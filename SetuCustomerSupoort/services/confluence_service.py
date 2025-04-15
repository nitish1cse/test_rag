from typing import List, Optional, Dict
from atlassian import Confluence
from bs4 import BeautifulSoup
import logging
from services.secret_store import retrieve_secret
from chromadb import PersistentClient, Collection
import os
import re
import traceback
from urllib.parse import urljoin
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

# Set up detailed logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConfluenceDocStore:
    def __init__(self):
        self.chroma_dir = "chroma_db"
        os.makedirs(self.chroma_dir, exist_ok=True)
        
        # Get OpenAI API key from secret store
        api_key = retrieve_secret("OPENAI_API_KEY")
        if not api_key:
            logger.error("OpenAI API key not configured")
            raise ValueError("OpenAI API key not configured. Please configure it using /openai/api-key endpoint")
        
        # Initialize ChromaDB client
        self.client = PersistentClient(path=self.chroma_dir)
        
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=api_key
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        logger.info(f"Initialized ChromaDB at {self.chroma_dir}")

    def normalize_collection_name(self, name: str) -> str:
        """Normalize collection name to meet ChromaDB requirements"""
        # Convert to lowercase and replace invalid characters
        normalized = re.sub(r'[^a-zA-Z0-9._-]', '_', name)
        
        # Ensure it starts with a letter or number
        if not normalized[0].isalnum():
            normalized = f"collection_{normalized}"
            
        # Ensure minimum length
        if len(normalized) < 3:
            normalized = f"collection_{normalized}"
            
        # Ensure it ends with alphanumeric
        if not normalized[-1].isalnum():
            normalized = f"{normalized}_collection"
            
        # Truncate if too long (keeping the maximum at 63 characters)
        if len(normalized) > 63:
            normalized = normalized[:63]
            # Ensure it still ends with alphanumeric
            if not normalized[-1].isalnum():
                normalized = normalized[:-1] + "x"
                
        return normalized

    def get_or_create_collection(self, product: str) -> Collection:
        """Get or create a collection for a product"""
        collection_name = self.normalize_collection_name(product)
        logger.info(f"Using collection name: {collection_name} for product: {product}")
        return self.client.get_or_create_collection(name=collection_name)

    def clean_html(self, html_content: str) -> str:
        """Clean HTML content and extract text"""
        if not html_content:
            return ""
        soup = BeautifulSoup(html_content, 'html.parser')
        return soup.get_text(separator="\n", strip=True)

    def get_page_url(self, base_url: str, page: Dict) -> str:
        """Safely construct page URL from page data"""
        try:
            if 'space' in page and 'key' in page['space']:
                return f"{base_url}/wiki/spaces/{page['space']['key']}/pages/{page['id']}"
            elif '_links' in page and 'webui' in page['_links']:
                return urljoin(base_url, page['_links']['webui'])
            else:
                return f"{base_url}/wiki/pages/{page['id']}"
        except Exception:
            return f"{base_url}/wiki/pages/{page.get('id', 'unknown')}"

    def fetch_confluence_page_and_children(self, confluence: Confluence, page_id: str, depth: int = 0) -> List[Document]:
        """Fetch a Confluence page and all its children recursively"""
        try:
            page_content = []
            logger.info(f"Fetching page {page_id} at depth {depth}")
            
            # Fetch main page with expanded content
            try:
                main_page = confluence.get_page_by_id(
                    page_id, 
                    expand='body.storage,version,space,ancestors,children.page,descendants.page'
                )
                if not main_page:
                    logger.error(f"Page not found: {page_id}")
                    return []
                
                logger.debug(f"Retrieved page data: {main_page.keys()}")
            except Exception as e:
                logger.error(f"Error fetching page {page_id}: {e}")
                return []

            # Process main page
            try:
                title = main_page.get('title', f"Document {page_id}")
                body = main_page.get('body', {})
                storage = body.get('storage', {}) if isinstance(body, dict) else {}
                content = self.clean_html(storage.get('value', '')) if isinstance(storage, dict) else ''
                
                if not content:
                    logger.warning(f"Empty content for page {page_id} ({title})")
                else:
                    # Get ancestors for breadcrumb
                    ancestors = main_page.get('ancestors', [])
                    breadcrumb = " > ".join([a.get('title', '') for a in ancestors if isinstance(a, dict)])
                    
                    space_data = main_page.get('space', {})
                    space_key = space_data.get('key', '') if isinstance(space_data, dict) else ''
                    
                    version_data = main_page.get('version', {})
                    version_number = version_data.get('number', '1') if isinstance(version_data, dict) else '1'
                    last_modified = version_data.get('when', '') if isinstance(version_data, dict) else ''
                    
                    page_content.append(Document(
                        page_content=content,
                        metadata={
                            "title": title,
                            "source": "confluence",
                            "page_id": page_id,
                            "type": "main_page" if depth == 0 else "child_page",
                            "depth": depth,
                            "breadcrumb": breadcrumb,
                            "space_key": space_key,
                            "version": version_number,
                            "last_modified": last_modified,
                        }
                    ))
                    logger.info(f"Processed page: {title} ({page_id})")
            except Exception as e:
                logger.error(f"Error processing main page content {page_id}: {e}")

            # Process child pages
            try:
                # Get children from expanded data
                children = (
                    main_page.get('children', {}).get('page', {}).get('results', [])
                    if isinstance(main_page.get('children', {}), dict)
                    else []
                )
                
                logger.info(f"Found {len(children)} children for page {page_id}")
                
                for child in children:
                    if not isinstance(child, dict):
                        continue
                        
                    child_id = child.get('id')
                    if not child_id:
                        continue
                    
                    child_content = self.fetch_confluence_page_and_children(
                        confluence=confluence,
                        page_id=child_id,
                        depth=depth + 1
                    )
                    page_content.extend(child_content)

            except Exception as e:
                logger.error(f"Error processing children for page {page_id}: {e}")

            # Process attachments
            try:
                attachments = confluence.get_attachments_from_page(page_id)
                for attachment in attachments:
                    if not isinstance(attachment, dict):
                        continue
                        
                    if attachment.get('mediaType', '').startswith('text/'):
                        try:
                            attachment_content = confluence.get_attachment_content(page_id, attachment['id'])
                            if attachment_content:
                                page_content.append(Document(
                                    page_content=attachment_content.decode('utf-8'),
                                    metadata={
                                        "title": f"{title} - {attachment.get('title', 'Attachment')}",
                                        "source": "confluence_attachment",
                                        "page_id": page_id,
                                        "attachment_id": attachment.get('id'),
                                        "type": "attachment",
                                        "depth": depth,
                                        "media_type": attachment.get('mediaType'),
                                        "parent_title": title
                                    }
                                ))
                                logger.info(f"Processed attachment: {attachment.get('title')} for page {page_id}")
                        except Exception as e:
                            logger.warning(f"Error processing attachment {attachment.get('id')} for page {page_id}: {e}")
                            
            except Exception as e:
                logger.warning(f"Error fetching attachments for page {page_id}: {e}")

            if not page_content:
                logger.warning(f"No content found for page {page_id} and its children")
                
            return page_content

        except Exception as e:
            logger.error(f"Error in fetch_confluence_page_and_children for {page_id}: {e}")
            logger.debug(f"Full traceback: {traceback.format_exc()}")
            return []

    def get_vectorstore(self, product: str) -> Optional[Chroma]:
        """Get vector store for a product"""
        try:
            store_path = os.path.join(self.chroma_dir, product)
            if not os.path.exists(store_path):
                return None
            
            return Chroma(
                persist_directory=store_path,
                embedding_function=self.embeddings
            )
        except Exception as e:
            logger.error(f"Error getting vector store for {product}: {e}")
            return None

    def get_document_metadata(self, product: str, page_id: str) -> Optional[Dict]:
        """Get stored metadata for a document"""
        try:
            vectorstore = self.get_vectorstore(product)
            if not vectorstore:
                return None
            
            collection = vectorstore._collection
            results = collection.get(
                where={"page_id": page_id},
                include=["metadatas"]
            )
            
            if results and results["metadatas"]:
                return results["metadatas"][0]
            return None
        except Exception as e:
            logger.error(f"Error getting document metadata: {e}")
            return None

    def has_document_changed(self, product: str, page_id: str, new_version: str, new_content: str) -> bool:
        """Check if document has changed"""
        stored_metadata = self.get_document_metadata(product, page_id)
        if not stored_metadata:
            return True  # Document doesn't exist, so it has "changed"
        
        if stored_metadata.get("version") != new_version:
            logger.info(f"Document {page_id} version changed from {stored_metadata.get('version')} to {new_version}")
            return True
        
        return False

    def store_confluence_docs(self, product: str, document_ids: List[str]) -> Dict:
        """Store Confluence documents in ChromaDB"""
        try:
            # Get Confluence credentials
            url = retrieve_secret("CONFLUENCE_URL")
            username = retrieve_secret("CONFLUENCE_USERNAME")
            api_token = retrieve_secret("CONFLUENCE_API_TOKEN")

            if not all([url, username, api_token]):
                logger.error("Missing Confluence credentials")
                return {
                    "success": False,
                    "error": "Missing credentials",
                    "total_requested": len(document_ids),
                    "processing_stats": {
                        "main_pages": 0,
                        "child_pages": 0,
                        "attachments": 0,
                        "total_processed": 0,
                        "unchanged": 0,
                        "updated": 0
                    },
                    "chunks_stored": 0,
                    "failed": []
                }

            # Initialize Confluence client
            confluence = Confluence(
                url=url,
                username=username,
                password=api_token,
                cloud=True
            )

            # Fetch and process documents
            documents = []
            failed_docs = []
            processing_stats = {
                "main_pages": 0,
                "child_pages": 0,
                "attachments": 0,
                "total_processed": 0,
                "unchanged": 0,
                "updated": 0
            }
            
            for doc_id in document_ids:
                try:
                    logger.info(f"Processing document tree for ID: {doc_id}")
                    
                    # First fetch the main page to check version
                    main_page = confluence.get_page_by_id(
                        doc_id,
                        expand='version'
                    )
                    
                    if not main_page:
                        failed_docs.append({"id": doc_id, "error": "Page not found"})
                        continue
                    
                    new_version = str(main_page.get('version', {}).get('number', '1'))
                    
                    # Check if document has changed
                    if not self.has_document_changed(product, doc_id, new_version, ""):
                        logger.info(f"Document {doc_id} unchanged, skipping")
                        processing_stats["unchanged"] += 1
                        continue
                    
                    # If changed, fetch full content
                    page_docs = self.fetch_confluence_page_and_children(confluence, doc_id)
                    
                    if page_docs:
                        # Update statistics
                        for doc in page_docs:
                            doc_type = doc.metadata.get("type", "unknown")
                            if doc_type == "main_page":
                                processing_stats["main_pages"] += 1
                            elif doc_type == "child_page":
                                processing_stats["child_pages"] += 1
                            elif doc_type == "attachment":
                                processing_stats["attachments"] += 1
                            processing_stats["total_processed"] += 1
                        
                        processing_stats["updated"] += 1
                        documents.extend(page_docs)
                        logger.info(f"Successfully processed document tree {doc_id} with {len(page_docs)} total documents")
                    else:
                        failed_docs.append({"id": doc_id, "error": "No content found"})
                        logger.warning(f"No content found for document tree {doc_id}")
                except Exception as e:
                    logger.error(f"Error processing document {doc_id}: {e}")
                    failed_docs.append({"id": doc_id, "error": str(e)})

            if not documents:
                return {
                    "success": True if processing_stats["unchanged"] > 0 else False,
                    "message": "No new or updated documents to process" if processing_stats["unchanged"] > 0 else "No documents to process",
                    "total_requested": len(document_ids),
                    "processing_stats": processing_stats,
                    "chunks_stored": 0,
                    "failed": failed_docs
                }

            # Split documents into chunks
            chunks = self.text_splitter.split_documents(documents)
            
            # Create or get the vector store
            vectorstore = Chroma(
                persist_directory=os.path.join(self.chroma_dir, product),
                embedding_function=self.embeddings
            )

            # Remove old versions of updated documents
            collection = vectorstore._collection
            for doc in documents:
                page_id = doc.metadata.get("page_id")
                if page_id:
                    collection.delete(where={"page_id": page_id})

            # Add new documents to the vector store
            vectorstore.add_documents(chunks)
            
            # Get statistics
            count = collection.count()
            
            logger.info(f"Successfully stored {count} chunks from {len(documents)} documents")

            return {
                "success": True,
                "total_requested": len(document_ids),
                "processing_stats": processing_stats,
                "chunks_stored": count,
                "failed": failed_docs
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error storing documents: {error_msg}")
            logger.debug(f"Full traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "error": error_msg,
                "total_requested": len(document_ids),
                "processing_stats": {
                    "main_pages": 0,
                    "child_pages": 0,
                    "attachments": 0,
                    "total_processed": 0,
                    "unchanged": 0,
                    "updated": 0
                },
                "chunks_stored": 0,
                "failed": [{"id": "all", "error": error_msg}]
            }

# Create global instance
doc_store = ConfluenceDocStore()

def fetch_and_store_documents(product: str, document_ids: List[str]) -> Dict:
    """Fetch and store Confluence documents"""
    return doc_store.store_confluence_docs(product, document_ids)
