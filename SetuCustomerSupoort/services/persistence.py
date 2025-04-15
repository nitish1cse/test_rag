import json
import os
import config

PERSISTENCE_FILE = "product_docs.json"

def save_product_docs():
    """Save the PRODUCT_DOCS dictionary to a JSON file."""
    try:
        print(f"Saving PRODUCT_DOCS: {json.dumps(config.PRODUCT_DOCS, indent=2)}")
        with open(PERSISTENCE_FILE, 'w') as f:
            json.dump(config.PRODUCT_DOCS, f, indent=4)
        print(f"Successfully saved PRODUCT_DOCS to {PERSISTENCE_FILE}")
        
        # Verify the file was written correctly
        with open(PERSISTENCE_FILE, 'r') as f:
            saved_content = json.load(f)
        print(f"Verified saved content: {json.dumps(saved_content, indent=2)}")
    except Exception as e:
        print(f"Error saving PRODUCT_DOCS: {e}")

def load_product_docs():
    """Load the PRODUCT_DOCS dictionary from a JSON file."""
    if os.path.exists(PERSISTENCE_FILE):
        try:
            with open(PERSISTENCE_FILE, 'r') as f:
                loaded_docs = json.load(f)
            print(f"Loaded from file: {json.dumps(loaded_docs, indent=2)}")
            config.PRODUCT_DOCS.update(loaded_docs)
            print(f"After update - PRODUCT_DOCS: {json.dumps(config.PRODUCT_DOCS, indent=2)}")
        except Exception as e:
            print(f"Error loading PRODUCT_DOCS: {e}") 