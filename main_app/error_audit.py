from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from .models import ErrorAudit
from .logging_config import get_logger
from datetime import datetime, timezone
import traceback
import uuid

logger = get_logger(__name__)

class ErrorAuditor:
    def __init__(self, db: Session):
        self.db = db
    
    def log_api_error(
        self,
        error: Exception,
        endpoint: str,
        http_method: str,
        http_status: int,
        user_id: str = None,
        request_id: str = None,
        user_agent: str = None,
        ip_address: str = None,
        metadata: dict = None
    ):
        """Log backend API errors"""
        try:
            severity = self._determine_severity(http_status, error)
            
            error_audit = ErrorAudit(
                error_type="API_ERROR",
                severity=severity,
                source="BACKEND",
                user_id=user_id,
                request_id=request_id,
                error_code=error.__class__.__name__,
                error_message=str(error),
                stack_trace=traceback.format_exc(),
                endpoint=endpoint,
                http_method=http_method,
                http_status=http_status,
                user_agent=user_agent,
                ip_address=ip_address,
                metadata=metadata or {}
            )
            
            self.db.add(error_audit)
            self.db.commit()
            
            logger.error(f"API error logged", extra={
                "error_audit_id": str(error_audit.id),
                "endpoint": endpoint,
                "severity": severity
            })
            
        except Exception as e:
            logger.error(f"Failed to log API error: {str(e)}")
    
    def log_ui_error(
        self,
        error_message: str,
        error_code: str = None,
        stack_trace: str = None,
        user_id: str = None,
        session_id: str = None,
        user_agent: str = None,
        page_url: str = None,
        metadata: dict = None
    ):
        """Log frontend/UI errors"""
        try:
            error_audit = ErrorAudit(
                error_type="UI_ERROR",
                severity="MEDIUM",
                source="FRONTEND",
                user_id=user_id,
                session_id=session_id,
                error_code=error_code or "UI_ERROR",
                error_message=error_message,
                stack_trace=stack_trace,
                endpoint=page_url,
                user_agent=user_agent,
                metadata=metadata or {}
            )
            
            self.db.add(error_audit)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log UI error: {str(e)}")
    
    def log_third_party_error(
        self,
        service_name: str,
        error_message: str,
        error_code: str = None,
        http_status: int = None,
        user_id: str = None,
        request_id: str = None,
        metadata: dict = None
    ):
        """Log third-party service errors"""
        try:
            severity = "HIGH" if http_status and http_status >= 500 else "MEDIUM"
            
            error_audit = ErrorAudit(
                error_type="THIRD_PARTY_ERROR",
                severity=severity,
                source="EXTERNAL",
                user_id=user_id,
                request_id=request_id,
                error_code=error_code or f"{service_name}_ERROR",
                error_message=f"{service_name}: {error_message}",
                http_status=http_status,
                metadata={
                    "service_name": service_name,
                    **(metadata or {})
                }
            )
            
            self.db.add(error_audit)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log third-party error: {str(e)}")
    
    def _determine_severity(self, http_status: int, error: Exception) -> str:
        """Determine error severity based on status code and error type"""
        if http_status >= 500:
            return "CRITICAL"
        elif http_status >= 400:
            return "HIGH"
        elif isinstance(error, (ValueError, TypeError)):
            return "MEDIUM"
        else:
            return "LOW"

# Global error auditor factory
def get_error_auditor(db: Session) -> ErrorAuditor:
    return ErrorAuditor(db)