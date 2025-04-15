from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
from services.secret_store import retrieve_secret
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate
from datetime import datetime
import os
import logging

router = APIRouter(prefix="/qa", tags=["QA"])
logger = logging.getLogger(__name__)

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
            temperature=0.7,
            streaming=True,
            openai_api_key=api_key
        )

        # Initialize vector store
        vectorstore = Chroma(
            persist_directory=os.path.join("chroma_db", product),
            embedding_function=embeddings
        )

        # Initialize memory and retriever
        memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key="answer"
        )
        retriever = vectorstore.as_retriever(search_kwargs={"k": 10})

        # Create the conversation chain
        conversation_chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=retriever,
            memory=memory,
            return_source_documents=True,
            output_key="answer",
            combine_docs_chain_kwargs={"prompt": TROUBLESHOOT_PROMPT}
        )

        return conversation_chain
    except Exception as e:
        logger.error(f"Error initializing QA chain: {e}")
        raise

@router.post("/ask")
async def ask_question(request: QuestionRequest):
    """Ask a question about a product's documentation"""
    try:
        # Get QA chain for the product
        conversation_chain = get_qa_chain(request.product)

        # Get answer
        result = conversation_chain.invoke({
            "question": request.question
        })

        # Extract answer and sources
        answer = result["answer"]
        sources = result.get("source_documents", [])
        source_titles = [
            {
                "title": doc.metadata.get("title", "Unknown"),
                "page_id": doc.metadata.get("page_id", "Unknown"),
                "type": doc.metadata.get("type", "Unknown")
            }
            for doc in sources if doc.metadata.get("title")
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
