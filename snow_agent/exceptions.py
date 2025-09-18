"""
Custom exception classes for ServiceNow agent.
"""


class ServiceNowError(Exception):
    """Base exception for all ServiceNow-related errors."""
    pass


class ServiceNowClientError(ServiceNowError):
    """Exception raised for client-side errors."""
    pass


class ServiceNowAuthenticationError(ServiceNowError):
    """Exception raised when authentication fails."""
    pass


class ServiceNowRateLimitError(ServiceNowError):
    """Exception raised when rate limit is exceeded."""
    pass


class ServiceNowValidationError(ServiceNowError):
    """Exception raised for validation errors."""
    pass


class ServiceNowTimeoutError(ServiceNowError):
    """Exception raised when a request times out."""
    pass


class ServiceNowConfigurationError(ServiceNowError):
    """Exception raised for configuration errors."""
    pass


class ServiceNowConnectionError(ServiceNowError):
    """Exception raised for connection errors."""
    pass
