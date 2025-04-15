from typing import Optional
from langchain_community.chat_models import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from services.vectorstore import VectorStore
import config

class QAService:
    def __init__(self):
        self.vectorstore = VectorStore()
        self.llm = ChatOpenAI(
            model_name=config.OPENAI_MODEL,
            temperature=config.OPENAI_TEMPERATURE,
            api_key=config.OPENAI_API_KEY
        )
        
    def get_answer(self, product_code: str, question: str) -> str:
        try:
            # Get relevant documents
            docs = self.vectorstore.search(question, product_code)
            
            if not docs:
                return "No relevant information found for this question."
            
            # Create context from documents
            context = "\n\n".join([doc.page_content for doc in docs])
            
            # Generate answer using ChatGPT
            prompt = f"""Based on the following context, answer the question. If you cannot answer based on the context, say so.

            Context: {context}

            Question: {question}

            Answer:"""
            
            response = self.llm.predict(prompt)
            return response
            
        except Exception as e:
            return f"Error: {str(e)}" 