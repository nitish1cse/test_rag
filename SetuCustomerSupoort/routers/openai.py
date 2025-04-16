from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.secret_store import store_secret, retrieve_secret
from openai import OpenAI

router = APIRouter(prefix="/openai", tags=["openai"])

class APIKeyRequest(BaseModel):
    api_key: str

@router.get("/api-key")
async def get_api_key() -> dict:
    """Get OpenAI API key status"""
    try:
        api_key = retrieve_secret("openai_api_key")
        if not api_key:
            return {"status": "not_configured", "message": "API key not found"}
        
        # Test the key
        client = OpenAI(api_key=api_key)
        try:
            client.models.list()
            return {"status": "configured", "message": "API key is valid"}
        except Exception as e:
            return {"status": "invalid", "message": f"API key is invalid: {str(e)}"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/api-key")
async def set_api_key(request: APIKeyRequest) -> dict:
    """Store OpenAI API key"""
    try:
        # Validate the API key
        client = OpenAI(api_key=request.api_key)
        try:
            client.models.list()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid API key: {str(e)}")
        
        # Store the key
        store_secret("openai_api_key", request.api_key)
        return {"status": "success", "message": "API key stored successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
