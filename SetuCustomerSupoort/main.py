from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import openai, qa, confluence
from datetime import datetime

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(openai.router)
app.include_router(qa.router)
app.include_router(confluence.router)

@app.get("/")
async def root():
    return {
        "message": "Setu Documentation Assistant API",
        "version": "1.0.0",
        "openai_configured": bool(config.OPENAI_API_KEY)
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "openai_key_configured": bool(config.OPENAI_API_KEY),
        "database_initialized": True
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
