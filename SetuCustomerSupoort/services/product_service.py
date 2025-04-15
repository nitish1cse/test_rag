import json
from typing import List, Dict
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class ProductService:
    def __init__(self):
        self.config_dir = Path("config")
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / "product_docs.json"
        self.product_docs = self._load_product_docs()

    def _load_product_docs(self) -> Dict[str, List[str]]:
        """Load product docs configuration"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            else:
                # Initialize with default structure
                default_config = {
                    "AA": [],
                    "BOU": [],
                    "COU": [],
                    "UMAP": [],
                    "Collect": [],
                    "Bridge": [],
                    "KYC": [],
                    "Esign": []
                }
                self._save_product_docs(default_config)
                return default_config
        except Exception as e:
            logger.error(f"Error loading product docs: {e}")
            return {}

    def _save_product_docs(self, config: Dict[str, List[str]]) -> bool:
        """Save product docs configuration"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Error saving product docs: {e}")
            return False

    def get_product_docs(self, product: str) -> List[str]:
        """Get document IDs for a product"""
        return self.product_docs.get(product, [])

    def get_all_products(self) -> List[str]:
        """Get list of all products"""
        return list(self.product_docs.keys())

    def update_product_docs(self, product: str, doc_ids: List[str]) -> bool:
        """Update document IDs for a product"""
        try:
            self.product_docs[product] = doc_ids
            return self._save_product_docs(self.product_docs)
        except Exception as e:
            logger.error(f"Error updating product docs: {e}")
            return False

    def verify_product_docs(self) -> bool:
        """Verify product docs file exists and is readable"""
        try:
            if not self.config_file.exists():
                logger.error("Product docs file does not exist")
                return False
            
            with open(self.config_file, 'r') as f:
                content = json.load(f)
                if not isinstance(content, dict):
                    logger.error("Product docs file is not a valid JSON object")
                    return False
                
                # Verify all products exist
                expected_products = {"AA", "BOU", "COU", "UMAP", "Collect", "Bridge", "KYC", "Esign"}
                if not all(product in content for product in expected_products):
                    logger.error("Product docs file is missing some products")
                    return False
                
                # Verify all values are lists
                if not all(isinstance(docs, list) for docs in content.values()):
                    logger.error("Product docs file contains invalid document lists")
                    return False
                
            return True
        except Exception as e:
            logger.error(f"Error verifying product docs: {e}")
            return False

    def add_product_docs(self, product: str, doc_ids: List[str]) -> bool:
        """Add document IDs to a product"""
        try:
            if not self.verify_product_docs():
                logger.warning("Product docs verification failed, attempting to reload")
                self.product_docs = self._load_product_docs()
            
            current_docs = set(self.product_docs.get(product, []))
            current_docs.update(doc_ids)
            self.product_docs[product] = sorted(list(current_docs))  # Sort for consistency
            
            success = self._save_product_docs(self.product_docs)
            if success:
                logger.info(f"Successfully updated {product} with {len(doc_ids)} documents")
            else:
                logger.error(f"Failed to save product docs for {product}")
            return success
        except Exception as e:
            logger.error(f"Error adding product docs: {e}")
            return False

    def remove_product_docs(self, product: str, doc_ids: List[str]) -> bool:
        """Remove document IDs from a product"""
        try:
            current_docs = set(self.product_docs.get(product, []))
            current_docs.difference_update(doc_ids)
            self.product_docs[product] = list(current_docs)
            return self._save_product_docs(self.product_docs)
        except Exception as e:
            logger.error(f"Error removing product docs: {e}")
            return False

# Create global instance
product_service = ProductService() 