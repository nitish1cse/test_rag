from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict
import config as app_config
import os
import json
from services.product_service import product_service
import logging

router = APIRouter(prefix="/config", tags=["Configuration"])
logger = logging.getLogger(__name__)

@router.get("/products")
async def get_products() -> List[str]:
    """Get a list of all available products"""
    try:
        # First try to get from product_service
        products = product_service.get_all_products()
        
        if not products:
            # Fallback to direct config
            products = list(app_config.PRODUCT_DOCS.keys())
            
            # If still empty, add default products
            if not products:
                default_products = ["AA", "BOU", "COU", "UMAP", "Collect", "Bridge", "DG"]
                logger.info(f"No products found, adding default products: {default_products}")
                
                # Update product_docs.json
                updated_product_docs = {product: [] for product in default_products}
                try:
                    with open('product_docs.json', 'w') as f:
                        json.dump(updated_product_docs, f)
                    # Update in-memory config
                    app_config.PRODUCT_DOCS = updated_product_docs
                    products = default_products
                except Exception as e:
                    logger.error(f"Error writing default products: {e}")
                    raise HTTPException(status_code=500, detail=f"Error initializing products: {str(e)}")
        
        return products
        
    except Exception as e:
        logger.error(f"Error retrieving products: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/products/{product}")
async def add_product(product: str) -> Dict:
    """Add a new product to the system"""
    try:
        if product in app_config.PRODUCT_DOCS:
            return {"message": f"Product '{product}' already exists"}
            
        # Add to PRODUCT_DOCS
        app_config.PRODUCT_DOCS[product] = []
        
        # Update product_docs.json
        try:
            with open('product_docs.json', 'w') as f:
                json.dump(app_config.PRODUCT_DOCS, f)
        except Exception as e:
            logger.error(f"Error writing product_docs.json: {e}")
            raise HTTPException(status_code=500, detail=f"Error saving product: {str(e)}")
            
        # Create product directory in chroma_db if it doesn't exist
        os.makedirs(os.path.join("chroma_db", product), exist_ok=True)
            
        return {"message": f"Product '{product}' added successfully"}
        
    except Exception as e:
        logger.error(f"Error adding product: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 