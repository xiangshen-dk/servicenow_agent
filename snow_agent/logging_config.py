"""
Centralized logging configuration for ServiceNow agent.
"""
import logging
import sys
import os
from typing import Optional
import json
from datetime import datetime


class SensitiveDataFilter(logging.Filter):
    """Filter to prevent sensitive data from being logged."""
    
    SENSITIVE_PATTERNS = [
        'password', 'secret', 'token', 'key', 'auth',
        'credential', 'api_key', 'access_token', 'refresh_token'
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out log records containing sensitive information."""
        # Check the message
        message = str(record.getMessage()).lower()
        
        # Check for sensitive patterns in the message
        for pattern in self.SENSITIVE_PATTERNS:
            if pattern in message:
                # Mask the sensitive parts
                record.msg = self._mask_sensitive_data(record.msg)
        
        # Check args if present
        if hasattr(record, 'args') and record.args:
            record.args = self._mask_args(record.args)
        
        return True
    
    def _mask_sensitive_data(self, text: str) -> str:
        """Mask sensitive data in text."""
        if not isinstance(text, str):
            text = str(text)
        
        # Replace common patterns
        import re
        
        # Mask passwords in URLs
        text = re.sub(
            r'(https?://[^:]+:)([^@]+)(@)',
            r'\1***MASKED***\3',
            text
        )
        
        # Mask values after sensitive keys
        for pattern in self.SENSITIVE_PATTERNS:
            text = re.sub(
                rf'({pattern}["\']?\s*[:=]\s*["\']?)([^"\',\s}}]+)',
                r'\1***MASKED***',
                text,
                flags=re.IGNORECASE
            )
        
        return text
    
    def _mask_args(self, args):
        """Mask sensitive data in log arguments."""
        if isinstance(args, dict):
            masked = {}
            for key, value in args.items():
                if any(pattern in key.lower() for pattern in self.SENSITIVE_PATTERNS):
                    masked[key] = "***MASKED***"
                else:
                    masked[key] = value
            return masked
        elif isinstance(args, (list, tuple)):
            return tuple(
                "***MASKED***" if any(
                    pattern in str(arg).lower() 
                    for pattern in self.SENSITIVE_PATTERNS
                ) else arg
                for arg in args
            )
        return args


class StructuredFormatter(logging.Formatter):
    """Formatter for structured logging output."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON for production."""
        log_obj = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_obj['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_obj['extra'] = record.extra_fields
        
        return json.dumps(log_obj)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for development/debugging."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        """Add color to log output for better readability."""
        if record.levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
            )
        return super().format(record)


def setup_logging(
    log_level: Optional[str] = None,
    log_format: Optional[str] = None,
    use_structured: bool = False,
    use_colors: bool = True
) -> None:
    """
    Configure logging for the ServiceNow agent.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format string for logs
        use_structured: Use structured JSON logging (for production)
        use_colors: Use colored output (for development)
    """
    # Determine log level
    if log_level is None:
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # Validate log level
    if log_level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
        log_level = 'INFO'
    
    # Determine if we're in production
    is_production = os.getenv('ENVIRONMENT', 'development').lower() == 'production'
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    
    # Add sensitive data filter
    sensitive_filter = SensitiveDataFilter()
    console_handler.addFilter(sensitive_filter)
    
    # Set formatter based on environment
    if use_structured or is_production:
        formatter = StructuredFormatter()
    else:
        if log_format is None:
            log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        if use_colors and not is_production:
            formatter = ColoredFormatter(log_format)
        else:
            formatter = logging.Formatter(log_format)
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Configure third-party loggers
    configure_third_party_loggers(log_level)
    
    # Log initial configuration
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured: level={log_level}, production={is_production}")


def configure_third_party_loggers(log_level: str) -> None:
    """Configure logging levels for third-party libraries."""
    # Reduce noise from HTTP libraries
    noisy_loggers = [
        'httpx',
        'httpcore',
        'urllib3',
        'asyncio',
        'google.auth',
        'google.api_core'
    ]
    
    for logger_name in noisy_loggers:
        logger = logging.getLogger(logger_name)
        # Set to WARNING unless we're in DEBUG mode
        if log_level == 'DEBUG':
            logger.setLevel(logging.INFO)
        else:
            logger.setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the sensitive data filter applied.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Ensure sensitive data filter is applied
    if not any(isinstance(f, SensitiveDataFilter) for f in logger.filters):
        logger.addFilter(SensitiveDataFilter())
    
    return logger


class LogContext:
    """Context manager for adding contextual information to logs."""
    
    def __init__(self, logger: logging.Logger, **context):
        self.logger = logger
        self.context = context
        self.old_factory = None
    
    def __enter__(self):
        """Enter the context and add contextual information."""
        old_factory = logging.getLogRecordFactory()
        context = self.context
        
        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.extra_fields = context
            return record
        
        logging.setLogRecordFactory(record_factory)
        self.old_factory = old_factory
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context and restore the original factory."""
        if self.old_factory:
            logging.setLogRecordFactory(self.old_factory)


# Don't initialize logging on module import to avoid side effects
# Call setup_logging() explicitly when needed
