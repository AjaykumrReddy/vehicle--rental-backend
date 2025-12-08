from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from .db import get_db
from .error_audit import get_error_auditor
import uuid
import traceback

class ErrorAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Generate request ID for tracking
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        try:
            response = await call_next(request)
            return response
            
        except Exception as error:
            # Log the error to audit system
            try:
                db: Session = next(get_db())
                auditor = get_error_auditor(db)
                
                # Extract user info if available
                user_id = getattr(request.state, 'user_id', None)
                
                auditor.log_api_error(
                    error=error,
                    endpoint=str(request.url.path),
                    http_method=request.method,
                    http_status=500,
                    user_id=user_id,
                    request_id=request_id,
                    user_agent=request.headers.get("user-agent"),
                    ip_address=request.client.host if request.client else None,
                    metadata={
                        "query_params": dict(request.query_params),
                        "path_params": request.path_params
                    }
                )
                
                db.close()
                
            except Exception as audit_error:
                # Don't let audit errors break the response
                print(f"Error audit failed: {audit_error}")
            
            # Return error response
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "request_id": request_id
                }
            )