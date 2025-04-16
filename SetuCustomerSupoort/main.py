from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import openai, qa, confluence, url, config
from datetime import datetime
import config as app_config
from services.secret_store import retrieve_secret

app = FastAPI()

# Update CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React app URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(openai.router)
app.include_router(qa.router)
app.include_router(confluence.router)
app.include_router(url.router)
app.include_router(config.router)

@app.get("/")
async def root():
    """Root endpoint with system status"""
    try:
        openai_key = retrieve_secret("openai_api_key")
        confluence_config = app_config.CONFLUENCE_CONFIG
        return {
            "status": "running",
            "timestamp": datetime.now().isoformat(),
            "openai_configured": bool(openai_key),
            "confluence_configured": bool(confluence_config),
            "vectorstore_initialized": bool(app_config.VECTORSTORE),
            "products": list(app_config.PRODUCT_DOCS.keys())
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "openai_key_configured": bool(app_config.OPENAI_API_KEY),
        "database_initialized": True
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
