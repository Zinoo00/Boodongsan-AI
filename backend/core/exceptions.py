"""
Custom exception hierarchy for Korean Real Estate RAG AI Chatbot
Provides structured error handling with proper context and logging
"""

import logging
from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    """Standardized error codes"""
    
    # Configuration errors
    CONFIG_VALIDATION_ERROR = "CONFIG_VALIDATION_ERROR"
    CONFIG_MISSING_REQUIRED = "CONFIG_MISSING_REQUIRED"
    
    # Database errors
    DATABASE_CONNECTION_ERROR = "DATABASE_CONNECTION_ERROR"
    DATABASE_QUERY_ERROR = "DATABASE_QUERY_ERROR"
    DATABASE_TRANSACTION_ERROR = "DATABASE_TRANSACTION_ERROR"
    
    # Cache errors
    CACHE_CONNECTION_ERROR = "CACHE_CONNECTION_ERROR"
    CACHE_OPERATION_ERROR = "CACHE_OPERATION_ERROR"
    
    # AI Service errors
    AI_SERVICE_UNAVAILABLE = "AI_SERVICE_UNAVAILABLE"
    AI_RATE_LIMIT_EXCEEDED = "AI_RATE_LIMIT_EXCEEDED"
    AI_INVALID_RESPONSE = "AI_INVALID_RESPONSE"
    AI_TIMEOUT = "AI_TIMEOUT"
    
    # Vector Service errors
    VECTOR_CONNECTION_ERROR = "VECTOR_CONNECTION_ERROR"
    VECTOR_INDEX_ERROR = "VECTOR_INDEX_ERROR"
    VECTOR_SEARCH_ERROR = "VECTOR_SEARCH_ERROR"
    
    # RAG Service errors
    RAG_CONTEXT_ERROR = "RAG_CONTEXT_ERROR"
    RAG_PROCESSING_ERROR = "RAG_PROCESSING_ERROR"
    
    # External API errors
    EXTERNAL_API_ERROR = "EXTERNAL_API_ERROR"
    EXTERNAL_API_RATE_LIMIT = "EXTERNAL_API_RATE_LIMIT"
    EXTERNAL_API_TIMEOUT = "EXTERNAL_API_TIMEOUT"
    
    # Validation errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"
    
    # User errors
    USER_NOT_FOUND = "USER_NOT_FOUND"
    USER_UNAUTHORIZED = "USER_UNAUTHORIZED"
    USER_FORBIDDEN = "USER_FORBIDDEN"
    
    # Property errors
    PROPERTY_NOT_FOUND = "PROPERTY_NOT_FOUND"
    PROPERTY_INVALID_FILTER = "PROPERTY_INVALID_FILTER"
    
    # Policy errors
    POLICY_NOT_FOUND = "POLICY_NOT_FOUND"
    POLICY_MATCH_ERROR = "POLICY_MATCH_ERROR"
    
    # Generic errors
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"


class BaseAppException(Exception):
    """Base application exception with structured error information"""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
        correlation_id: str | None = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.cause = cause
        self.correlation_id = correlation_id
        
        super().__init__(self.message)
        
        # Log the exception
        self._log_exception()
    
    def _log_exception(self):
        """Log the exception with appropriate level"""
        logger = logging.getLogger(self.__class__.__module__)
        
        log_data = {
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details,
            "correlation_id": self.correlation_id
        }
        
        if self.cause:
            log_data["cause"] = str(self.cause)
        
        if isinstance(self, (ConfigurationError, ValidationError)):
            logger.error("Application error: %s", log_data)
        elif isinstance(self, ExternalServiceError):
            logger.warning("External service error: %s", log_data)
        else:
            logger.error("Unhandled application error: %s", log_data, exc_info=True)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details,
            "correlation_id": self.correlation_id
        }


class ConfigurationError(BaseAppException):
    """Configuration-related errors"""
    
    def __init__(self, message: str, field_name: str | None = None, **kwargs):
        details = kwargs.pop("details", {})
        if field_name:
            details["field_name"] = field_name
        
        super().__init__(
            message=message,
            error_code=kwargs.pop("error_code", ErrorCode.CONFIG_VALIDATION_ERROR),
            details=details,
            **kwargs
        )


class DatabaseError(BaseAppException):
    """Database operation errors"""
    
    def __init__(self, message: str, operation: str | None = None, **kwargs):
        details = kwargs.pop("details", {})
        if operation:
            details["operation"] = operation
        
        super().__init__(
            message=message,
            error_code=kwargs.pop("error_code", ErrorCode.DATABASE_CONNECTION_ERROR),
            details=details,
            **kwargs
        )


class CacheError(BaseAppException):
    """Cache operation errors"""
    
    def __init__(self, message: str, operation: str | None = None, **kwargs):
        details = kwargs.pop("details", {})
        if operation:
            details["operation"] = operation
        
        super().__init__(
            message=message,
            error_code=kwargs.pop("error_code", ErrorCode.CACHE_CONNECTION_ERROR),
            details=details,
            **kwargs
        )


class AIServiceError(BaseAppException):
    """AI service errors"""
    
    def __init__(
        self, 
        message: str, 
        provider: str | None = None,
        model: str | None = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if provider:
            details["provider"] = provider
        if model:
            details["model"] = model
        
        super().__init__(
            message=message,
            error_code=kwargs.pop("error_code", ErrorCode.AI_SERVICE_UNAVAILABLE),
            details=details,
            **kwargs
        )


class VectorServiceError(BaseAppException):
    """Vector database operation errors"""
    
    def __init__(
        self, 
        message: str, 
        collection: str | None = None,
        operation: str | None = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if collection:
            details["collection"] = collection
        if operation:
            details["operation"] = operation
        
        super().__init__(
            message=message,
            error_code=kwargs.pop("error_code", ErrorCode.VECTOR_CONNECTION_ERROR),
            details=details,
            **kwargs
        )


class RAGServiceError(BaseAppException):
    """RAG processing errors"""
    
    def __init__(
        self, 
        message: str, 
        stage: str | None = None,
        user_id: str | None = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if stage:
            details["stage"] = stage
        if user_id:
            details["user_id"] = user_id
        
        super().__init__(
            message=message,
            error_code=kwargs.pop("error_code", ErrorCode.RAG_PROCESSING_ERROR),
            details=details,
            **kwargs
        )


class ExternalServiceError(BaseAppException):
    """External API errors"""
    
    def __init__(
        self, 
        message: str, 
        service_name: str | None = None,
        status_code: int | None = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if service_name:
            details["service_name"] = service_name
        if status_code:
            details["status_code"] = status_code
        
        super().__init__(
            message=message,
            error_code=kwargs.pop("error_code", ErrorCode.EXTERNAL_API_ERROR),
            details=details,
            **kwargs
        )


class ValidationError(BaseAppException):
    """Input validation errors"""
    
    def __init__(
        self, 
        message: str, 
        field_name: str | None = None,
        field_value: Any | None = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if field_name:
            details["field_name"] = field_name
        if field_value is not None:
            details["field_value"] = str(field_value)
        
        super().__init__(
            message=message,
            error_code=kwargs.pop("error_code", ErrorCode.VALIDATION_ERROR),
            details=details,
            **kwargs
        )


class BusinessLogicError(BaseAppException):
    """Business rule violation errors"""
    
    def __init__(self, message: str, rule: str | None = None, **kwargs):
        details = kwargs.pop("details", {})
        if rule:
            details["business_rule"] = rule
        
        super().__init__(
            message=message,
            error_code=kwargs.pop("error_code", ErrorCode.BUSINESS_RULE_VIOLATION),
            details=details,
            **kwargs
        )


class UserError(BaseAppException):
    """User-related errors"""
    
    def __init__(
        self, 
        message: str, 
        user_id: str | None = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if user_id:
            details["user_id"] = user_id
        
        super().__init__(
            message=message,
            error_code=kwargs.pop("error_code", ErrorCode.USER_NOT_FOUND),
            details=details,
            **kwargs
        )


class PropertyError(BaseAppException):
    """Property-related errors"""
    
    def __init__(
        self, 
        message: str, 
        property_id: str | None = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if property_id:
            details["property_id"] = property_id
        
        super().__init__(
            message=message,
            error_code=kwargs.pop("error_code", ErrorCode.PROPERTY_NOT_FOUND),
            details=details,
            **kwargs
        )


class PolicyError(BaseAppException):
    """Policy-related errors"""
    
    def __init__(
        self, 
        message: str, 
        policy_id: str | None = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if policy_id:
            details["policy_id"] = policy_id
        
        super().__init__(
            message=message,
            error_code=kwargs.pop("error_code", ErrorCode.POLICY_NOT_FOUND),
            details=details,
            **kwargs
        )


# Utility functions for error handling

def handle_database_error(operation: str):
    """Decorator for database operations"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                raise DatabaseError(
                    message=f"Database operation failed: {operation}",
                    operation=operation,
                    cause=e
                )
        return wrapper
    return decorator


def handle_external_api_error(service_name: str):
    """Decorator for external API calls"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                raise ExternalServiceError(
                    message=f"External service error: {service_name}",
                    service_name=service_name,
                    cause=e
                )
        return wrapper
    return decorator


def validate_required_fields(data: dict[str, Any], required_fields: list):
    """Validate required fields in data"""
    missing_fields = []
    for field in required_fields:
        if field not in data or data[field] is None or data[field] == "":
            missing_fields.append(field)
    
    if missing_fields:
        raise ValidationError(
            message=f"Missing required fields: {', '.join(missing_fields)}",
            details={"missing_fields": missing_fields}
        )


def safe_execute(func, default_value=None, error_class=BaseAppException):
    """Safely execute a function with error handling"""
    try:
        return func()
    except error_class:
        raise
    except Exception as e:
        logging.getLogger(__name__).error(f"Unexpected error in {func.__name__}: {str(e)}")
        return default_value