from typing import Optional
from langchain.memory import ConversationBufferMemory
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = BASE_DIR / "chroma_db"

# Create necessary directories
DATA_DIR.mkdir(exist_ok=True)
CHROMA_DIR.mkdir(exist_ok=True)

# File paths
DB_PATH = str(DATA_DIR / "secrets.db")
KEY_PATH = str(DATA_DIR / "secret.key")

# OpenAI Configuration
OPENAI_API_KEY: Optional[str] = None
OPENAI_MODEL = "gpt-4-turbo-preview"
OPENAI_TEMPERATURE = 0

# Ensure the Confluence configuration is set correctly
CONFLUENCE_CONFIG = {}

# Initialize PRODUCT_DOCS with default values
PRODUCT_DOCS = {
    "AA": [],
    "BOU": [],
    "COU": [],
    "UMAP": [],
    "Collect": [],
    "Bridge": [],
    "KYC": [],
    "Esign": []
}

# Initialize the vectorstore to None
VECTORSTORE = None

# Set up memory for conversation history using the new format
MEMORY = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True,
    output_key="answer"
)