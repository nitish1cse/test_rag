import clear
import gradio as gr
import json
import requests
import os
from typing import Dict, List, Any, Optional
import pandas as pd
from datetime import datetime
from openai import OpenAI
from services.secret_store import retrieve_secret, store_secret  # Import the secret retrieval and storage functions
import time
from pathlib import Path
import config  # Add this import

# Disable all external connections and analytics
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
os.environ["GRADIO_TELEMETRY_ENABLED"] = "False"
os.environ["GRADIO_USE_CACHE"] = "False"
os.environ["GRADIO_TEMP_DIR"] = "./gradio_temp"

# Configure Gradio to serve local files
GRADIO_STATIC = os.path.join(os.path.dirname(__file__), "setu-docs-frontend/src/static")
os.makedirs(GRADIO_STATIC, exist_ok=True)

# Load product configuration
def load_products() -> List[str]:
    try:
        with open('config/product_docs.json', 'r') as f:
            products = json.load(f)
            return list(products.keys())
    except Exception as e:
        print(f"Error loading products: {e}")
        return []

# API Configuration
API_BASE_URL = "http://localhost:8000"

# Replace the OpenAI client initialization
def get_openai_client() -> Optional[OpenAI]:
    """Get OpenAI client with API key from secure storage"""
    try:
        # First try to get from secure storage
        api_key = retrieve_secret("openai_api_key")
        if api_key:
            return OpenAI(api_key=api_key)
        
        # Try FastAPI backend as fallback
        response = requests.get(f"{API_BASE_URL}/openai/api-key")
        if response.status_code == 200:
            api_key = response.json().get("api_key")
            if api_key:
                return OpenAI(api_key=api_key)
        
        # Try local config as last resort
        api_key = config_manager.get_config_value("openai_api_key")
        if api_key:
            return OpenAI(api_key=api_key)
            
        print("Warning: OpenAI API key not found in any storage")
        return None
    except Exception as e:
        print(f"Error initializing OpenAI client: {e}")
        return None

# System message for the bot
SYSTEM_MESSAGE = """You are an AI assistant helping with Setu's documentation. 
Your role is to provide accurate, clear answers based on the available documentation.
Always be professional and concise in your responses."""

class ConfigManager:
    def __init__(self):
        self.config_file = "config/app_config.json"
        self.load_config()

    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            else:
                self.config = {
                    "openai_api_key": "",
                    "confluence_url": "",
                    "confluence_username": "",
                    "confluence_api_token": ""
                }
                self.save_config()
        except Exception as e:
            print(f"Error loading config: {e}")
            self.config = {
                "openai_api_key": "",
                "confluence_url": "",
                "confluence_username": "",
                "confluence_api_token": ""
            }

    def save_config(self):
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def update_config(self, key: str, value: str) -> str:
        try:
            self.config[key] = value
            self.save_config()
            return f"✅ Updated {key}"
        except Exception as e:
            return f"❌ Error updating {key}: {e}"

    def get_config_value(self, key: str, default: str = "") -> str:
        """Get config value with fallback"""
        return self.config.get(key, default)

config_manager = ConfigManager()

# Remove the global client initialization
# Instead of: client = OpenAI()
client = None  # Will be initialized when needed

# Update the configure_api_key function to store in secure storage
def configure_api_key(api_key: str) -> str:
    """Configure OpenAI API key in secure storage and local config"""
    try:
        if not api_key:
            return "❌ Error: API key cannot be empty"
            
        # Test the API key first
        test_client = OpenAI(api_key=api_key)
        try:
            test_client.models.list()
        except Exception as e:
            return f"❌ Invalid API key: {str(e)}"
        
        # Store in secure storage
        store_secret("openai_api_key", api_key)
        
        # Store in FastAPI backend
        response = requests.post(
            f"{API_BASE_URL}/openai/api-key",
            json={"api_key": api_key}
        )
        
        if response.status_code != 200:
            return f"⚠️ Warning: Failed to store in backend: {response.json().get('detail', 'Unknown error')}"
        
        # Update local config
        config_manager.update_config("openai_api_key", api_key)
        
        # Update the client for the current session
        global client
        client = OpenAI(api_key=api_key)
        
        return "✅ OpenAI API key configured successfully"
    except Exception as e:
        return f"❌ Error: {str(e)}"

def configure_confluence(url: str, username: str, api_token: str) -> str:
    try:
        response = requests.post(
            f"{API_BASE_URL}/confluence/config",
            json={
                "url": url,
                "username": username,
                "api_token": api_token
            }
        )
        if response.status_code == 200:
            config_manager.update_config("confluence_url", url)
            config_manager.update_config("confluence_username", username)
            config_manager.update_config("confluence_api_token", api_token)
            return "Confluence configured successfully"
        return f"Error: {response.json()['detail']}"
    except Exception as e:
        return f"Error: {str(e)}"

def get_doc_context(product: str, question: str) -> str:
    """Get relevant document context for the question"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/qa/context",
            json={"product": product, "question": question},
            timeout=10
        )
        if response.ok:
            return response.json().get("context", "")
        return ""
    except Exception as e:
        print(f"Error getting context: {e}")
        return ""

def chat_with_docs(
    message: str,
    history: List[Dict[str, str]],
    product: str,
    status_box: gr.Textbox
) -> tuple[str, List[Dict[str, str]], str]:
    """Enhanced chat with documentation using OpenAI chat completion"""
    if not message.strip():
        return "", history, "Please enter a message"
    
    try:
        status_box.update(value="Loading...")  # Update status
        
        # Get OpenAI client
        client = get_openai_client()
        if not client:
            return "", history, "⚠️ OpenAI API key not configured. Please configure it in the Configuration tab."
        
        # Validate product selection
        if not product:
            return "", history, "⚠️ Please select a product first"
        
        # Get document context
        context = get_doc_context(product, message)
        
        # Prepare messages for OpenAI
        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "system", "content": f"Current product context: {product}"},
        ]
        
        if context:
            messages.append({
                "role": "system", 
                "content": f"Relevant documentation context: {context}"
            })

        # Add conversation history
        for msg in history:
            messages.append({
                "role": "user" if msg["role"] == "user" else "assistant",
                "content": msg["content"]
            })
        
        # Add current message
        messages.append({"role": "user", "content": message})

        # Get response from OpenAI
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )

        # Extract answer
        answer = response.choices[0].message.content
        
        # Update history with new message format
        new_history = history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": answer}
        ]
        
        status_box.update(value="Ready")  # Update status
        return "", new_history, "✅ Ready for next question"
            
    except Exception as e:
        status_box.update(value="Error")  # Update status
        error_msg = f"Error: {str(e)}"
        print(error_msg)  # For debugging
        return "", history, f"⚠️ {error_msg}"

def get_config_status() -> pd.DataFrame:
    """Get current configuration status with detailed checks"""
    status_data = []
    
    # Check OpenAI API key
    client = get_openai_client()
    openai_status = "✅ Configured" if client else "❌ Not Configured"
    
    status_data.append({
        "Component": "OpenAI API Key",
        "Status": openai_status,
        "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # Add other components
    for component, key in [
        ("Confluence URL", "confluence_url"),
        ("Confluence Username", "confluence_username"),
        ("Confluence API Token", "confluence_api_token")
    ]:
        value = config_manager.get_config_value(key)
        status = "✅ Configured" if value else "❌ Not Configured"
        status_data.append({
            "Component": component,
            "Status": status,
            "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return pd.DataFrame(status_data)

def get_document_stats(product: str) -> pd.DataFrame:
    """Get document statistics for a product"""
    try:
        response = requests.get(f"{API_BASE_URL}/confluence/documents/{product}")
        if response.status_code == 200:
            data = response.json()
            return pd.DataFrame([{
                "Product": product,
                "Document Count": data["document_count"],
                "Status": data["status"]
            }])
    except Exception as e:
        print(f"Error getting stats: {e}")
    return pd.DataFrame()

def store_confluence_docs(product: str, doc_ids: str) -> str:
    """Store Confluence documents"""
    try:
        doc_ids = [id.strip() for id in doc_ids.split(",")]
        response = requests.post(
            f"{API_BASE_URL}/confluence/documents",
            json={"product": product, "document_ids": doc_ids}
        )
        return response.json().get("message", "Error storing documents")
    except Exception as e:
        return f"Error: {str(e)}"

def store_urls(product: str, urls: str) -> str:
    """Store URLs"""
    try:
        urls = [url.strip() for url in urls.split(",")]
        response = requests.post(
            f"{API_BASE_URL}/url/store",
            json={"product": product, "urls": urls}
        )
        return response.json().get("message", "Error storing URLs")
    except Exception as e:
        return f"Error: {str(e)}"

def validate_product_selection(product: str) -> str:
    """Validate if the selected product has documents"""
    try:
        if not product:
            return "⚠️ Please select a product"
            
        response = requests.get(
            f"{API_BASE_URL}/confluence/documents/{product}",
            timeout=5  # Add timeout
        )
        
        if response.status_code == 200:
            data = response.json()
            if data["document_count"] == 0:
                return "⚠️ Warning: No documents found for this product. Please add documents first."
            return f"✅ {data['document_count']} documents available for {product}"
        elif response.status_code == 404:
            return "⚠️ Product not found in the system"
        else:
            return f"⚠️ Error checking documents: {response.status_code}"
    except requests.exceptions.ConnectionError:
        return "⚠️ Cannot connect to the server. Is it running?"
    except requests.exceptions.Timeout:
        return "⚠️ Server request timed out"
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# Add this function to get product document counts
def get_all_product_stats() -> pd.DataFrame:
    """Get document statistics for all products"""
    try:
        products = load_products()
        stats_data = []
        for product in products:
            response = requests.get(f"{API_BASE_URL}/confluence/documents/{product}")
            if response.status_code == 200:
                data = response.json()
                stats_data.append({
                    "Product": product,
                    "Document Count": data["document_count"],
                    "Status": data["status"]
                })
        return pd.DataFrame(stats_data)
    except Exception as e:
        print(f"Error getting stats: {e}")
        return pd.DataFrame()

def check_server_status() -> str:
    """Check if the FastAPI server is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/")
        if response.status_code == 200:
            return "✅ Server is running"
        return f"⚠️ Server returned status {response.status_code}"
    except requests.exceptions.ConnectionError:
        return "❌ Cannot connect to server"
    except Exception as e:
        return f"❌ Error: {str(e)}"

def validate_api_key() -> str:
    """Validate the stored OpenAI API key with retry"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            client = get_openai_client()
            if not client:
                return "❌ No API key configured"
            
            client.models.list()
            return "✅ API key is valid"
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)  # Wait before retry
                continue
            return f"❌ API key validation failed: {str(e)}"

# Replace the custom theme configuration
custom_theme = gr.themes.Soft(
    primary_hue="blue",
    secondary_hue="gray",
    font=gr.themes.GoogleFont("Inter"),  # Use only Google Font
    font_mono=gr.themes.GoogleFont("IBM Plex Mono")  # Use only Google Font
).set(
    body_background_fill="white",
    block_background_fill="*neutral_50",
    block_border_width="0px"
)

# Update the Blocks configuration
with gr.Blocks(
    title="Setu Documentation Assistant",
    theme=custom_theme,
    css="""
    * { 
        font-family: Inter, -apple-system, BlinkMacSystemFont, system-ui, sans-serif; 
    }
    code, pre { 
        font-family: 'IBM Plex Mono', Consolas, monospace; 
    }
    .gradio-container { 
        min-height: 100vh; 
        max-width: 1200px !important;
        margin: auto !important;
    }
    .chatbot-window {
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        background: #f9f9f9;
        padding: 10px;
    }
    .chat-input {
        border-radius: 8px;
        border: 2px solid #2196F3;
        margin-top: 10px;
    }
    .system-message {
        padding: 10px;
        border-radius: 8px;
        background: #e3f2fd;
        margin-top: 10px;
    }
    .message.user {
        background: #e3f2fd;
        border-radius: 15px 15px 2px 15px;
        padding: 10px 15px;
        margin: 5px;
        max-width: 80%;
        float: right;
    }
    .message.bot {
        background: #f5f5f5;
        border-radius: 15px 15px 15px 2px;
        padding: 10px 15px;
        margin: 5px;
        max-width: 80%;
        float: left;
    }
    """
) as app:
    gr.Markdown("# Setu Documentation Assistant")
    
    with gr.Tabs():
        # Configuration Tab
        with gr.Tab("Configuration"):
            gr.Markdown("### Current Configuration Status")
            status_table = gr.DataFrame(
                value=get_config_status(),
                interactive=False
            )
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### OpenAI Configuration")
                    openai_key = gr.Textbox(
                        label="OpenAI API Key",
                        type="password"
                    )
                    openai_button = gr.Button("Configure OpenAI")
                    openai_output = gr.Textbox(label="Status")
                    
                with gr.Column():
                    gr.Markdown("### Confluence Configuration")
                    confluence_url = gr.Textbox(label="Confluence URL")
                    confluence_username = gr.Textbox(label="Username")
                    confluence_token = gr.Textbox(
                        label="API Token",
                        type="password"
                    )
                    confluence_button = gr.Button("Configure Confluence")
                    confluence_output = gr.Textbox(label="Status")
            
            gr.Markdown("### API Key Status")
            api_key_status = gr.Textbox(
                value=validate_api_key(),
                label="API Key Status",
                interactive=False
            )
            validate_key_button = gr.Button("🔄 Validate API Key")
            
            refresh_button = gr.Button("Refresh Status")

        # Document Configuration Tab
        with gr.Tab("Document Configuration"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Confluence Documents")
                    conf_product = gr.Dropdown(
                        choices=load_products(),
                        label="Select Product"
                    )
                    conf_doc_ids = gr.Textbox(
                        label="Document IDs (comma-separated)",
                        lines=3,
                        placeholder="e.g., 123456, 789012"
                    )
                    conf_store_button = gr.Button("Store Confluence Documents")
                    conf_status = gr.Textbox(label="Status")

                with gr.Column():
                    gr.Markdown("### URL Documents")
                    url_product = gr.Dropdown(
                        choices=load_products(),
                        label="Select Product"
                    )
                    urls_input = gr.Textbox(
                        label="URLs (comma-separated)",
                        lines=3,
                        placeholder="e.g., https://example.com/doc1, https://example.com/doc2"
                    )
                    url_store_button = gr.Button("Store URLs")
                    url_status = gr.Textbox(label="Status")

            gr.Markdown("### Document Statistics")
            doc_stats = gr.DataFrame()
            stats_product = gr.Dropdown(
                choices=load_products(),
                label="Select Product for Stats"
            )
            stats_button = gr.Button("Get Statistics")
        
        # Chat Tab
        with gr.Tab("Chat"):
            gr.Markdown("### 🤖 AI Documentation Assistant")
            
            with gr.Row():
                with gr.Column(scale=1):
                    chat_product = gr.Dropdown(
                        choices=load_products(),
                        label="📚 Select Product",
                        interactive=True
                    )
                    refresh_products = gr.Button("🔄 Refresh Products")
                    system_message = gr.Markdown(
                        value="Select a product to start chatting",
                        elem_classes=["system-message"]
                    )
                    
                with gr.Column(scale=2):
                    chatbot = gr.Chatbot(
                        label="Conversation",
                        height=500,
                        show_label=False,
                        elem_classes=["chatbot-window"],
                        type="messages"
                    )
                    
                    msg = gr.Textbox(
                        label="Your Question",
                        placeholder="Ask me anything about the documentation... (Press Enter to send)",
                        lines=1,
                        show_label=False,
                        elem_classes=["chat-input"],
                        scale=4
                    )
                    
                    status_box = gr.Textbox(
                        label="Status",
                        value="Ready",
                        interactive=False
                    )
                    
                    with gr.Row():
                        with gr.Column(scale=4):
                            msg
                        with gr.Column(scale=1):
                            send_button = gr.Button("Send 📤")

    # Configure event handlers
    openai_button.click(
        configure_api_key,
        inputs=[openai_key],
        outputs=[openai_output]
    )
    
    confluence_button.click(
        configure_confluence,
        inputs=[confluence_url, confluence_username, confluence_token],
        outputs=[confluence_output]
    )
    
    validate_key_button.click(
        validate_api_key,
        outputs=[api_key_status]
    )
    
    refresh_button.click(
        lambda: gr.DataFrame(value=get_config_status()),
        outputs=[status_table]
    )
    
    conf_store_button.click(
        store_confluence_docs,
        inputs=[conf_product, conf_doc_ids],
        outputs=[conf_status]
    )
    
    url_store_button.click(
        store_urls,
        inputs=[url_product, urls_input],
        outputs=[url_status]
    )
    
    stats_button.click(
        get_document_stats,
        inputs=[stats_product],
        outputs=[doc_stats]
    )
    
    msg.submit(
        fn=chat_with_docs,
        inputs=[msg, chatbot, chat_product, status_box],
        outputs=[msg, chatbot, system_message]
    ).then(
        lambda: gr.update(value=""),
        None,
        [msg]
    )

    send_button.click(
        fn=chat_with_docs,
        inputs=[msg, chatbot, chat_product, status_box],
        outputs=[msg, chatbot, system_message]
    ).then(
        lambda: gr.update(value=""),
        None,
        [msg]
    )
    


    refresh_products.click(
        lambda: (
            gr.update(choices=load_products()),
            "Products refreshed. Select a product to start chatting"
        ),
        outputs=[chat_product, system_message]
    )

    chat_product.change(
        validate_product_selection,
        inputs=[chat_product],
        outputs=[system_message]
    )

    # Add at the top of your interface
    with gr.Row():
        server_status = gr.Textbox(
            value=check_server_status(),
            label="Server Status",
            interactive=False
        )
        refresh_status = gr.Button("🔄 Refresh")
    
    # Add event handler
    refresh_status.click(
        check_server_status,
        outputs=[server_status]
    )

if __name__ == "__main__":
    # Try to initialize OpenAI client
    client = get_openai_client()
    if not client:
        print("Warning: OpenAI client not initialized. Please configure API key in the interface.")
    
    # Create temp directory if it doesn't exist
    os.makedirs("./gradio_temp", exist_ok=True)
    
    app.launch(
        # server_name="0.0.0.0",
        # server_port=7860,
        # share=False,
        # show_api=False,  # Disable API docs
        # show_error=True,
        # favicon_path=None,  # Disable favicon
        # quiet=True,  # Reduce console output
        # root_path="",  # Disable PWA features
        # ssl_verify=False,
        # prevent_thread_lock=True,
        # max_threads=40,
        # auth=None,
        # allowed_paths=[],  # Restrict file access
        # blocked_paths=None,
    )