from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from uuid import UUID
from ..db import get_db
from ..models import ErrorAudit
from ..auth import get_current_user, get_optional_current_user

router = APIRouter(prefix="/errors", tags=["error-audit"])

class ErrorAuditRequest(BaseModel):
    error_type: str
    severity: str
    source: str
    error_message: str
    error_code: Optional[str] = None
    stack_trace: Optional[str] = None
    endpoint: Optional[str] = None
    http_method: Optional[str] = None
    http_status: Optional[int] = None
    context_data: Optional[Dict[str, Any]] = None

@router.post("/log")
def log_error(
    error_data: ErrorAuditRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    """Log a single error to audit table"""
    try:
        error_audit = ErrorAudit(
            error_type=error_data.error_type,
            severity=error_data.severity,
            source=error_data.source,
            error_message=error_data.error_message,
            error_code=error_data.error_code,
            stack_trace=error_data.stack_trace,
            endpoint=error_data.endpoint or str(request.url),
            http_method=error_data.http_method or request.method,
            http_status=error_data.http_status,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host,
            context_data=error_data.context_data,
            user_id=UUID(current_user["user_id"]) if current_user and current_user.get("user_id") else None
        )
        
        db.add(error_audit)
        db.commit()
        db.refresh(error_audit)
        
        return {
            "success": True,
            "error_id": str(error_audit.id),
            "message": "Error logged successfully"
        }
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to log error: {str(e)}"
        )

@router.post("/log-batch")
def log_errors_batch(
    errors: List[ErrorAuditRequest],
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    """Log multiple errors in batch (recommended for mobile apps)"""
    try:
        error_ids = []
        user_id = UUID(current_user["user_id"]) if current_user and current_user.get("user_id") else None
        
        for error_data in errors:
            error_audit = ErrorAudit(
                error_type=error_data.error_type,
                severity=error_data.severity,
                source=error_data.source,
                error_message=error_data.error_message,
                error_code=error_data.error_code,
                stack_trace=error_data.stack_trace,
                endpoint=error_data.endpoint,
                http_method=error_data.http_method,
                http_status=error_data.http_status,
                user_agent=request.headers.get("user-agent"),
                ip_address=request.client.host,
                context_data=error_data.context_data,
                user_id=user_id
            )
            db.add(error_audit)
            db.flush()  # Get ID without committing
            error_ids.append(str(error_audit.id))
        
        db.commit()
        
        return {
            "success": True,
            "errors_logged": len(errors),
            "error_ids": error_ids,
            "message": f"Successfully logged {len(errors)} errors"
        }
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to log batch errors: {str(e)}"
        )

@router.get("/")
def get_errors(
    page: int = 1,
    limit: int = 20,
    severity: Optional[str] = None,
    error_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get error logs with pagination"""
    try:
        query = db.query(ErrorAudit)
        
        if severity:
            query = query.filter(ErrorAudit.severity == severity)
        if error_type:
            query = query.filter(ErrorAudit.error_type == error_type)
        
        offset = (page - 1) * limit
        errors = query.order_by(ErrorAudit.created_at.desc()).offset(offset).limit(limit).all()
        
        return {
            "errors": [
                {
                    "id": str(error.id),
                    "error_type": error.error_type,
                    "severity": error.severity,
                    "source": error.source,
                    "error_message": error.error_message,
                    "endpoint": error.endpoint,
                    "created_at": error.created_at.isoformat()
                }
                for error in errors
            ],
            "page": page,
            "limit": limit
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch errors: {str(e)}"
        )