from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import List, Dict
from services.url_service import url_store
from services.product_service import product_service
import logging
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from services.secret_store import retrieve_secret
import os
from datetime import datetime

router = APIRouter(prefix="/url", tags=["URL"])
logger = logging.getLogger(__name__)

class URLRequest(BaseModel):
    product: str
    urls: List[HttpUrl]

@router.post("/store")
async def store_urls(request: URLRequest) -> Dict:
    """Store URL content for a product"""
    try:
        # Validate product
        if request.product not in product_service.get_all_products():
            raise HTTPException(status_code=400, detail=f"Invalid product: {request.product}")

        # Store URLs
        result = url_store.store_urls(request.product, [str(url) for url in request.urls])
        
        if not result["success"]:
            error_msg = f"Failed to store URLs. {result['processing_stats']['failed']} URLs failed."
            logger.error(f"{error_msg} Details: {result}")
            raise HTTPException(status_code=500, detail={
                "message": error_msg,
                "details": result
            })
        
        stats = result["processing_stats"]
        return {
            "message": (
                f"Processing complete: {stats['pages_processed']} pages processed "
                f"({stats['successful']} root URLs successful, {stats['failed']} failed), "
                f"{stats['chunks_stored']} chunks stored"
            ),
            "details": {
                "processing_stats": stats,
                "failed_urls": result["failed"],
                "crawl_details": result.get("details", {})
            }
        }
    except Exception as e:
        logger.error(f"Error in store_urls: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/{product}")
async def get_url_stats(product: str) -> Dict:
    """Get URL statistics for a product"""
    try:
        vectorstore = url_store.get_vectorstore(product)
        if not vectorstore:
            return {
                "product": product,
                "url_count": 0,
                "status": "No URLs found"
            }
            
        collection = vectorstore._collection
        count = collection.count()
        
        return {
            "product": product,
            "url_count": count,
            "status": "active" if count > 0 else "empty"
        }
    except Exception as e:
        logger.error(f"Error getting URL stats for {product}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/crawl-merchant-docs")
async def crawl_merchant_docs() -> Dict:
    """Special endpoint to directly crawl merchant onboarding documentation"""
    try:
        # Hardcode the specific URL and product for merchant onboarding
        product = "UMAP"
        merchant_url = "https://docs.setu.co/payments/umap/merchant-onboarding"
        
        logger.info(f"Starting special crawl for merchant onboarding documentation: {merchant_url}")
        
        # Store URL with extra emphasis on content extraction
        result = url_store.store_urls(product, [merchant_url])
        
        if not result["success"]:
            error_msg = f"Failed to crawl merchant documentation: {result.get('error', 'Unknown error')}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
        
        stats = result["processing_stats"]
        return {
            "message": (
                f"Merchant onboarding documentation crawl complete: {stats['pages_processed']} pages processed, "
                f"{stats['chunks_stored']} chunks stored"
            ),
            "details": {
                "processing_stats": stats,
                "merchant_content_url": merchant_url,
                "product": product
            }
        }
    except Exception as e:
        logger.error(f"Error in merchant docs crawl: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/inject-merchant-content")
async def inject_merchant_content() -> Dict:
    """Directly inject merchant onboarding content into the vectorstore"""
    try:
        # Hardcode the product
        product = "UMAP"
        
        # Create a document with the merchant onboarding steps
        merchant_content = """# Merchant On-boarding

## Steps to on-board a merchant

An aggregator can seamlessly on-board merchants onto the UPI Setu ecosystem, and enable them to start accepting UPI payments. This journey starts from collecting a merchant's business details, setting up their configuration and as the final step activation of the merchant's ability to process transactions.

### Step 1 - Share information about merchant

As the first step, the operations team gathers necessary details from the merchant, ensuring that the UPI Setu system has all the relevant information to proceed with the on-boarding process.

### Step 2 - Setup a merchant

After getting the merchant's information, a preliminary verification is conducted. Then, a record for the merchant is created in the UPI Setu system, which formally initiates their on-boarding journey.

Create merchant API is used for this step.

### Step 3 - Register a VPA

A VPA has to be created for the merchant, before they can start transacting on UPI Setu. This gives the merchant the capability to accept payments via UPI, completing the on-boarding process. This can include 2 steps—

#### Check if a VPA is available (optional)

This API helps you check the availability of a desired VPA, to ensure it is unique and can be assigned to the merchant without conflicts.

Check VPA availability API is used for this step.

#### Register VPA (required)

The next API is used to assign a VPA to the merchant. With this, merchant on-boarding is completed seamlessly! The merchant can now initiate transactions on UPI.

Create VPA API is used for this step.

## Manage your merchants

### Update merchant status

If a merchant needs to be disabled by an aggregator then they can call this API to update their status. If a merchant is disabled UPI Setu will decline all transactions to the VPA assigned to this particular merchant.

Update merchant status API is used for this.

### Update merchant details

This API can be called to update the information associated with the merchant like settlement configuration or KYC information that may be required for accepting different payment instruments on UPI.

Update merchant details API is used for this.
"""
        
        # Create the document
        doc = Document(
            page_content=merchant_content,
            metadata={
                "url": "https://docs.setu.co/payments/umap/merchant-onboarding",
                "url_hash": "merchant_onboarding_manual",
                "domain": "docs.setu.co",
                "path": "/payments/umap/merchant-onboarding",
                "type": "url",
                "depth": 0,
                "fetched_at": datetime.now().isoformat(),
                "title": "Merchant On-boarding",
                "section": "payments",
                "subsection": "umap",
                "is_setu_docs": True,
                "product": product,
                "source": "manual_injection" 
            }
        )
        
        # Split into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        chunks = text_splitter.split_documents([doc])
        
        # Get the vectorstore
        api_key = retrieve_secret("OPENAI_API_KEY")
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=api_key
        )
        
        vectorstore = Chroma(
            persist_directory=os.path.join("chroma_db", product),
            embedding_function=embeddings
        )
        
        # Add chunks to vectorstore
        vectorstore.add_documents(chunks)
        
        return {
            "message": f"Successfully injected {len(chunks)} chunks of merchant onboarding content",
            "details": {
                "chunks": len(chunks),
                "product": product
            }
        }
    except Exception as e:
        logger.error(f"Error injecting merchant content: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 