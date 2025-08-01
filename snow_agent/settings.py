from typing import Any, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, SecretStr, field_validator
import os
import logging

logger = logging.getLogger(__name__)


class ServiceNowSettings(BaseSettings):
    """ServiceNow configuration settings."""
    
    instance_url: str = Field(
        ...,
        description="ServiceNow instance URL (e.g., https://dev123456.service-now.com)"
    )
    username: str = Field(
        ...,
        description="ServiceNow username for API access"
    )
    password: SecretStr = Field(
        default=None,
        description="ServiceNow password for API access"
    )
    
    def __init__(self, **kwargs):
        """Initialize settings, fetching password from Secret Manager if needed."""
        super().__init__(**kwargs)
        
        # If password is not set, try to fetch from Secret Manager
        if not self.password:
            password_value = self._get_password_from_secret_manager()
            if password_value:
                self.password = SecretStr(password_value)
            else:
                # Fall back to environment variable
                env_password = os.getenv("SERVICENOW_PASSWORD")
                if env_password:
                    self.password = SecretStr(env_password)
                else:
                    raise ValueError("ServiceNow password not found in Secret Manager or environment variables")
    
    def _get_password_from_secret_manager(self) -> Optional[str]:
        """Fetch password from Google Secret Manager."""
        try:
            from google.cloud import secretmanager
            
            # Get project ID from environment
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
            if not project_id:
                logger.warning("GOOGLE_CLOUD_PROJECT not set, cannot fetch from Secret Manager")
                return None
            
            # Create the Secret Manager client
            client = secretmanager.SecretManagerServiceClient()
            
            # Build the resource name of the secret
            secret_name = f"projects/{project_id}/secrets/servicenow-password/versions/latest"
            
            # Access the secret version
            response = client.access_secret_version(request={"name": secret_name})
            
            # Return the decoded payload
            password = response.payload.data.decode("UTF-8")
            logger.info("Successfully retrieved ServiceNow password from Secret Manager")
            return password
            
        except Exception as e:
            logger.warning(f"Could not fetch password from Secret Manager: {e}")
            return None
    
    # Tables configuration
    allowed_tables: list[str] | str = Field(
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
    
    @field_validator('allowed_tables', mode='before')
    @classmethod
    def parse_allowed_tables(cls, v):
        if isinstance(v, str):
            return [table.strip() for table in v.split(',') if table.strip()]
        return v
    
    # API configuration
    api_timeout: int = Field(
        default=30,
        description="API request timeout in seconds"
    )
    max_records: int = Field(
        default=100,
        description="Maximum number of records to return in a single query"
    )
    
    class Config:
        env_prefix = "SERVICENOW_"
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


class AgentSettings(BaseSettings):
    """Agent configuration settings."""
    
    agent_name: str = Field(
        default="ServiceNow_Agent",
        description="Display name for the agent (must be a valid identifier)"
    )
    agent_description: str = Field(
        default="An AI agent for managing ServiceNow records through natural language",
        description="Agent description"
    )
    model: str = Field(
        default="gemini-2.5-flash",
        description="Google AI model to use"
    )
    
    class Config:
        env_prefix = "AGENT_"
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env
