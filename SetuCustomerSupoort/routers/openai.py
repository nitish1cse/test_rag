from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.secret_store import store_secret, retrieve_secret
import logging

router = APIRouter(prefix="/openai", tags=["OpenAI"])
logger = logging.getLogger(__name__)

class OpenAIConfig(BaseModel):
    api_key: str

@router.post("/api-key")
async def set_openai_api_key(config: OpenAIConfig):
    """Configure OpenAI API key"""
    try:
        if not store_secret("OPENAI_API_KEY", config.api_key):
            raise HTTPException(
                status_code=500,
                detail="Failed to store OpenAI API key"
            )
        return {"message": "OpenAI API key configured successfully"}
    except Exception as e:
        logger.error(f"Error configuring OpenAI API key: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api-key/status")
async def check_api_key_status():
    """Check if OpenAI API key is configured"""
    api_key = retrieve_secret("OPENAI_API_KEY")
    return {
        "configured": bool(api_key),
        "status": "API key is configured" if api_key else "API key is not configured"
    }
