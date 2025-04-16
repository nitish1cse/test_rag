from typing import Optional, List, Dict
from langchain_core.memory import BaseMemory
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from pydantic import BaseModel, Field
from pathlib import Path
import os
import json

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

# Ensure the Confluence configuration is set correctly
CONFLUENCE_CONFIG = {}

# Product information storage
PRODUCT_DOCS = {}

# Function to load product docs
def load_product_docs():
    global PRODUCT_DOCS
    try:
        if os.path.exists('product_docs.json'):
            with open('product_docs.json', 'r') as f:
                PRODUCT_DOCS = json.load(f)
        else:
            # Create empty file if it doesn't exist
            PRODUCT_DOCS = {}
            with open('product_docs.json', 'w') as f:
                json.dump(PRODUCT_DOCS, f)
    except Exception as e:
        print(f"Error loading product docs: {e}")
        PRODUCT_DOCS = {}

# Load products on startup
load_product_docs()

# Initialize the vectorstore to None
VECTORSTORE = None

# Custom chat history implementation
class CustomChatHistory(BaseModel):
    messages: List[BaseMessage] = Field(default_factory=list)

    def add_user_message(self, message: str) -> None:
        self.messages.append(HumanMessage(content=message))

    def add_ai_message(self, message: str) -> None:
        self.messages.append(AIMessage(content=message))

    def clear(self) -> None:
        self.messages = []

# Update memory configuration to use the latest format
class CustomConversationMemory(BaseMemory, BaseModel):
    chat_history: CustomChatHistory = Field(default_factory=CustomChatHistory)
    input_key: str = Field(default="input")
    output_key: str = Field(default="output")
    return_messages: bool = Field(default=True)

    @property
    def memory_variables(self) -> List[str]:
        return ["chat_history"]

    def load_memory_variables(self, inputs: Dict) -> Dict:
        """Load memory variables for the conversation."""
        return {
            "chat_history": self.chat_history.messages
        }

    def save_context(self, inputs: Dict, outputs: Dict) -> None:
        """Save context from this conversation to memory."""
        if self.input_key in inputs:
            self.chat_history.add_user_message(inputs[self.input_key])
        if self.output_key in outputs:
            self.chat_history.add_ai_message(outputs[self.output_key])

    def clear(self) -> None:
        """Clear memory contents."""
        self.chat_history.clear()

# Initialize the custom memory
MEMORY = CustomConversationMemory()