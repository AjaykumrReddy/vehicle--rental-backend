import logging
import logging.config
import json
import os
from datetime import datetime
from typing import Dict, Any

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields if present
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'endpoint'):
            log_entry['endpoint'] = record.endpoint
        if hasattr(record, 'method'):
            log_entry['method'] = record.method
        if hasattr(record, 'status_code'):
            log_entry['status_code'] = record.status_code
        if hasattr(record, 'duration'):
            log_entry['duration_ms'] = record.duration
        if hasattr(record, 'error_type'):
            log_entry['error_type'] = record.error_type
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)

def setup_logging():
    """Setup logging configuration"""
    
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # Logging configuration
    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": JSONFormatter,
            },
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            },
        },
        "handlers": {
            "console": {
                "level": "INFO",
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "level": "DEBUG",
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "json",
                "filename": "logs/app.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
            },
            "error_file": {
                "level": "ERROR",
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "json",
                "filename": "logs/error.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
            },
        },
        "loggers": {
            "redi_rental": {
                "level": "DEBUG",
                "handlers": ["console", "file", "error_file"],
                "propagate": False,
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "level": "WARNING",
                "handlers": ["file"],
                "propagate": False,
            },
        },
        "root": {
            "level": "INFO",
            "handlers": ["console", "file"],
        },
    }
    
    logging.config.dictConfig(LOGGING_CONFIG)

def get_logger(name: str) -> logging.Logger:
    """Get logger instance with app prefix"""
    return logging.getLogger(f"redi_rental.{name}")

# Utility functions for structured logging
def log_api_request(logger: logging.Logger, method: str, endpoint: str, user_id: str = None, request_id: str = None):
    """Log API request"""
    logger.info(
        f"API Request: {method} {endpoint}",
        extra={
            "method": method,
            "endpoint": endpoint,
            "user_id": user_id,
            "request_id": request_id,
            "event_type": "api_request"
        }
    )

def log_api_response(logger: logging.Logger, method: str, endpoint: str, status_code: int, 
                    duration_ms: float, user_id: str = None, request_id: str = None):
    """Log API response"""
    logger.info(
        f"API Response: {method} {endpoint} - {status_code} ({duration_ms}ms)",
        extra={
            "method": method,
            "endpoint": endpoint,
            "status_code": status_code,
            "duration": duration_ms,
            "user_id": user_id,
            "request_id": request_id,
            "event_type": "api_response"
        }
    )

def log_database_operation(logger: logging.Logger, operation: str, table: str, 
                          user_id: str = None, record_id: str = None):
    """Log database operations"""
    logger.info(
        f"DB Operation: {operation} on {table}",
        extra={
            "operation": operation,
            "table": table,
            "user_id": user_id,
            "record_id": record_id,
            "event_type": "database_operation"
        }
    )

def log_business_event(logger: logging.Logger, event: str, details: Dict[str, Any] = None):
    """Log business events"""
    message = f"Business Event: {event}"
    extra = {
        "event_type": "business_event",
        "business_event": event
    }
    if details:
        extra.update(details)
    
    logger.info(message, extra=extra)

def log_error(logger: logging.Logger, error: Exception, context: Dict[str, Any] = None, operation: str = None):
    """Log errors with context"""
    import traceback
    
    extra = {
        "error_type": type(error).__name__,
        "event_type": "error",
        "error_message": str(error)
    }
    
    if operation:
        extra["operation"] = operation
    
    if context:
        extra.update(context)
    
    # Add stack trace summary for quick debugging
    stack = traceback.extract_tb(error.__traceback__)
    if stack:
        extra["error_location"] = f"{stack[-1].filename}:{stack[-1].lineno} in {stack[-1].name}"
    
    logger.error(f"Error in {operation or 'unknown operation'}: {str(error)}", extra=extra, exc_info=True)