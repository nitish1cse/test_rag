from typing import List, Dict, Optional, Set
import logging
import os
from bs4 import BeautifulSoup
import requests
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from services.secret_store import retrieve_secret
import hashlib
from urllib.parse import urlparse, urljoin
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)

class URLDocStore:
    def __init__(self):
        self.chroma_dir = "chroma_db"
        os.makedirs(self.chroma_dir, exist_ok=True)
        
        # Get OpenAI API key
        api_key = retrieve_secret("OPENAI_API_KEY")
        if not api_key:
            logger.error("OpenAI API key not configured")
            raise ValueError("OpenAI API key not configured")
        
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=api_key
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        # Settings for recursive crawling
        self.max_depth = 3  # Maximum depth to crawl
        self.max_urls_per_domain = 100  # Maximum URLs to process per domain
        
        logger.info(f"Initialized URLDocStore at {self.chroma_dir}")

    def get_vectorstore(self, product: str) -> Chroma:
        """Get or create a Chroma vectorstore for a specific product"""
        try:
            api_key = retrieve_secret("OPENAI_API_KEY")
            if not api_key:
                logger.error("OpenAI API key not configured")
                raise ValueError("OpenAI API key not configured")
                
            embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small",
                openai_api_key=api_key
            )
            
            product_dir = os.path.join(self.chroma_dir, product)
            os.makedirs(product_dir, exist_ok=True)
            
            vectorstore = Chroma(
                persist_directory=product_dir,
                embedding_function=embeddings
            )
            
            logger.info(f"Retrieved vectorstore for product {product}")
            return vectorstore
            
        except Exception as e:
            logger.error(f"Error getting vectorstore for product {product}: {e}")
            raise

    def get_url_hash(self, url: str) -> str:
        """Generate a unique hash for a URL"""
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    def clean_html(self, html_content: str) -> str:
        """Clean HTML content and extract text with improved handling for modern websites"""
        if not html_content:
            return ""
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Enhanced text extraction specifically for Setu docs format
        main_content = soup.find('main') or soup.find('article') or soup.find('div', {'class': 'content'}) or soup
        
        # Remove unwanted elements that might contain navigation or irrelevant text
        for element in main_content(["script", "style", "nav", "footer", "header"]):
            element.decompose()
        
        # Special handling for Setu documentation - extract headings and their content
        content_blocks = []
        
        # Add title
        if soup.title:
            content_blocks.append(f"# {soup.title.string.strip()}\n")
        
        # Extract all headings and their content
        headings = main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        
        # If we found headings, extract them and their content
        if headings:
            for heading in headings:
                heading_level = int(heading.name[1])
                heading_text = heading.get_text(strip=True)
                
                # Skip empty headings
                if not heading_text:
                    continue
                    
                # Add heading with appropriate markdown level
                content_blocks.append(f"{'#' * heading_level} {heading_text}\n")
                
                # Find all siblings until next heading or end
                current = heading.next_sibling
                siblings_text = []
                
                while current and not (current.name and current.name.startswith('h')):
                    if current.name:
                        # Handle list items
                        if current.name == 'ul':
                            for li in current.find_all('li'):
                                siblings_text.append(f"* {li.get_text(strip=True)}")
                        # Handle paragraphs and other block elements
                        elif current.name in ['p', 'div', 'section']:
                            text = current.get_text(strip=True)
                            if text:
                                siblings_text.append(text)
                    current = current.next_sibling
                
                if siblings_text:
                    content_blocks.append("\n".join(siblings_text) + "\n")
        
        # If no headings were found, fall back to basic text extraction
        if not content_blocks or len(content_blocks) < 2:  # Just title or empty
            # Get text and clean it
            text = main_content.get_text(separator="\n", strip=True)
            if text:
                content_blocks = [text]
        
        # Join all blocks with double newlines for better separation
        final_text = "\n\n".join(content_blocks)
        
        # Special post-processing for Setu docs format - clean up excess whitespace
        final_text = "\n".join(line.strip() for line in final_text.split("\n") if line.strip())
        
        # Log the length of extracted content for debugging
        logger.info(f"Extracted {len(final_text)} characters of text content")
        
        return final_text

    def extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract all links from a page with improved handling for different link formats"""
        links = []
        base_domain = urlparse(base_url).netloc
        base_path = urlparse(base_url).path.rstrip('/')
        
        # Find all links in the page
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Skip empty, javascript, and anchor-only links
            if not href or href.startswith(('javascript:', '#', 'mailto:', 'tel:')):
                continue
                
            # Handle relative paths with and without leading slash
            if href.startswith('/'):
                # Absolute path within the same domain
                full_url = urljoin(f"https://{base_domain}", href)
            elif not href.startswith(('http://', 'https://')):
                # Relative path from current URL
                if base_path:
                    full_url = urljoin(f"https://{base_domain}{base_path}/", href)
                else:
                    full_url = urljoin(f"https://{base_domain}/", href)
            else:
                # Already absolute URL
                full_url = href
            
            parsed = urlparse(full_url)
            
            # Handle hash fragments - remove them but keep the base URL
            if '#' in full_url:
                # Only consider the part before the hash
                path_parts = parsed.path.split('#')[0]
                fragment = parsed.fragment
                
                # Reconstruct URL without fragment
                full_url = f"{parsed.scheme}://{parsed.netloc}{path_parts}"
                
                # If the fragment looks like a section ID and not just an anchor,
                # also add the full URL with fragment for specific content
                if fragment and not fragment.startswith(('top', 'content', 'main')):
                    fragment_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    if fragment_url not in links:
                        links.append(fragment_url)
            
            # Only include links from the same domain and with http(s) scheme
            # But also include specific external domains that might be relevant
            allowed_domains = [base_domain, 'docs.setu.co', 'setu.co']
            
            if ((parsed.netloc in allowed_domains or parsed.netloc == '') and 
                parsed.scheme in ['http', 'https'] and 
                not parsed.path.endswith(('.pdf', '.jpg', '.png', '.gif', '.xml', '.zip'))):
                # Normalize URL for deduplication
                normalized_url = full_url.rstrip('/')
                if normalized_url not in links:
                    links.append(normalized_url)
        
        # Special handling for Setu documentation structure
        # If current URL is a product page, also add common subpages
        if 'docs.setu.co/payments/' in base_url:
            # Extract product path (e.g., "umap" from ".../payments/umap/...")
            path_parts = urlparse(base_url).path.strip('/').split('/')
            if len(path_parts) >= 2:
                product_path = path_parts[1]  # e.g., "umap"
                
                # Add important related pages that might not be directly linked
                related_sections = [
                    'overview', 
                    'quickstart', 
                    'merchant-onboarding',  # Specifically add merchant-onboarding
                    'api-reference',
                    'faqs'
                ]
                
                for section in related_sections:
                    related_url = f"https://docs.setu.co/payments/{product_path}/{section}"
                    if related_url not in links:
                        links.append(related_url)
        
        return links

    def fetch_url_content(self, url: str, depth: int = 0, visited: Optional[Set[str]] = None) -> List[Document]:
        """Recursively fetch content from a URL and its links with improved handling"""
        if visited is None:
            visited = set()
        
        # Normalize URL for comparison
        normalized_url = url.rstrip('/')
        
        if normalized_url in visited:
            return []
        
        visited.add(normalized_url)
        documents = []
        url_hash = self.get_url_hash(normalized_url)
        
        try:
            logger.info(f"Fetching URL (depth {depth}): {normalized_url}")
            
            # Add more browser-like headers
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": "https://docs.setu.co/",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
            
            response = requests.get(normalized_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Get page title (fallback to URL path if not found)
            title = soup.title.string.strip() if soup.title else urlparse(normalized_url).path.split('/')[-1].replace('-', ' ').title()
            
            # Extract the main content
            content = self.clean_html(response.text)
            
            if content:
                # Extract path parts for better metadata
                url_parts = urlparse(normalized_url).path.strip('/').split('/')
                
                # Create document for current page with enhanced metadata
                doc = Document(
                    page_content=content,
                    metadata={
                        "url": normalized_url,
                        "url_hash": url_hash,
                        "domain": urlparse(normalized_url).netloc,
                        "path": urlparse(normalized_url).path,
                        "type": "url",
                        "depth": depth,
                        "fetched_at": datetime.now().isoformat(),
                        "title": title,
                        # Add section and subsection for better filtering
                        "section": url_parts[1] if len(url_parts) > 1 else "",
                        "subsection": url_parts[2] if len(url_parts) > 2 else "",
                        # For Setu docs, add structured path information
                        "is_setu_docs": "docs.setu.co" in normalized_url
                    }
                )
                
                # Log successful content extraction
                logger.info(f"Extracted content from {normalized_url} ({len(content)} chars)")
                documents.append(doc)
                
                # If not at max depth, process links
                if depth < self.max_depth:
                    links = self.extract_links(soup, normalized_url)
                    logger.info(f"Found {len(links)} links on {normalized_url}")
                    domain_url_count = 1  # Start with 1 for current URL
                    
                    for link in links:
                        if domain_url_count >= self.max_urls_per_domain:
                            logger.warning(f"Reached maximum URLs for domain: {urlparse(normalized_url).netloc}")
                            break
                            
                        # Recursively fetch content from links
                        child_docs = self.fetch_url_content(link, depth + 1, visited)
                        if child_docs:
                            documents.extend(child_docs)
                            domain_url_count += len(child_docs)
                
            else:
                logger.warning(f"No content extracted from {normalized_url}")
            
        except Exception as e:
            logger.error(f"Error fetching URL {normalized_url}: {e}")
        
        return documents

    def add_document_to_vectorstore(self, document: Document, product: str) -> int:
        """Add a single document to the vector store and return number of chunks created"""
        try:
            # Split document into chunks
            chunks = self.text_splitter.split_documents([document])
            
            if not chunks:
                logger.warning(f"No chunks created for document: {document.metadata.get('url', 'unknown')}")
                return 0
                
            # Get the vectorstore for this product
            vectorstore = self.get_vectorstore(product)
            
            # Add chunks to vectorstore
            vectorstore.add_documents(chunks)
            
            # Also add to the central VectorStore used by QA
            from services.vectorstore import VectorStore
            qa_vectorstore = VectorStore()
            
            # Ensure all chunks have the product metadata
            for chunk in chunks:
                if 'product' not in chunk.metadata:
                    chunk.metadata['product'] = product
            
            # Add to the QA vectorstore
            qa_vectorstore.add_documents(chunks, product)
            
            logger.info(f"Added {len(chunks)} chunks to vectorstore for product {product}")
            return len(chunks)
            
        except Exception as e:
            logger.error(f"Error adding document to vectorstore: {e}")
            return 0
            
    def detect_product_from_content(self, content: str) -> Optional[str]:
        """Detect the product from the content using keyword matching"""
        try:
            # Get all available products
            from services.product_service import product_service
            all_products = product_service.get_all_products()
            
            # Product keyword mappings - map keywords to products
            product_keywords = {
                # Banking products
                "ACCOUNT": ["account", "saving", "bank account", "account statement"],
                "PAYMENT": ["payment", "pay", "transfer", "transaction"],
                "FD": ["fixed deposit", "fd", "deposit"],
                
                # Payment products
                "UPI": ["upi", "unified payment", "upi payment", "upi transaction"],
                "UMAP": ["umap", "merchant", "merchant onboarding", "merchant payment"],
                "BILLPAY": ["bill", "bill payment", "utility bill", "recharge"],
                
                # Data products
                "ACCOUNT_AGGREGATOR": ["account aggregator", "aa", "data sharing", "consent", "fi data"],
                "SANDBOX": ["sandbox", "testing", "test mode", "test environment"],
                
                # Lending products
                "OCEN": ["ocen", "loan", "credit", "lending", "lender"],
                "SETTLEMENTS": ["settlement", "disburse", "disbursement", "neft", "imps", "rtgs"],
                "ESCROW": ["escrow", "trustee", "trusted"],
                
                # Common or other products
                "KYC": ["kyc", "know your customer", "onboard", "verification", "verify"]
            }
            
            # Count occurrences of keywords for each product
            product_scores = {product: 0 for product in all_products}
            
            # For each product's keywords, check if they exist in the content
            for product, keywords in product_keywords.items():
                if product in all_products:  # Only consider valid products
                    for keyword in keywords:
                        # Count occurrences (case-insensitive)
                        count = content.lower().count(keyword.lower())
                        product_scores[product] += count
            
            # Get the product with the highest score
            best_match = max(product_scores.items(), key=lambda x: x[1], default=(None, 0))
            
            # Return the product if score is above threshold
            if best_match[1] > 0:
                logger.info(f"Detected product {best_match[0]} with score {best_match[1]}")
                return best_match[0]
            
            # Fallback: try to find exact product names in the content
            for product in all_products:
                if product.lower() in content.lower():
                    logger.info(f"Detected product {product} by direct name match")
                    return product
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting product from content: {e}")
            return None

    def store_urls(self, urls: List[str], default_product: str = None) -> Dict:
        """Store URL content in ChromaDB with automatic product detection"""
        try:
            all_documents = []
            product_document_map = {}  # Maps products to their documents
            failed_urls = []
            processing_stats = {
                "total_urls": len(urls),
                "successful": 0,
                "failed": 0,
                "chunks_stored": 0,
                "pages_processed": 0,
                "products_detected": {}
            }
            
            # Process each starting URL
            for url in urls:
                try:
                    visited = set()
                    documents = self.fetch_url_content(url, visited=visited)
                    
                    if documents:
                        # Group documents by detected product
                        for doc in documents:
                            # Get content and detect product
                            content = doc.page_content
                            detected_product = self.detect_product_from_content(content)
                            
                            # Use detected product or fall back to default
                            product = detected_product or default_product or "UMAP"
                            
                            # Add product metadata
                            doc.metadata["product"] = product
                            doc.metadata["detected_product"] = detected_product  # Store the detected product separately
                            
                            # Initialize product in document map if needed
                            if product not in product_document_map:
                                product_document_map[product] = []
                                processing_stats["products_detected"][product] = 0
                            
                            # Add document to the product group
                            product_document_map[product].append(doc)
                            processing_stats["products_detected"][product] += 1
                        
                        all_documents.extend(documents)
                        processing_stats["successful"] += 1
                        processing_stats["pages_processed"] += len(documents)
                    else:
                        failed_urls.append({"url": url, "error": "No content found"})
                        processing_stats["failed"] += 1
                        
                except Exception as e:
                    logger.error(f"Error processing URL {url}: {e}")
                    failed_urls.append({"url": url, "error": str(e)})
                    processing_stats["failed"] += 1

            if not all_documents:
                return {
                    "success": False,
                    "error": "No documents to process",
                    "processing_stats": processing_stats,
                    "failed": failed_urls
                }

            # Get OpenAI API key for embeddings
            api_key = retrieve_secret("OPENAI_API_KEY")
            embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small",
                openai_api_key=api_key
            )
            
            # Process each product group
            total_chunks = 0
            
            for product, documents in product_document_map.items():
                # Skip if no documents for this product
                if not documents:
                    continue
                    
                logger.info(f"Processing {len(documents)} documents for product {product}")
                
                # Split documents into chunks
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000,
                    chunk_overlap=200
                )
                chunks = text_splitter.split_documents(documents)
                
                # Ensure all chunks have product information
                for chunk in chunks:
                    if "product" not in chunk.metadata:
                        chunk.metadata["product"] = product
                
                # Store chunks in the main product directory
                main_vectorstore = Chroma(
                    persist_directory=os.path.join(self.chroma_dir, product),
                    embedding_function=embeddings
                )
                
                # Also store in the product_urls directory for backup/separate access
                url_vectorstore = Chroma(
                    persist_directory=os.path.join(self.chroma_dir, f"{product}_urls"),
                    embedding_function=embeddings
                )

                # Add documents to both vector stores
                logger.info(f"Adding {len(chunks)} URL chunks to main vectorstore for product '{product}'")
                main_vectorstore.add_documents(chunks)
                
                logger.info(f"Adding {len(chunks)} URL chunks to URL-specific vectorstore")
                url_vectorstore.add_documents(chunks)
                
                total_chunks += len(chunks)
            
            # Update statistics
            processing_stats["chunks_stored"] = total_chunks
            
            return {
                "success": True,
                "processing_stats": processing_stats,
                "failed": failed_urls,
                "details": {
                    "products_detected": processing_stats["products_detected"],
                    "pages_processed": processing_stats["pages_processed"],
                    "chunks_stored": processing_stats["chunks_stored"]
                }
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error storing URLs: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "processing_stats": processing_stats,
                "failed": failed_urls
            }

# Create global instance
url_store = URLDocStore() 