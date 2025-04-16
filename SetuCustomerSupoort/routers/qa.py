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

        # Initialize vector store
        vectorstore = Chroma(
            persist_directory=os.path.join("chroma_db", product),
            embedding_function=embeddings
        )

        # Create a product-specific prompt template
        prompt_template = get_product_prompt_template(product)

        # Initialize memory and retriever
        memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key="answer"
        )
        
        # Use more results for better coverage
        retriever = vectorstore.as_retriever(
            search_kwargs={
                "k": 15,  # Increased from 10 to 15
                "filter": {"product": product}
            }
        )

        # Create the conversation chain
        conversation_chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=retriever,
            memory=memory,
            return_source_documents=True,
            output_key="answer",
            combine_docs_chain_kwargs={"prompt": prompt_template}
        )

        return conversation_chain
    except Exception as e:
        logger.error(f"Error initializing QA chain: {e}")
        raise

def get_product_prompt_template(product: str) -> PromptTemplate:
    """Get a product-specific prompt template"""
    base_template = """
You are a helpful assistant trained on {product} documentation.

Use the following context to answer the question. Be specific and concise.
Only answer based on the context provided. If the context doesn't contain the answer, say "I don't have enough information to answer this question."
Format your response using markdown for better readability.
Use bullet points, headers, and code blocks when appropriate.

Context:
{context}

Question:
{question}

Answer:
"""
    
    # Product-specific templates
    if product == "UMAP":
        template = """
You are a helpful assistant trained on Setu's UPI Setu (UMAP) documentation.

Use the following context to accurately answer questions about UMAP, including merchant onboarding, payment processing, and API integration.
Pay special attention to merchant onboarding steps and procedures when they are asked about.
Be specific, concise and accurate in your responses.

If you're asked about steps to onboard a merchant, be sure to provide the complete step-by-step process from the documentation.
Use clear numbered steps and provide all relevant API endpoints when discussing the merchant onboarding process.

Only answer based on the context provided. If the context doesn't contain the answer, say "I don't have enough information to answer this question."
Format your response using markdown for better readability.
Use bullet points, headers, and code blocks when appropriate.

Context:
{context}

Question:
{question}

Answer:
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
    
    async def generate_stream() -> AsyncGenerator[str, None]:
        """Generate a streaming response."""
        try:
            # Check if the product exists
            product_dir = os.path.join("chroma_db", request.product)
            if not os.path.exists(product_dir):
                yield f"No documentation found for product '{request.product}'. Please check the product name or add documentation first."
                # Send metadata at the end
                yield json.dumps({"sources": []})
                return
                
            # Get OpenAI API key
            api_key = retrieve_secret("OPENAI_API_KEY")
            if not api_key:
                yield "Error: OpenAI API key not configured."
                yield json.dumps({"sources": []})
                return

            # Initialize embeddings and LLM with streaming
            embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small",
                openai_api_key=api_key
            )
            
            # Use streaming LLM
            llm = ChatOpenAI(
                model_name="gpt-4-turbo-preview",
                temperature=0.7,
                streaming=True,
                openai_api_key=api_key
            )

            # Initialize vector store
            vectorstore = Chroma(
                persist_directory=os.path.join("chroma_db", request.product),
                embedding_function=embeddings
            )
            
            # Get retriever with product filter to ensure we only use this product's data
            retriever = vectorstore.as_retriever(
                search_kwargs={
                    "k": 10,
                    "filter": {"product": request.product}
                }
            )
            
            # Get relevant documents
            docs = retriever.get_relevant_documents(request.question)
            
            # Filter documents to ensure product match
            valid_docs = []
            for doc in docs:
                doc_product = doc.metadata.get("product", "")
                if doc_product == request.product or not doc_product:
                    valid_docs.append(doc)
            
            # Prepare context from documents
            context = "\n\n".join([doc.page_content for doc in valid_docs])
            
            # Format the prompt with markdown
            prompt = f"""
You are Setu Assistant, a helpful AI trained on {request.product} documentation.

Use the following context to answer the question.
Format your response using markdown for better readability.
Use bullet points, headers, and code blocks when appropriate.
If you cannot answer based on the context, say so.
Be accurate, helpful and concise.

Context:
{context}

Question:
{request.question}

Answer:
"""
            
            # Prepare sources metadata for later
            source_titles = [
                {
                    "title": doc.metadata.get("title", "Unknown"),
                    "page_id": doc.metadata.get("page_id", "Unknown"),
                    "type": doc.metadata.get("type", "Unknown"),
                    "product": doc.metadata.get("product", request.product)
                }
                for doc in valid_docs if doc.metadata.get("title")
            ]
            
            # If no valid documents found
            if not valid_docs:
                # Generate a more helpful response with markdown formatting
                no_docs_response = f"""## No Information Found

I don't have any information about '{request.product}' to answer your question.

Please try:
- Checking if you selected the correct product
- Adding documentation for this product first
- Asking about a different topic

If you believe this is an error, please contact support."""
                
                yield no_docs_response
                # Add a small delay before sending metadata to ensure proper separation
                await asyncio.sleep(0.1)
                yield json.dumps({"sources": []})
                return
            
            # Stream the response chunks
            response_chunks = []
            async for chunk in llm.astream(prompt):
                chunk_text = chunk.content
                response_chunks.append(chunk_text)
                yield chunk_text
                # Small delay to simulate natural typing
                await asyncio.sleep(0.01)
            
            # At the end, send the sources metadata as a JSON chunk
            await asyncio.sleep(0.1)  # Add a small delay before sending metadata
            yield json.dumps({"sources": source_titles})
            
        except Exception as e:
            logger.error(f"Error in streaming response: {e}")
            yield f"\n\nError: {str(e)}"
            yield json.dumps({"sources": []})
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream"
    )
