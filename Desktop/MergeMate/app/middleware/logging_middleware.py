import time
import json
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.utils.logger import app_logger

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Log request
        start_time = time.time()
        
        # Get request details
        request_id = request.headers.get("X-Request-ID", "N/A")
        client_host = request.client.host if request.client else "N/A"
        
        # Get request body if it exists
        body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    try:
                        body = json.loads(body)
                    except json.JSONDecodeError:
                        body = body.decode()
            except Exception as e:
                app_logger.warning(f"Failed to read request body: {str(e)}")
        
        # Create detailed request log
        request_details = {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "client_host": client_host,
            "headers": dict(request.headers),
            "query_params": dict(request.query_params),
            "body": body
        }
        
        # Log complete request details
        app_logger.info(
            "Incoming request details:\n" + json.dumps(request_details, indent=2)
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log response with details
            response_details = {
                "request_id": request_id,
                "status_code": response.status_code,
                "process_time_ms": round(process_time * 1000, 2),
                "headers": dict(response.headers)
            }
            
            app_logger.info(
                "Request completed:\n" + json.dumps(response_details, indent=2)
            )
            
            return response
            
        except Exception as e:
            # Log error with full context
            error_details = {
                "request_id": request_id,
                "error": str(e),
                "request_details": request_details
            }
            
            app_logger.error(
                "Request failed:\n" + json.dumps(error_details, indent=2),
                exc_info=True
            )
            raise 