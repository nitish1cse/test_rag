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
        """
        Get an answer to a question based on a specific product's documentation.
        Ensures that only context from the requested product is used.
        """
        try:
            # Get relevant documents from only the specified product
            docs = self.vectorstore.search(question, product_code)
            
            if not docs:
                return f"No relevant information found for this question in the {product_code} documentation."
            
            # Verify documents are from the requested product
            filtered_docs = []
            for doc in docs:
                doc_product = doc.metadata.get("product", "")
                if doc_product == product_code or not doc_product:
                    filtered_docs.append(doc)
            
            if not filtered_docs:
                return f"No relevant information found in the {product_code} documentation."
            
            # Create context from product-specific documents
            context = "\n\n".join([doc.page_content for doc in filtered_docs])
            
            # Generate answer using ChatGPT
            prompt = f"""Based on the following context from {product_code} documentation, answer the question. 
If you cannot answer based on the context, say that you don't have enough information in the {product_code} documentation.

Context: {context}

Question: {question}

Answer:"""
            
            response = self.llm.predict(prompt)
            return response
            
        except Exception as e:
            return f"Error retrieving information from {product_code} documentation: {str(e)}" 