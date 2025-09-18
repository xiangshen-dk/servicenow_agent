"""
Secure settings module with improved password handling and validation.
"""
from typing import Any, Optional, List, Union
from pydantic_settings import BaseSettings
from pydantic import Field, SecretStr, field_validator, validator
import os
import logging
from contextlib import contextmanager

# Configure logger without exposing sensitive data
logger = logging.getLogger(__name__)
logger.addFilter(lambda record: not any(
    sensitive in str(record.msg).lower() 
    for sensitive in ['password', 'secret', 'token', 'key']
))


class SecureServiceNowSettings(BaseSettings):
    """ServiceNow configuration with enhanced security."""
    
    instance_url: str = Field(
        default="https://ven04789.service-now.com",
        description="ServiceNow instance URL"
    )
    username: str = Field(
        ...,
        description="ServiceNow username for API access"
    )
    password: Optional[SecretStr] = Field(
        default=None,
        description="ServiceNow password for API access"
    )
    
    # Tables configuration with validation
    allowed_tables: Union[List[str], str] = Field(
        default=[
            "incident",
            "change_request",
            "problem",
            "sc_task",
            "sc_req_item",
            "cmdb_ci",
        ],
        description="List of ServiceNow tables the agent can interact with"
    )
    
    # API configuration with sensible limits
    api_timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="API request timeout in seconds (5-120)"
    )
    max_records: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum records per query (1-1000)"
    )
    
    # Retry configuration
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retry attempts"
    )
    retry_delay: float = Field(
        default=1.0,
        ge=0.1,
        le=30.0,
        description="Initial retry delay in seconds"
    )
    
    def __init__(self, **kwargs):
        """Initialize with secure password retrieval."""
        super().__init__(**kwargs)
        
        if not self.password:
            self.password = self._get_password_securely()
    
    def _get_password_securely(self) -> Optional[SecretStr]:
        """Securely retrieve password from Secret Manager or environment."""
        # Try Secret Manager first
        password_value = self._fetch_from_secret_manager()
        
        if password_value:
            logger.info("Password retrieved from Secret Manager")
            return SecretStr(password_value)
        
        # Fall back to environment variable
        env_password = os.getenv("SERVICENOW_PASSWORD")
        if env_password:
            logger.info("Password retrieved from environment variable")
            return SecretStr(env_password)
        
        logger.error("ServiceNow password not found in any source")
        raise ValueError(
            "ServiceNow password not found. Please set SERVICENOW_PASSWORD "
            "environment variable or configure Secret Manager."
        )
    
    @contextmanager
    def _get_secret_manager_client(self):
        """Context manager for Secret Manager client."""
        from google.cloud import secretmanager
        client = None
        try:
            client = secretmanager.SecretManagerServiceClient()
            yield client
        finally:
            if client:
                # Properly close the client to release resources
                try:
                    client.close()
                except Exception as e:
                    logger.debug(f"Error closing Secret Manager client: {e}")
    
    def _fetch_from_secret_manager(self) -> Optional[str]:
        """Fetch password from Google Secret Manager with proper resource management."""
        try:
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
            if not project_id:
                logger.debug("GOOGLE_CLOUD_PROJECT not set")
                return None
            
            with self._get_secret_manager_client() as client:
                secret_name = f"projects/{project_id}/secrets/servicenow-password-prod/versions/latest"
                
                try:
                    response = client.access_secret_version(request={"name": secret_name})
                    return response.payload.data.decode("UTF-8")
                except Exception as e:
                    logger.debug(f"Secret Manager access failed: {type(e).__name__}")
                    return None
                    
        except ImportError:
            logger.debug("Google Cloud Secret Manager library not available")
            return None
        except Exception as e:
            logger.debug(f"Unexpected error accessing Secret Manager: {type(e).__name__}")
            return None
    
    @field_validator('allowed_tables', mode='before')
    @classmethod
    def parse_and_validate_tables(cls, v):
        """Parse and validate allowed tables."""
        if isinstance(v, str):
            tables = [table.strip() for table in v.split(',') if table.strip()]
        else:
            tables = v
        
        # Validate table names (alphanumeric and underscore only)
        import re
        valid_pattern = re.compile(r'^[a-zA-Z0-9_]+$')
        
        for table in tables:
            if not valid_pattern.match(table):
                raise ValueError(
                    f"Invalid table name '{table}'. "
                    "Table names must contain only letters, numbers, and underscores."
                )
        
        return tables
    
    @field_validator('instance_url')
    @classmethod
    def validate_instance_url(cls, v):
        """Validate ServiceNow instance URL."""
        if not v.startswith(('https://', 'http://')):
            raise ValueError("Instance URL must start with https:// or http://")
        
        # Remove trailing slash for consistency
        return v.rstrip('/')
    
    class Config:
        env_prefix = "SERVICENOW_"
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"
        
        # Hide sensitive fields in string representation
        json_encoders = {
            SecretStr: lambda v: "***HIDDEN***" if v else None
        }


class SecureAgentSettings(BaseSettings):
    """Agent configuration with validation."""
    
    agent_name: str = Field(
        default="ServiceNow_Agent",
        pattern=r'^[a-zA-Z][a-zA-Z0-9_]*$',
        description="Agent name (valid identifier)"
    )
    agent_description: str = Field(
        default="An AI agent for managing ServiceNow records through natural language",
        max_length=500,
        description="Agent description"
    )
    model: str = Field(
        default="gemini-2.5-flash",
        description="Google AI model to use"
    )
    
    # Logging configuration
    log_level: str = Field(
        default="INFO",
        pattern=r'^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$',
        description="Logging level"
    )
    
    class Config:
        env_prefix = "AGENT_"
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"
