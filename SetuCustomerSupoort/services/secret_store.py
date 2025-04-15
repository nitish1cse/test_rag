import sqlite3
from typing import Optional, Dict
import os
from cryptography.fernet import Fernet, InvalidToken
from contextlib import contextmanager
import logging
import json
from config import DB_PATH, KEY_PATH, DATA_DIR
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SecretStore:
    def __init__(self):
        self.db_path = "data/secrets.db"
        self.key_path = "data/secret.key"
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.key_path), exist_ok=True)
        
        # Initialize encryption
        self.fernet = self._initialize_encryption()
        self._init_db()

    def _initialize_encryption(self) -> Fernet:
        """Initialize or load encryption key"""
        try:
            if os.path.exists(self.key_path):
                with open(self.key_path, 'rb') as key_file:
                    key = key_file.read()
            else:
                key = Fernet.generate_key()
                with open(self.key_path, 'wb') as key_file:
                    key_file.write(key)
            return Fernet(key)
        except Exception as e:
            logger.error(f"Error initializing encryption: {e}")
            raise

    def _init_db(self):
        """Initialize the SQLite database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS secrets (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

    def store_secret(self, key: str, value: str) -> bool:
        """Store an encrypted secret"""
        try:
            encrypted_value = self.fernet.encrypt(value.encode())
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO secrets (key, value)
                VALUES (?, ?)
            """, (key, encrypted_value.decode()))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error storing secret: {e}")
            return False

    def retrieve_secret(self, key: str) -> Optional[str]:
        """Retrieve and decrypt a secret"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM secrets WHERE key = ?", (key,))
            result = cursor.fetchone()
            conn.close()

            if result:
                try:
                    decrypted_value = self.fernet.decrypt(result[0].encode())
                    return decrypted_value.decode()
                except InvalidToken:
                    logger.error(f"Invalid encryption token for key: {key}")
                    return None
            return None
        except Exception as e:
            logger.error(f"Error retrieving secret: {e}")
            return None

    def reset_encryption(self):
        """Reset encryption and re-encrypt all secrets"""
        try:
            # Get all current secrets
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM secrets")
            old_secrets = cursor.fetchall()

            # Generate new key
            new_key = Fernet.generate_key()
            new_fernet = Fernet(new_key)

            # Re-encrypt all secrets
            for key, encrypted_value in old_secrets:
                try:
                    # Decrypt with old key
                    value = self.fernet.decrypt(encrypted_value.encode()).decode()
                    # Encrypt with new key
                    new_encrypted = new_fernet.encrypt(value.encode())
                    # Update database
                    cursor.execute("""
                        UPDATE secrets 
                        SET value = ? 
                        WHERE key = ?
                    """, (new_encrypted.decode(), key))
                except InvalidToken:
                    logger.error(f"Could not decrypt value for key: {key}")
                    continue

            # Save new key
            with open(self.key_path, 'wb') as key_file:
                key_file.write(new_key)

            conn.commit()
            conn.close()

            # Update current fernet instance
            self.fernet = new_fernet
            return True
        except Exception as e:
            logger.error(f"Error resetting encryption: {e}")
            return False

    def delete_secret(self, key: str) -> bool:
        """Delete a secret"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM secrets WHERE key = ?", (key,))
                conn.commit()
            logger.info(f"Secret deleted successfully: {key}")
            return True
        except Exception as e:
            logger.error(f"Error deleting secret: {e}")
            return False

    def list_secrets(self) -> Dict[str, Dict]:
        """List all secrets (without values)"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT key, created_at, updated_at 
                    FROM secrets
                """)
                results = cursor.fetchall()
                return {
                    row['key']: {
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at']
                    } for row in results
                }
        except Exception as e:
            logger.error(f"Error listing secrets: {e}")
            return {}

# Create global instance
secret_store = SecretStore()
store_secret = secret_store.store_secret
retrieve_secret = secret_store.retrieve_secret
reset_encryption = secret_store.reset_encryption
