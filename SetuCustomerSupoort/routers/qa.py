from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, AsyncGenerator
from services.secret_store import retrieve_secret
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate
from datetime import datetime
import os
import logging
import json
import asyncio
from services.vectorstore import VectorStore

router = APIRouter(prefix="/qa", tags=["QA"])
logger = logging.getLogger(__name__)

# Initialize the VectorStore service once for reuse
vector_store = VectorStore()

class QuestionRequest(BaseModel):
    product: str
    question: str

class FeedbackRequest(BaseModel):
    question: str
    answer: str
    is_helpful: bool

# Store feedback
feedback_store: Dict[str, List[Dict]] = {}

# Define the prompt template
TROUBLESHOOT_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template="""
You are a helpful assistant trained on Account Aggregator engineering documentation.

Use the following context to help troubleshoot issues related to data not appearing in webhooks/API responses from banks.
If applicable, clearly identify root causes (e.g. FIP_DENIED, data block empty, notification not received) and next steps.
If question references JSON, respond based on parsed meaning.
if you don't know the answer, just say that you don't know. dont make up an answer.

Context:
{context}

Question:
{question}

Answer:
"""
)

def get_qa_chain(product: str):
    """Initialize QA chain for a product"""
    try:
        # Get OpenAI API key
        api_key = retrieve_secret("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not configured")

        # Initialize embeddings and LLM
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=api_key
        )
        llm = ChatOpenAI(
            model_name="gpt-4-turbo-preview",
            temperature=0.2,  # Reduced temperature for more factual responses
            streaming=True,
            openai_api_key=api_key
        )

        # Use the VectorStore already initialized at module level
        # This will access all documents, including GitHub and Confluence
        retriever = vector_store.search
        
        # Create memory
        memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key="answer"
        )
        
        # Create a product-specific prompt template
        prompt_template = get_product_prompt_template(product)

        # Custom implementation of ConversationalRetrievalChain to use our VectorStore
        class CustomConversationalChain:
            def __init__(self, llm, retriever, memory, prompt_template, product):
                self.llm = llm
                self.retriever = retriever
                self.memory = memory
                self.prompt_template = prompt_template
                self.product = product
                self.history = []
                
            def invoke(self, inputs):
                question = inputs["question"]
                
                # Add to history
                if "chat_history" in inputs:
                    self.history = inputs["chat_history"]
                
                # Get documents from retriever
                docs = self.retriever(question, self.product, k=15)
                
                # Format context from documents
                context = "\n\n".join([doc.page_content for doc in docs])
                
                # Format prompt with context and question
                formatted_prompt = self.prompt_template.format(
                    context=context,
                    question=question
                )
                
                # Generate answer using LLM
                answer = self.llm.predict(formatted_prompt)
                
                # Return answer and source documents
                return {
                    "answer": answer,
                    "source_documents": docs
                }

        return CustomConversationalChain(
            llm=llm,
            retriever=retriever,
            memory=memory,
            prompt_template=prompt_template,
            product=product
        )
    except Exception as e:
        logger.error(f"Error initializing QA chain: {e}")
        raise

def get_product_prompt_template(product: str) -> PromptTemplate:
    """Get a product-specific prompt template"""
    base_template = """
You are a helpful human support assistant from Setu who specializes in {product}.
Use the following reference information to answer the question:
{context}


Question:
{question}

"""

    # Product-specific templates
    if product == "UMAP":
        template = """
You are a helpful human support assistant at Setu who specializes in UPI Setu (UMAP) integration.




{context}

Question:
{question}

Your helpful human response:
"""
    elif product == "ACCOUNT_AGGREGATOR":
        template = """
You are a helpful human support assistant at Setu who specializes in Account Aggregator.



Use the following reference information to answer their question:
{context}

Question:
{question}

Your helpful human response:
"""
    else:
        template = base_template.replace("{product}", product)

    return PromptTemplate(
        input_variables=["context", "question"],
        template=template
    )

@router.post("/ask")
async def ask_question(request: QuestionRequest):
    """Ask a question about a product's documentation"""
    try:
        # Check if the product exists
        product_dir = os.path.join("chroma_db", request.product)
        if not os.path.exists(product_dir):
            return {
                "answer": f"No documentation found for product '{request.product}'. Please check the product name or add documentation first.",
                "sources": [],
                "previous_feedback": []
            }
            
        # Get QA chain for the product
        conversation_chain = get_qa_chain(request.product)

        # Log the question for debugging
        logger.info(f"Processing question for product '{request.product}': {request.question}")

        # Get answer
        result = conversation_chain.invoke({
            "question": request.question
        })

        # Extract answer and sources
        answer = result["answer"]
        sources = result.get("source_documents", [])
        
        # Log source count for debugging
        logger.info(f"Found {len(sources)} sources for product '{request.product}'")
        
        # Verify that sources are from the requested product
        valid_sources = []
        for doc in sources:
            doc_product = doc.metadata.get("product", "")
            if doc_product == request.product or not doc_product:  # Allow docs without product tag if from product-specific collection
                valid_sources.append(doc)
        
        # Log the number of valid sources
        logger.info(f"After filtering, {len(valid_sources)} valid sources remain")
        
        source_titles = [
            {
                "title": doc.metadata.get("title", "Unknown"),
                "page_id": doc.metadata.get("page_id", "Unknown"),
                "type": doc.metadata.get("type", "URL" if doc.metadata.get("url") else "Unknown"),
                "product": doc.metadata.get("product", request.product),
                "url": doc.metadata.get("url", "")  # Include URL for web sources
            }
            for doc in valid_sources if doc.metadata.get("title") or doc.metadata.get("url")
        ]

        # Get previous feedback
        prior_feedbacks = feedback_store.get(request.question, [])

        return {
            "answer": answer,
            "sources": source_titles,
            "previous_feedback": prior_feedbacks[-3:] if prior_feedbacks else []
        }

    except Exception as e:
        logger.error(f"Error processing question: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """Submit feedback for an answer"""
    try:
        feedback_store.setdefault(request.question, []).append({
            "answer": request.answer,
            "feedback": "👍" if request.is_helpful else "👎",
            "timestamp": datetime.now().isoformat()
        })
        return {"message": "Feedback submitted successfully"}
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/feedback/{question}")
async def get_feedback(question: str):
    """Get feedback history for a question"""
    return {
        "question": question,
        "feedback_history": feedback_store.get(question, [])
    }

@router.post("/ask/stream")
async def ask_question_stream(request: QuestionRequest):
    """Ask a question about a product's documentation with streaming response"""
    try:
        # Check if the product exists
        product_dir = os.path.join("chroma_db", request.product)
        if not os.path.exists(product_dir):
            # Create an error generator instead of trying to return from inside yield
            async def error_generator():
                error_message = (f"No documentation found for product '{request.product}'. "
                             f"Please check the product name or add documentation first.")
                yield error_message
                yield f'\n\n{{"sources": []}}'
                
            return StreamingResponse(error_generator(), media_type="text/plain")
            
        # Get QA chain for the product
        conversation_chain = get_qa_chain(request.product)

        # Log the question for debugging
        logger.info(f"Processing streaming question for product '{request.product}': {request.question}")
        
        async def generate_stream() -> AsyncGenerator[str, None]:
            try:
                # Get result but not streaming part yet
                result = conversation_chain.invoke({
                    "question": request.question
                })
                
                # Extract answer and process
                answer = result["answer"]
                
                # Yield the answer for streaming
                yield answer
                
                # After streaming the content, send the sources as JSON
                sources = result.get("source_documents", [])
                
                # Format the sources as needed
                source_titles = [
                    {
                        "title": doc.metadata.get("title", "Unknown"),
                        "page_id": doc.metadata.get("page_id", "Unknown"),
                        "type": doc.metadata.get("type", "URL" if doc.metadata.get("url") else "Unknown"),
                        "product": doc.metadata.get("product", request.product),
                        "url": doc.metadata.get("url", "")
                    }
                    for doc in sources if doc.metadata.get("title") or doc.metadata.get("url")
                ]
                
                # Yield the sources as JSON
                yield f'\n\n{{"sources": {json.dumps(source_titles)}}}'
                
            except Exception as e:
                logger.error(f"Error in stream generation: {e}")
                yield f"Error generating answer: {str(e)}"
        
        return StreamingResponse(generate_stream(), media_type="text/plain")
        
    except Exception as e:
        logger.error(f"Error processing streaming question: {e}")
        raise HTTPException(status_code=500, detail=str(e))
