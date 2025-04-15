import sqlite3
import json
import config
import os

DB_FILE = "product_docs.db"

def get_db_connection():
    """Get a connection to the database."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_product_docs_table():
    """Initialize the product_docs table if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS product_docs (
        product TEXT PRIMARY KEY,
        page_ids TEXT
    )
    ''')
    conn.commit()
    conn.close()

def save_product_docs():
    """Save the PRODUCT_DOCS dictionary to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for product, page_ids in config.PRODUCT_DOCS.items():
        if page_ids:  # Only save non-empty lists
            cursor.execute(
                "INSERT OR REPLACE INTO product_docs (product, page_ids) VALUES (?, ?)",
                (product, json.dumps(page_ids))
            )
    
    conn.commit()
    conn.close()
    print("Saved PRODUCT_DOCS to database")

def load_product_docs():
    """Load the PRODUCT_DOCS dictionary from the database."""
    init_product_docs_table()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT product, page_ids FROM product_docs")
    rows = cursor.fetchall()
    
    for product, page_ids_json in rows:
        config.PRODUCT_DOCS[product] = json.loads(page_ids_json)
    
    conn.close()
    print("Loaded PRODUCT_DOCS from database") 