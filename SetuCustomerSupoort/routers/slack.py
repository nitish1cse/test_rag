from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Optional
import logging
import logging.handlers
import os
import json
from services.secret_store import store_secret, retrieve_secret
from services.url_service import url_store
from services.product_service import product_service
from langchain_core.documents import Document
from datetime import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import time
import random
import asyncio
import functools

router = APIRouter(prefix="/slack", tags=["Slack"])

# Configure logging
logger = logging.getLogger(__name__)

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Add a file handler for Slack processing logs
slack_handler = logging.handlers.RotatingFileHandler(
    "logs/slack_processing.log",
    maxBytes=10485760,  # 10MB
    backupCount=5
)

# Set formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
slack_handler.setFormatter(formatter)

# Add handler to logger if it doesn't already have it
if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in logger.handlers):
    logger.addHandler(slack_handler)
    logger.setLevel(logging.INFO)

# Define models for request validation
class SlackConfig(BaseModel):
    api_token: str
    bot_token: Optional[str] = None

class SlackChannelConfig(BaseModel):
    channel_id: str
    product: str
    include_threads: bool = True
    max_messages: int = 1000
    description: Optional[str] = None

# Path to store slack channel configurations
SLACK_CONFIG_PATH = "config/slack_channels.json"
os.makedirs(os.path.dirname(SLACK_CONFIG_PATH), exist_ok=True)

def load_channel_configs() -> Dict:
    """Load slack channel configurations from file"""
    if not os.path.exists(SLACK_CONFIG_PATH):
        return {}
    try:
        with open(SLACK_CONFIG_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading slack configs: {e}")
        return {}

def save_channel_configs(configs: Dict) -> bool:
    """Save slack channel configurations to file"""
    try:
        with open(SLACK_CONFIG_PATH, 'w') as f:
            json.dump(configs, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving slack configs: {e}")
        return False

def get_slack_client():
    """Get a Slack client using the stored API token"""
    token = retrieve_secret("SLACK_API_TOKEN")
    if not token:
        raise HTTPException(status_code=400, detail="Slack API token not configured")
    
    return WebClient(token=token)

# Add a retry decorator for handling rate limits
def retry_with_backoff(max_retries=None, initial_backoff=None, max_backoff=None):
    """Retry decorator with exponential backoff for handling rate limits"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Use global settings or provided values
            nonlocal max_retries, initial_backoff, max_backoff
            max_retries = max_retries or rate_limit_settings["max_retries"]
            initial_backoff = initial_backoff or rate_limit_settings["initial_backoff"]
            max_backoff = max_backoff or rate_limit_settings["max_backoff"]
            
            retries = 0
            backoff = initial_backoff
            
            while True:
                try:
                    return await func(*args, **kwargs)
                except SlackApiError as e:
                    # Check if it's a rate limiting error
                    if "ratelimited" in str(e).lower() or e.response.status_code == 429:
                        if retries >= max_retries:
                            logger.error(f"Maximum retries ({max_retries}) exceeded for rate limit")
                            raise
                        
                        # Get retry_after if available, otherwise use exponential backoff
                        retry_after = e.response.headers.get("Retry-After", None)
                        if retry_after:
                            backoff = float(retry_after)
                        
                        # Add some jitter to avoid all clients retrying simultaneously
                        jitter = random.uniform(0, 0.3 * backoff)
                        backoff_with_jitter = backoff + jitter
                        
                        logger.warning(f"Rate limited by Slack API. Retrying in {backoff_with_jitter:.2f}s (retry {retries+1}/{max_retries})")
                        
                        # Wait before retrying
                        await asyncio.sleep(backoff_with_jitter)
                        
                        # Increase backoff for next iteration
                        backoff = min(backoff * 2, max_backoff)
                        retries += 1
                    else:
                        # If it's not a rate limiting error, just raise it
                        raise
                        
        return wrapper
    return decorator

@router.post("/config")
async def configure_slack(config: SlackConfig):
    """Configure Slack API keys"""
    try:
        # Validate the token by making a test API call
        client = WebClient(token=config.api_token)
        test_result = client.api_test()
        
        if not test_result["ok"]:
            raise HTTPException(status_code=400, detail="Invalid Slack API token")
        
        # Store the tokens securely
        store_secret("SLACK_API_TOKEN", config.api_token)
        if config.bot_token:
            store_secret("SLACK_BOT_TOKEN", config.bot_token)
        
        return {"message": "Slack API configured successfully"}
    except SlackApiError as e:
        logger.error(f"Slack API Error: {e}")
        raise HTTPException(status_code=400, detail=f"Slack API Error: {str(e)}")
    except Exception as e:
        logger.error(f"Error configuring Slack: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/channels")
async def configure_channel(config: SlackChannelConfig):
    """Configure a Slack channel for document extraction"""
    try:
        # Validate the product exists
        all_products = product_service.get_all_products()
        if config.product not in all_products:
            raise HTTPException(status_code=400, detail=f"Invalid product: {config.product}")
        
        # Validate the channel ID by trying to get info about it
        client = get_slack_client()
        try:
            channel_info = client.conversations_info(channel=config.channel_id)
            channel_name = channel_info["channel"]["name"]
        except SlackApiError as e:
            raise HTTPException(status_code=400, detail=f"Invalid channel ID: {config.channel_id}")
        
        # Load existing configurations
        configs = load_channel_configs()
        
        # Add or update this configuration
        configs[config.channel_id] = {
            "product": config.product,
            "include_threads": config.include_threads,
            "max_messages": config.max_messages,
            "description": config.description or f"Channel: {channel_name}",
            "last_processed": None
        }
        
        # Save configurations
        if not save_channel_configs(configs):
            raise HTTPException(status_code=500, detail="Failed to save channel configuration")
        
        return {
            "message": f"Channel {channel_name} configured successfully for product {config.product}",
            "channel_id": config.channel_id,
            "product": config.product
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error configuring Slack channel: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Add a helper function for safely making API calls with handling for rate limits
async def safe_slack_api_call(client, method_name, *args, **kwargs):
    """Make a Slack API call with retry and rate limit handling"""
    retries = 0
    max_retries = rate_limit_settings["max_retries"]
    backoff = rate_limit_settings["initial_backoff"]
    max_backoff = rate_limit_settings["max_backoff"]
    
    while True:
        try:
            # Get the method from the client
            method = getattr(client, method_name)
            
            # Call the method with the provided arguments
            result = method(*args, **kwargs)
            return result
            
        except SlackApiError as e:
            # Check if it's a rate limiting error
            if "ratelimited" in str(e).lower() or e.response.status_code == 429:
                if retries >= max_retries:
                    logger.error(f"Maximum retries ({max_retries}) exceeded for rate limit on {method_name}")
                    raise
                
                # Get retry_after if available, otherwise use exponential backoff
                retry_after = e.response.headers.get("Retry-After", None)
                if retry_after:
                    backoff = float(retry_after)
                
                # Add some jitter to avoid all clients retrying simultaneously
                jitter = random.uniform(0, 0.3 * backoff)
                backoff_with_jitter = backoff + jitter
                
                logger.warning(f"Rate limited by Slack API for {method_name}. Retrying in {backoff_with_jitter:.2f}s (retry {retries+1}/{max_retries})")
                
                # Wait before retrying
                await asyncio.sleep(backoff_with_jitter)
                
                # Increase backoff for next iteration
                backoff = min(backoff * 2, max_backoff)
                retries += 1
            else:
                # If it's not a rate limiting error, just raise it
                raise

# Create a simple user cache to reduce API calls
user_cache = {}

def cache_user_info(max_size=500, ttl=3600):
    """Decorator to cache user info and handle expiration"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(client, user_id, *args, **kwargs):
            # Check if in cache and not expired
            now = time.time()
            if user_id in user_cache:
                user_data, timestamp = user_cache[user_id]
                # If not expired, return cached result
                if now - timestamp < ttl:
                    return user_data
            
            # Limit cache size
            if len(user_cache) >= max_size:
                # Remove the oldest entries
                oldest_key = min(user_cache.keys(), key=lambda k: user_cache[k][1])
                user_cache.pop(oldest_key)
            
            # Get actual data
            result = await func(client, user_id, *args, **kwargs)
            
            # Cache the result with timestamp
            user_cache[user_id] = (result, now)
            
            return result
        return wrapper
    return decorator

@cache_user_info(max_size=500, ttl=3600)  # Cache for 1 hour
async def get_user_info(client, user_id):
    """Get user info with caching and rate limit handling"""
    try:
        # Make synchronous API call
        user_info = client.users_info(user=user_id)
        return user_info
    except SlackApiError as e:
        if "ratelimited" in str(e).lower() or e.response.status_code == 429:
            # Handle rate limiting
            retry_after = e.response.headers.get("Retry-After", "1")
            backoff = float(retry_after)
            logger.warning(f"Rate limited when fetching user info. Waiting {backoff}s")
            await asyncio.sleep(backoff + 0.5)
            
            # Try one more time
            return client.users_info(user=user_id)
        else:
            # Re-raise other errors
            raise

@router.get("/channels")
async def list_channels():
    """List all configured Slack channels"""
    try:
        configs = load_channel_configs()
        
        # Get channel names for all configured channels
        client = get_slack_client()
        result = []
        
        # Process channels in batches to avoid rate limits
        for batch_start in range(0, len(configs), 20):
            batch_channels = list(configs.keys())[batch_start:batch_start + 20]
            logger.info(f"Processing batch of {len(batch_channels)} channels (batch {batch_start//20 + 1})")
            
            # Add delay between batches to avoid rate limits
            if batch_start > 0:
                await asyncio.sleep(1)
            
            for channel_id in batch_channels:
                try:
                    # Call Slack API directly but with rate limit handling
                    try:
                        channel_info = client.conversations_info(channel=channel_id)
                        channel_name = channel_info["channel"]["name"]
                    except SlackApiError as e:
                        if "ratelimited" in str(e).lower() or e.response.status_code == 429:
                            # Handle rate limiting
                            retry_after = e.response.headers.get("Retry-After", "1")
                            backoff = float(retry_after)
                            logger.warning(f"Rate limited when fetching channel info. Waiting {backoff}s")
                            await asyncio.sleep(backoff + 0.5)
                            
                            # Try one more time after waiting
                            channel_info = client.conversations_info(channel=channel_id)
                            channel_name = channel_info["channel"]["name"]
                        else:
                            # For other API errors, treat as inaccessible
                            logger.warning(f"Slack API error for channel {channel_id}: {str(e)}")
                            channel_name = "Unknown or inaccessible channel"
                except Exception as e:
                    logger.warning(f"Error fetching info for channel {channel_id}: {str(e)}")
                    channel_name = "Unknown or inaccessible channel"
                    
                result.append({
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "product": configs[channel_id]["product"],
                    "description": configs[channel_id].get("description", ""),
                    "last_processed": configs[channel_id].get("last_processed", None)
                })
                
                # Small delay between channel info requests
                await asyncio.sleep(0.2)
        
        return {"channels": result}
    except Exception as e:
        logger.error(f"Error listing Slack channels: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: str):
    """Remove a Slack channel configuration"""
    try:
        configs = load_channel_configs()
        
        if channel_id not in configs:
            raise HTTPException(status_code=404, detail=f"Channel ID {channel_id} not found in configurations")
        
        product = configs[channel_id]["product"]
        del configs[channel_id]
        
        if not save_channel_configs(configs):
            raise HTTPException(status_code=500, detail="Failed to save channel configuration")
        
        return {
            "message": f"Channel {channel_id} removed from configurations",
            "product": product
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting Slack channel: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process/{channel_id}")
async def process_channel(channel_id: str, force_full: bool = False):
    """Process messages from a Slack channel and store as documents"""
    try:
        logger.info(f"Starting to process Slack channel: {channel_id} (force_full={force_full})")
        
        # Load channel configuration
        configs = load_channel_configs()
        
        if channel_id not in configs:
            logger.error(f"Channel ID {channel_id} not found in configurations")
            raise HTTPException(status_code=404, detail=f"Channel ID {channel_id} not found in configurations")
        
        channel_config = configs[channel_id]
        product = channel_config["product"]
        logger.info(f"Processing channel for product: {product}")
        logger.info(f"Channel configuration: include_threads={channel_config['include_threads']}, max_messages={channel_config['max_messages']}")
        
        # Get Slack client
        client = get_slack_client()
        logger.info("Slack client initialized successfully")
        
        # Get messages from the channel with rate limit handling
        try:
            # Determine how far back to go
            oldest = None
            if not force_full and channel_config.get("last_processed"):
                oldest = channel_config["last_processed"]
                last_date = datetime.fromtimestamp(float(oldest)).strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"Fetching messages since: {last_date} (timestamp: {oldest})")
            else:
                logger.info("Fetching all messages (no timestamp filter)")
            
            # Get messages from the channel
            logger.info(f"Requesting {channel_config['max_messages']} messages from Slack API")
            
            # Use cursor-based pagination to handle large channels
            messages = []
            cursor = None
            page_count = 0
            remaining_msg_count = channel_config["max_messages"]
            
            # Configure batch size to avoid rate limits
            batch_size = min(100, remaining_msg_count)  # Slack API max is 1000, but we use smaller batches
            
            while remaining_msg_count > 0 and (page_count == 0 or cursor):
                page_count += 1
                logger.info(f"Fetching message page {page_count} (batch size: {batch_size})")
                
                # Add delay between requests to avoid rate limiting
                if page_count > 1:
                    # Add a small delay between API calls
                    await asyncio.sleep(1.0)  # 1 second delay
                
                try:
                    # Call Slack API with pagination
                    response = client.conversations_history(
                        channel=channel_id,
                        cursor=cursor,
                        limit=batch_size,
                        oldest=oldest
                    )
                    
                    # Get messages from response
                    page_messages = response["messages"]
                    logger.info(f"Retrieved {len(page_messages)} messages from page {page_count}")
                    
                    # Add messages to our list
                    messages.extend(page_messages)
                    
                    # Update cursor and remaining count
                    cursor = response.get("response_metadata", {}).get("next_cursor", None)
                    remaining_msg_count -= len(page_messages)
                    
                    # If we got fewer messages than requested, there are no more
                    if len(page_messages) < batch_size:
                        logger.info(f"Reached end of channel history after {page_count} pages")
                        break
                        
                    # Update batch size for next request
                    batch_size = min(100, remaining_msg_count)
                    
                except SlackApiError as e:
                    if "ratelimited" in str(e).lower() or e.response.status_code == 429:
                        retry_after = e.response.headers.get("Retry-After", "1")
                        backoff = float(retry_after)
                        logger.warning(f"Rate limited during pagination. Waiting {backoff}s before retry")
                        await asyncio.sleep(backoff + 0.5)  # Add a small buffer
                        # Don't update cursor or counts - we'll retry the same request
                    else:
                        # For other errors, log and re-raise
                        logger.error(f"Error fetching messages: {str(e)}")
                        raise
            
            logger.info(f"Total messages retrieved: {len(messages)}")
            
            # Get thread replies if configured with rate limit handling
            if channel_config["include_threads"]:
                logger.info("Thread processing is enabled - fetching thread replies")
                thread_count = 0
                reply_count = 0
                
                # Extract all thread timestamps
                thread_ts_list = [msg.get("thread_ts") for msg in messages if msg.get("thread_ts")]
                thread_ts_set = set(thread_ts_list)  # Remove duplicates
                
                logger.info(f"Found {len(thread_ts_set)} threads to process")
                
                # Process threads with pagination and rate limit handling
                for i, thread_ts in enumerate(thread_ts_set):
                    thread_count += 1
                    
                    # Log progress in batches
                    if i % 10 == 0 or i == len(thread_ts_set) - 1:
                        logger.info(f"Processing thread {i+1}/{len(thread_ts_set)}")
                    
                    # Add a small delay between thread requests to avoid rate limits
                    if i > 0 and i % 5 == 0:
                        await asyncio.sleep(1.0)  # 1 second delay every 5 threads
                    
                    try:
                        logger.info(f"Fetching thread replies for thread ts: {thread_ts}")
                        thread_messages = []
                        thread_cursor = None
                        
                        # Use pagination for threads too
                        while True:
                            thread_response = client.conversations_replies(
                                channel=channel_id,
                                ts=thread_ts,
                                cursor=thread_cursor,
                                limit=50  # Smaller batch size for threads
                            )
                            
                            # Get thread messages
                            page_replies = thread_response["messages"]
                            
                            # Add to our list, excluding the parent message
                            parent_ts = thread_ts  # The thread parent has the same ts as thread_ts
                            thread_messages.extend([reply for reply in page_replies if reply["ts"] != parent_ts])
                            
                            # Check if there are more pages
                            thread_cursor = thread_response.get("response_metadata", {}).get("next_cursor")
                            if not thread_cursor:
                                break
                            
                            # Add small delay between pages
                            await asyncio.sleep(0.5)
                        
                        # Add all thread messages to our main list
                        reply_count += len(thread_messages)
                        messages.extend(thread_messages)
                        logger.info(f"Added {len(thread_messages)} replies from thread")
                        
                    except SlackApiError as e:
                        if "ratelimited" in str(e).lower() or e.response.status_code == 429:
                            retry_after = e.response.headers.get("Retry-After", "1")
                            backoff = float(retry_after)
                            logger.warning(f"Rate limited during thread fetch. Waiting {backoff}s before retry")
                            await asyncio.sleep(backoff + 0.5)  # Add a small buffer
                            # Retry this thread in the next iteration
                            i -= 1  # Decrement to retry this thread
                        else:
                            # For other errors, log and continue with next thread
                            logger.warning(f"Error fetching thread {thread_ts}: {str(e)}")
                            # Skip this thread but continue with others
                
                logger.info(f"Retrieved {reply_count} replies from {thread_count} threads")
            
            # Convert messages to documents
            documents = []
            skipped_count = 0
            
            logger.info("Starting to process messages into documents")
            
            # Process messages in larger batches to optimize performance
            for msg in messages:
                # Skip bot messages unless they contain useful content
                if msg.get("subtype") == "bot_message" and not msg.get("text"):
                    skipped_count += 1
                    continue
                
                # Get message text 
                text = msg.get("text", "")
                
                # Skip empty messages
                if not text.strip():
                    skipped_count += 1
                    continue
                
                # # Get user info for context with caching
                # user_id = msg.get("user")
                # user_name = "Unknown User"
                #
                # if user_id:
                #     try:
                #         # Use cached user info if possible, to speed up processing
                #         if user_id in user_cache:
                #             user_data, _ = user_cache[user_id]
                #             user_name = user_data["user"]["real_name"]
                #         else:
                #             # Only call API if not cached
                #             user_info = client.users_info(user=user_id)
                #             user_name = user_info["user"]["real_name"]
                #             # Cache the result
                #             user_cache[user_id] = (user_info, time.time())
                #     except Exception as e:
                #         logger.warning(f"Error fetching user info for {user_id}: {str(e)}")
                
                # Create document with user context
                doc_text = f"Message in  Slack:\n\n{text}"
                
                # Add timestamp as a date for better context
                timestamp = float(msg.get("ts", 0))
                message_date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                
                doc = Document(
                    page_content=doc_text,
                    metadata={
                        "source": "slack",
                        "channel_id": channel_id,
                        #"user": user_name,
                        "timestamp": message_date,
                        "message_ts": msg.get("ts"),
                        "thread_ts": msg.get("thread_ts"),
                        "product": product,
                        "title": f"Slack message  on {message_date}"
                    }
                )
                
                documents.append(doc)
            
            logger.info(f"Created {len(documents)} documents from messages (skipped {skipped_count} messages)")
            
            # Store documents in vector store using batch processing for better performance
            chunks_stored = 0
            logger.info(f"Starting to add {len(documents)} documents to vectorstore for product {product}")
            
            # Use batch processing if available in your vector store
            BATCH_SIZE = 50  # Adjust based on your vector store capabilities
            
            for i in range(0, len(documents), BATCH_SIZE):
                batch = documents[i:i+BATCH_SIZE]
                batch_size = len(batch)
                logger.info(f"Processing batch {i//BATCH_SIZE + 1}/{(len(documents) + BATCH_SIZE - 1)//BATCH_SIZE} ({batch_size} documents)")
                
                # Try to use batch processing if the method is available
                try:
                    # Check if the vectorstore has a batch method
                    if hasattr(url_store, 'add_documents_to_vectorstore'):
                        batch_chunks = url_store.add_documents_to_vectorstore(batch, product)
                        chunks_stored += batch_chunks
                        logger.info(f"Batch stored {batch_chunks} chunks")
                    else:
                        # Fall back to individual processing
                        batch_chunks = 0
                        for doc in batch:
                            chunks = url_store.add_document_to_vectorstore(doc, product)
                            batch_chunks += chunks
                            chunks_stored += chunks
                        logger.info(f"Individually stored {batch_chunks} chunks")
                    
                    # Add a small sleep to prevent resource exhaustion
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Error processing batch: {str(e)}")
                    # Fall back to individual processing on batch failure
                    for doc in batch:
                        try:
                            chunks = url_store.add_document_to_vectorstore(doc, product)
                            chunks_stored += chunks
                        except Exception as inner_e:
                            logger.error(f"Error processing document: {str(inner_e)}")
            
            logger.info(f"Successfully stored {chunks_stored} chunks in vectorstore")
            
            # Update last processed time
            newest_ts = max([float(msg.get("ts", 0)) for msg in messages]) if messages else None
            if newest_ts:
                newest_date = datetime.fromtimestamp(newest_ts).strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"Updating last_processed timestamp to {newest_date} (timestamp: {newest_ts})")
                configs[channel_id]["last_processed"] = str(newest_ts)
                save_channel_configs(configs)
            
            result = {
                "message": f"Processed {len(documents)} messages from Slack channel, stored {chunks_stored} chunks",
                "product": product,
                "messages_processed": len(documents),
                "chunks_stored": chunks_stored
            }
            
            logger.info(f"Channel processing complete: {result['message']}")
            return result
            
        except SlackApiError as e:
            logger.error(f"Slack API Error while processing channel {channel_id}: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Slack API Error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing Slack channel {channel_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process/all")
async def process_all_channels(force_full: bool = False):
    """Process all configured Slack channels"""
    try:
        logger.info(f"Starting to process all Slack channels (force_full={force_full})")
        configs = load_channel_configs()
        logger.info(f"Found {len(configs)} configured channels")
        
        results = {}
        success_count = 0
        failure_count = 0
        total_messages = 0
        total_chunks = 0
        
        # Get rate limit settings from the global configuration
        batch_size = rate_limit_settings["batch_size"]
        batch_delay = rate_limit_settings["batch_delay"]
        channel_delay = rate_limit_settings["channel_delay"]
        failure_delay = rate_limit_settings["failure_delay"]
        
        logger.info(f"Using rate limit settings: batch_size={batch_size}, batch_delay={batch_delay}s, channel_delay={channel_delay}s")
        
        # Process channels in smaller batches to avoid rate limits
        for batch_start in range(0, len(configs), batch_size):
            batch_channels = list(configs.keys())[batch_start:batch_start + batch_size]
            batch_num = batch_start // batch_size + 1
            total_batches = (len(configs) + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch_channels)} channels)")
            
            # Add delay between batches
            if batch_start > 0:
                logger.info(f"Waiting {batch_delay} seconds before starting batch {batch_num} to avoid rate limits...")
                await asyncio.sleep(batch_delay)
            
            # Process channels in this batch
            for channel_id in batch_channels:
                logger.info(f"Processing channel {channel_id} for product {configs[channel_id]['product']}")
                try:
                    result = await process_channel(channel_id, force_full)
                    results[channel_id] = {
                        "success": True,
                        "messages_processed": result["messages_processed"],
                        "chunks_stored": result["chunks_stored"]
                    }
                    success_count += 1
                    total_messages += result["messages_processed"]
                    total_chunks += result["chunks_stored"]
                    logger.info(f"Successfully processed channel {channel_id}: {result['messages_processed']} messages, {result['chunks_stored']} chunks")
                    
                    # Add delay between processing channels
                    logger.info(f"Waiting {channel_delay} seconds before processing next channel...")
                    await asyncio.sleep(channel_delay)
                    
                except Exception as e:
                    failure_count += 1
                    results[channel_id] = {
                        "success": False,
                        "error": str(e)
                    }
                    logger.error(f"Failed to process channel {channel_id}: {str(e)}")
                    
                    # Add a longer delay after failure to recover from any rate limiting
                    logger.info(f"Waiting {failure_delay} seconds to recover after failure...")
                    await asyncio.sleep(failure_delay)
        
        logger.info(f"Finished processing all channels: {success_count} succeeded, {failure_count} failed")
        logger.info(f"Total messages processed: {total_messages}, total chunks stored: {total_chunks}")
        
        return {
            "message": f"Processed {len(configs)} Slack channels ({success_count} succeeded, {failure_count} failed)",
            "results": results,
            "summary": {
                "total_channels": len(configs),
                "successful_channels": success_count,
                "failed_channels": failure_count,
                "total_messages_processed": total_messages,
                "total_chunks_stored": total_chunks
            }
        }
    except Exception as e:
        logger.error(f"Error processing all Slack channels: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs")
async def get_slack_logs(lines: int = 100):
    """Get the most recent Slack processing logs"""
    try:
        log_file = "logs/slack_processing.log"
        if not os.path.exists(log_file):
            return {"message": "No logs found", "logs": []}
            
        # Read the last 'lines' lines from the log file
        with open(log_file, 'r') as f:
            # Use a deque to efficiently get the last N lines
            from collections import deque
            log_lines = deque(f, lines)
        
        return {
            "message": f"Retrieved last {len(log_lines)} lines of logs",
            "logs": list(log_lines)
        }
    except Exception as e:
        logger.error(f"Error retrieving logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Add this model for rate limit configuration
class RateLimitConfig(BaseModel):
    batch_size: int = 5  # Number of channels to process in a batch
    batch_delay: int = 30  # Seconds to wait between batches
    channel_delay: int = 5  # Seconds to wait between channels
    failure_delay: int = 10  # Seconds to wait after failure
    max_retries: int = 5  # Maximum number of retries
    initial_backoff: float = 1.0  # Initial backoff in seconds
    max_backoff: float = 60.0  # Maximum backoff in seconds

# Define global rate limit settings with defaults
rate_limit_settings = {
    "batch_size": 5,
    "batch_delay": 30,
    "channel_delay": 5,
    "failure_delay": 10,
    "max_retries": 5,
    "initial_backoff": 1.0,
    "max_backoff": 60.0
}

# Add configuration path to store rate limit settings
RATE_LIMIT_CONFIG_PATH = "config/slack_rate_limits.json"
os.makedirs(os.path.dirname(RATE_LIMIT_CONFIG_PATH), exist_ok=True)

# Initialize settings from file if it exists
if os.path.exists(RATE_LIMIT_CONFIG_PATH):
    try:
        with open(RATE_LIMIT_CONFIG_PATH, 'r') as f:
            loaded_settings = json.load(f)
            rate_limit_settings.update(loaded_settings)
    except Exception as e:
        logger.error(f"Error loading rate limit settings: {e}")

# Add this endpoint to configure rate limits
@router.post("/rate-limits")
async def configure_rate_limits(config: RateLimitConfig):
    """Configure rate limiting parameters"""
    try:
        # Update rate limit settings
        rate_limit_settings.update({
            "batch_size": config.batch_size,
            "batch_delay": config.batch_delay,
            "channel_delay": config.channel_delay,
            "failure_delay": config.failure_delay,
            "max_retries": config.max_retries,
            "initial_backoff": config.initial_backoff,
            "max_backoff": config.max_backoff
        })
        
        # Save settings to file
        with open(RATE_LIMIT_CONFIG_PATH, 'w') as f:
            json.dump(rate_limit_settings, f, indent=2)
        
        logger.info(f"Updated rate limit settings: {rate_limit_settings}")
        
        return {
            "message": "Rate limit settings updated successfully",
            "settings": rate_limit_settings
        }
    except Exception as e:
        logger.error(f"Error configuring rate limits: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rate-limits")
async def get_rate_limits():
    """Get current rate limiting parameters"""
    return {
        "settings": rate_limit_settings
    } 