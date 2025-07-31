from typing import Any
from pydantic_settings import BaseSettings
from pydantic import Field, SecretStr, field_validator


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
        ...,
        description="ServiceNow password for API access"
    )
    
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
        default="gemini-2.5-flash-lite",
        description="Google AI model to use"
    )
    
    class Config:
        env_prefix = "AGENT_"
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env
