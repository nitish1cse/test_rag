import os
import hashlib
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
import config
from db.storage import retrieve_secret
from typing import List, Optional
from langchain.docstore.document import Document
import chromadb
from chromadb.config import Settings
from config import CHROMA_DIR

# Dictionary to store document hashes for tracking changes
document_hashes = {}



def update_vectorstore(documents, product=None):
    """Update the vectorstore with only new or changed documents."""
    # Get the API key from the config or retrieve it from storage
    api_key = config.OPENAI_API_KEY or retrieve_secret("OPENAI_API_KEY")
    
    if not api_key:
        print("Warning: OpenAI API key not found")
        return None
    
    # Initialize document tracking if not already done
    global document_hashes
    
    # Identify new or changed documents
    new_or_changed_docs = []
    current_hashes = {}
    
    for doc in documents:
        # Add product metadata if provided
        if product and "product" not in doc.metadata:
            doc.metadata["product"] = product
    
    # Update our hash tracking
    document_hashes.update(current_hashes)
    
    # If no new or changed documents, return the existing vectorstore
    if not new_or_changed_docs and config.VECTORSTORE is not None:
        print("No new or changed documents detected. Using existing vectorstore.")
        return config.VECTORSTORE
    
    # Process documents if there are new or changed ones
    if new_or_changed_docs:
        print(f"Processing {len(new_or_changed_docs)} new or changed documents")
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.split_documents(new_or_changed_docs)
        
        # Filter complex metadata before adding to vectorstore
        cleaned_chunks = []
        for chunk in chunks:
            # Ensure metadata exists and is a dictionary
            if not hasattr(chunk, 'metadata') or not isinstance(chunk.metadata, dict):
                chunk.metadata = {}
            
            # Create a new metadata dictionary with filtered values
            filtered_metadata = {}
            for key, value in chunk.metadata.items():
                # Only include simple types
                if isinstance(value, (str, int, float, bool)) and value is not None:
                    filtered_metadata[key] = value
            
            # Set the filtered metadata back to the chunk
            chunk.metadata = filtered_metadata
            
            # Ensure product is set in metadata if provided
            if product:
                chunk.metadata['product'] = product
            
            cleaned_chunks.append(chunk)
        
        # Create or update the vectorstore
        if config.VECTORSTORE is None:
            # Create a new vectorstore
            embeddings = OpenAIEmbeddings(openai_api_key=api_key)
            config.VECTORSTORE = Chroma.from_documents(
                documents=cleaned_chunks,
                embedding=embeddings,
                persist_directory="./chroma_db"
            )
            print(f"Created new vectorstore with {len(cleaned_chunks)} chunks")
        else:
            # Add new documents to existing vectorstore
            config.VECTORSTORE.add_documents(cleaned_chunks)
            print(f"Added {len(cleaned_chunks)} chunks to existing vectorstore")
    
    # Print debug information
    if config.VECTORSTORE:
        collection = config.VECTORSTORE._collection
        count = collection.count()
        if count > 0:
            sample_embedding = collection.get(limit=1, include=["embeddings"])["embeddings"][0]
            dimensions = len(sample_embedding)
            print(f"Vectorstore contains {count:,} vectors of {dimensions:,} dimensions")
        else:
            print("Warning: Vectorstore contains no vectors")
    else:
        print("Warning: Failed to create vectorstore")
    
    return config.VECTORSTORE

def get_product_specific_retriever(product):
    """Get a retriever that only returns documents for a specific product."""
    if config.VECTORSTORE is None:
        return None
    
    # Create a search filter for the specific product
    search_filter = {"product": product}
    
    # Return a retriever with the product filter
    return config.VECTORSTORE.as_retriever(
        search_kwargs={
            "k": 10,
            "filter": search_filter
        }
    )

def persist_vectorstore():
    """Persist the vectorstore to disk."""
    if config.VECTORSTORE:
        try:
            # In newer versions of langchain-chroma, the persist method might not be available
            # Instead, we can use _collection.persist() or just rely on the auto-persistence
            if hasattr(config.VECTORSTORE, "persist"):
                config.VECTORSTORE.persist()
            elif hasattr(config.VECTORSTORE, "_collection") and hasattr(config.VECTORSTORE._collection, "persist"):
                config.VECTORSTORE._collection.persist()
            else:
                # For newer versions, Chroma might persist automatically when documents are added
                print("Using auto-persistence for Chroma vectorstore")
            print("Vectorstore persisted to disk")
        except Exception as e:
            print(f"Error persisting vectorstore: {e}")

def load_vectorstore():
    """Load the vectorstore from disk if it exists."""
    api_key = config.OPENAI_API_KEY or retrieve_secret("OPENAI_API_KEY")
    
    if not api_key:
        print("Warning: OpenAI API key not found")
        return None
    
    if os.path.exists("./chroma_db"):
        try:
            embeddings = OpenAIEmbeddings(openai_api_key=api_key)
            config.VECTORSTORE = Chroma(
                persist_directory="./chroma_db",
                embedding_function=embeddings
            )
            print("Loaded vectorstore from disk")
            return config.VECTORSTORE
        except Exception as e:
            print(f"Error loading vectorstore: {e}")
    
    return None

class VectorStore:
    def __init__(self):
        # Create directory if it doesn't exist
        os.makedirs(CHROMA_DIR, exist_ok=True)
        
        # Initialize ChromaDB with new configuration
        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DIR)
        )
        
    def add_documents(self, documents: List[Document], product_code: str):
        collection = self.client.get_or_create_collection(name=product_code)
        
        # Extract text and metadata
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        ids = [str(i) for i in range(len(documents))]
        
        # Add to collection
        collection.add(
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
        
    def search(self, query: str, product_code: str, k: int = 3) -> List[Document]:
        collection = self.client.get_collection(name=product_code)
        results = collection.query(
            query_texts=[query],
            n_results=k
        )
        
        # Convert results to Documents
        documents = []
        for i, text in enumerate(results['documents'][0]):
            doc = Document(
                page_content=text,
                metadata=results['metadatas'][0][i]
            )
            documents.append(doc)
            
        return documents

    def get_collection_stats(self, product_code: str) -> dict:
        try:
            collection = self.client.get_collection(name=product_code)
            return {
                "count": collection.count(),
                "name": product_code
            }
        except ValueError:
            return {
                "count": 0,
                "name": product_code
            }
