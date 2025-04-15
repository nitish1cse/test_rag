from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from services.confluence_service import fetch_and_store_documents, doc_store
from services.secret_store import secret_store, store_secret, retrieve_secret, reset_encryption
from services.product_service import product_service
import logging
import os
from chromadb import PersistentClient, Collection
from langchain_chroma import Chroma

router = APIRouter(prefix="/confluence", tags=["Confluence"])
logger = logging.getLogger(__name__)

class ConfluenceConfig(BaseModel):
    url: str
    username: str
    api_token: str

class DocumentRequest(BaseModel):
    product: str
    document_ids: List[str]

@router.post("/config")
async def configure_confluence(config: ConfluenceConfig):
    """Configure Confluence credentials"""
    try:
        # Reset encryption if needed
        if not store_secret("CONFLUENCE_URL", config.url):
            logger.info("Resetting encryption...")
            reset_encryption()
            
            # Try storing again
            if not store_secret("CONFLUENCE_URL", config.url):
                raise HTTPException(
                    status_code=500,
                    detail="Failed to store Confluence configuration"
                )

        # Store other credentials
        store_secret("CONFLUENCE_USERNAME", config.username)
        store_secret("CONFLUENCE_API_TOKEN", config.api_token)
        
        # Verify storage
        if not all([
            retrieve_secret("CONFLUENCE_URL"),
            retrieve_secret("CONFLUENCE_USERNAME"),
            retrieve_secret("CONFLUENCE_API_TOKEN")
        ]):
            raise HTTPException(
                status_code=500,
                detail="Failed to verify stored credentials"
            )
            
        return {"message": "Confluence configuration stored successfully"}
    except Exception as e:
        logger.error(f"Error configuring Confluence: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/documents")
async def store_documents(request: DocumentRequest) -> Dict:
    """Store Confluence documents for a product"""
    try:
        # Validate product
        if request.product not in product_service.get_all_products():
            raise HTTPException(status_code=400, detail=f"Invalid product: {request.product}")

        # Store documents
        result = fetch_and_store_documents(request.product, request.document_ids)
        
        # Update product docs based on successful document processing
        if result["success"] or result.get("processing_stats", {}).get("total_processed", 0) > 0:
            successful_docs = []
            failed_doc_ids = [doc["id"] for doc in result.get("failed", [])]
            
            # Only add documents that were successfully processed
            for doc_id in request.document_ids:
                if doc_id not in failed_doc_ids:
                    successful_docs.append(doc_id)
            
            if successful_docs:
                logger.info(f"Updating product_docs.json for {request.product} with {len(successful_docs)} documents")
                if not product_service.add_product_docs(request.product, successful_docs):
                    logger.error(f"Failed to update product_docs.json for {request.product}")
                    # Don't raise an exception here as the documents were still processed
        
        if not result["success"] and not result.get("message", "").startswith("No new"):
            error_msg = f"Failed to store documents. {len(result.get('failed', []))} documents failed."
            logger.error(f"{error_msg} Details: {result}")
            raise HTTPException(status_code=500, detail={
                "message": error_msg,
                "details": result
            })
        
        # Get updated document list after processing
        current_docs = product_service.get_product_docs(request.product)
        
        stats = result.get("processing_stats", {})
        return {
            "message": (
                f"Processing complete: {stats.get('unchanged', 0)} unchanged, "
                f"{stats.get('updated', 0)} updated "
                f"({stats.get('main_pages', 0)} main pages, "
                f"{stats.get('child_pages', 0)} child pages, "
                f"{stats.get('attachments', 0)} attachments) "
                f"with {result.get('chunks_stored', 0)} chunks stored"
            ),
            "details": {
                "total_requested": result.get("total_requested", 0),
                "processing_stats": stats,
                "chunks_stored": result.get("chunks_stored", 0),
                "failed_documents": result.get("failed", []),
                "current_product_docs": {
                    "product": request.product,
                    "total_docs": len(current_docs),
                    "document_ids": current_docs
                }
            }
        }
    except Exception as e:
        logger.error(f"Error in store_documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/products")
async def get_products() -> Dict:
    """Get all products and their document counts"""
    products = {}
    for product in product_service.get_all_products():
        doc_ids = product_service.get_product_docs(product)
        products[product] = {
            "document_count": len(doc_ids),
            "document_ids": doc_ids
        }
    return {"products": products}

@router.get("/products/{product}")
async def get_product_docs(product: str) -> Dict:
    """Get document IDs for a specific product"""
    if product not in product_service.get_all_products():
        raise HTTPException(status_code=404, detail=f"Product not found: {product}")
    
    doc_ids = product_service.get_product_docs(product)
    return {
        "product": product,
        "document_count": len(doc_ids),
        "document_ids": doc_ids
    }

@router.get("/documents/{product}")
async def get_document_stats(product: str) -> Dict:
    """Get document statistics for a product"""
    try:
        vectorstore = doc_store.get_vectorstore(product)
        if not vectorstore:
            return {
                "product": product,
                "document_count": 0,
                "status": "No documents found"
            }
            
        collection = vectorstore._collection
        count = collection.count()
        
        return {
            "product": product,
            "document_count": count,
            "status": "active" if count > 0 else "empty"
        }
    except Exception as e:
        logger.error(f"Error getting document stats for {product}: {e}")
        raise HTTPException(status_code=500, detail=str(e))



