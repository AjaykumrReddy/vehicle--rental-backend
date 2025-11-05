import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from .logging_config import get_logger, log_api_request, log_api_response

logger = get_logger("middleware")

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all API requests and responses"""
    
    async def dispatch(self, request: Request, call_next):
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Get user ID from token if available
        user_id = None
        if hasattr(request.state, 'user') and request.state.user:
            user_id = request.state.user.get('user_id')
        
        # Log request
        start_time = time.time()
        log_api_request(
            logger, 
            request.method, 
            str(request.url.path), 
            user_id, 
            request_id
        )
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = round((time.time() - start_time) * 1000, 2)
        
        # Log response
        log_api_response(
            logger,
            request.method,
            str(request.url.path),
            response.status_code,
            duration_ms,
            user_id,
            request_id
        )
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response