from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import List, Dict, Optional
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
import requests
import base64
import re
import asyncio
import shutil
import tempfile
import subprocess
import glob

router = APIRouter(prefix="/url", tags=["URL"])
logger = logging.getLogger(__name__)

class URLRequest(BaseModel):
    urls: List[HttpUrl]
    product: Optional[str] = None  # Optional product, will be auto-detected if not provided

class GitHubRequest(BaseModel):
    repo_url: str
    folders: str  # comma-separated list of folders to fetch
    token: Optional[str] = None  # Optional GitHub token for authentication

@router.post("/store")
async def store_urls(request: URLRequest) -> Dict:
    """Store URL content for a product (auto-detected if not specified)"""
    try:
        urls = [str(url) for url in request.urls]
        
        # If product is provided, validate it
        if request.product and request.product not in product_service.get_all_products():
            raise HTTPException(status_code=400, detail=f"Invalid product: {request.product}")

        # Store URLs with automatic product detection
        result = url_store.store_urls(urls, default_product=request.product)
        
        if not result["success"]:
            error_msg = f"Failed to store URLs. {result['processing_stats']['failed']} URLs failed."
            logger.error(f"{error_msg} Details: {result}")
            raise HTTPException(status_code=500, detail={
                "message": error_msg,
                "details": result
            })
        
        stats = result["processing_stats"]
        products_detected = result.get("details", {}).get("products_detected", {})
        
        # Format the product detection information
        product_info = ", ".join([f"{product}: {count}" for product, count in products_detected.items()])
        
        return {
            "message": (
                f"Processing complete: {stats['pages_processed']} pages processed "
                f"({stats['successful']} root URLs successful, {stats['failed']} failed), "
                f"{stats['chunks_stored']} chunks stored. "
                f"Products detected: {product_info}"
            ),
            "details": {
                "processing_stats": stats,
                "failed_urls": result.get("failed", []),
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

@router.post("/auto-crawl")
async def auto_crawl_url(url: str) -> Dict:
    """Crawl a single URL and automatically detect its product"""
    try:
        # Validate URL
        if not url or not url.startswith(('http://', 'https://')):
            raise HTTPException(status_code=400, detail="Invalid URL")
        
        # Store the URL with automatic product detection
        result = url_store.store_urls([url])
        
        if not result["success"]:
            error_msg = f"Failed to crawl URL: {result.get('error', 'Unknown error')}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
        
        # Extract detected product info
        products_detected = result.get("details", {}).get("products_detected", {})
        main_product = next(iter(products_detected.keys())) if products_detected else "Unknown"
        
        stats = result["processing_stats"]
        return {
            "message": f"URL crawled successfully and categorized as {main_product}",
            "details": {
                "url": url,
                "product_detected": main_product,
                "pages_processed": stats["pages_processed"],
                "chunks_stored": stats["chunks_stored"]
            }
        }
    except Exception as e:
        logger.error(f"Error in auto crawl: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/github")
async def fetch_github_content(request: GitHubRequest) -> Dict:
    """Fetch MDX content from a GitHub repository and automatically detect products"""
    temp_dir = None
    try:
        logger.info(f"Starting GitHub content fetch from: {request.repo_url}")
        
        # Parse the GitHub URL to extract owner and repo
        match = re.match(r'https?://github\.com/([^/]+)/([^/]+)', request.repo_url)
        if not match:
            raise HTTPException(status_code=400, detail="Invalid GitHub URL format")
        
        owner, repo = match.groups()
        folders = [folder.strip() for folder in request.folders.split(',')]
        
        # Initialize statistics counters
        stats = {
            "files_processed": 0,
            "successful": 0,
            "failed": 0,
            "chunks_stored": 0
        }
        products_detected = {}
        failed_files = []
        
        # Create a temporary directory for cloning
        temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary directory: {temp_dir}")
        
        # Construct the git clone command
        clone_url = f"https://github.com/{owner}/{repo}.git"
        if request.token:
            # Use token in clone URL for authentication
            clone_url = f"https://{request.token}@github.com/{owner}/{repo}.git"
            
        logger.info(f"Cloning repository {clone_url} to {temp_dir}")
        
        # Clone the repository
        try:
            subprocess.run(
                ["git", "clone", clone_url, temp_dir],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            logger.info(f"Successfully cloned repository")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error cloning repository: {e.stderr.decode('utf-8')}")
            raise HTTPException(status_code=500, detail=f"Error cloning repository: {e.stderr.decode('utf-8')}")
        
        # Process each requested folder
        for folder in folders:
            folder_path = os.path.join(temp_dir, folder)
            if not os.path.exists(folder_path):
                logger.warning(f"Folder {folder} does not exist in the repository")
                failed_files.append({
                    "folder": folder,
                    "reason": "Folder doesn't exist in repository"
                })
                continue
                
            logger.info(f"Processing folder: {folder}")
            
            # Find all .mdx files in the folder recursively
            mdx_pattern = os.path.join(folder_path, "**", "*.mdx")
            mdx_files = glob.glob(mdx_pattern, recursive=True)
            
            logger.info(f"Found {len(mdx_files)} MDX files in {folder}")
            
            # Process each MDX file
            for mdx_file in mdx_files:
                try:
                    stats["files_processed"] += 1
                    
                    # Read the file content
                    with open(mdx_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Get relative path within the repository
                    relative_path = os.path.relpath(mdx_file, temp_dir)
                    
                    # Extract product from file path
                    # Example path: content/payments/umap/overview.mdx
                    path_parts = relative_path.split(os.path.sep)
                    product = None
                    
                    if len(path_parts) >= 3 and path_parts[0] == 'content':
                        # The product is typically the second folder in content/category/product/
                        category = path_parts[1]
                        product_folder = path_parts[2]
                        
                        # Verify this is a valid product
                        all_products = product_service.get_all_products()
                        
                        # Try exact match first
                        if product_folder.upper() in all_products:
                            product = product_folder.upper()
                        else:
                            # Try partial match (some products might be named differently)
                            for p in all_products:
                                if p.lower() in product_folder.lower() or product_folder.lower() in p.lower():
                                    product = p
                                    break
                    
                    # If product is still None, try to detect from content
                    if not product:
                        # Use a simple keyword-based approach
                        product = url_store.detect_product_from_content(content)
                    
                    if not product:
                        logger.warning(f"Could not detect product for {relative_path}")
                        failed_files.append({
                            "file": relative_path,
                            "reason": "Could not detect product"
                        })
                        stats["failed"] += 1
                        continue
                    
                    # Create a document for the vector store
                    file_url = f"https://github.com/{owner}/{repo}/blob/main/{relative_path}"
                    file_hash = f"github_{owner}_{repo}_{os.path.basename(mdx_file)}"
                    
                    doc = Document(
                        page_content=content,
                        metadata={
                            "url": file_url,
                            "url_hash": file_hash,
                            "domain": "github.com",
                            "path": relative_path,
                            "type": "github",
                            "fetched_at": datetime.now().isoformat(),
                            "title": os.path.basename(mdx_file).replace('.mdx', ''),
                            "product": product,
                            "source": "github" 
                        }
                    )
                    
                    # Store the document in the vector store
                    chunks = url_store.add_document_to_vectorstore(doc, product)
                    
                    # Update statistics
                    stats["successful"] += 1
                    stats["chunks_stored"] += chunks
                    products_detected[product] = products_detected.get(product, 0) + 1
                    
                except Exception as e:
                    logger.error(f"Error processing file {mdx_file}: {e}")
                    relative_path = os.path.relpath(mdx_file, temp_dir)
                    failed_files.append({
                        "file": relative_path,
                        "reason": str(e)
                    })
                    stats["failed"] += 1
        
        return {
            "message": (
                f"GitHub content fetch complete: {stats['files_processed']} files processed "
                f"({stats['successful']} successful, {stats['failed']} failed), "
                f"{stats['chunks_stored']} chunks stored. "
                f"Products detected: {', '.join([f'{p}: {c}' for p, c in products_detected.items()])}"
            ),
            "details": {
                "processing_stats": stats,
                "failed_files": failed_files,
                "products_detected": products_detected
            }
        }
                
    except Exception as e:
        logger.error(f"Error in fetch_github_content: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up the temporary directory
        if temp_dir and os.path.exists(temp_dir):
            logger.info(f"Cleaning up temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir, ignore_errors=True) 