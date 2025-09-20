from typing import Optional, List, Union
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class ServiceNowSettings(BaseSettings):
    """ServiceNow configuration settings."""
    
    instance_url: str = Field(
        default="https://ven04789.service-now.com",
        description="ServiceNow instance URL (e.g., https://dev123456.service-now.com)"
    )
    
    # Tables configuration
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
    
    auth_id: Optional[str] = Field(
        default=None,
        description="The ID of the GCP Authorization resource to use for authentication.",
        alias="AUTH_ID"  # Read from AUTH_ID env var directly, bypassing AGENT_ prefix
    )

    agent_version: str = Field(
        default="0.0.1",
        description="The version of the agent."
    )
    
    class Config:
        env_prefix = "AGENT_"
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env
