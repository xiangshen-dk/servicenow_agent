from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class ServiceNowRecord(BaseModel):
    """Base model for ServiceNow records."""
    
    sys_id: Optional[str] = Field(None, description="Unique identifier for the record")
    sys_created_on: Optional[datetime] = Field(None, description="Record creation timestamp")
    sys_updated_on: Optional[datetime] = Field(None, description="Record last update timestamp")
    sys_created_by: Optional[str] = Field(None, description="User who created the record")
    sys_updated_by: Optional[str] = Field(None, description="User who last updated the record")
    
    class Config:
        extra = "allow"  # Allow additional fields from ServiceNow


class CRUDRequest(BaseModel):
    """Model for CRUD operation requests."""
    
    operation: str = Field(..., pattern="^(create|read|update|delete)$")
    table: str = Field(..., description="ServiceNow table name")
    query: Optional[Dict[str, Any]] = Field(None, description="Query parameters for read/delete operations")
    data: Optional[Dict[str, Any]] = Field(None, description="Data for create/update operations")
    sys_id: Optional[str] = Field(None, description="Record sys_id for update/delete operations")
    fields: Optional[List[str]] = Field(None, description="Fields to return in the response")
    limit: Optional[int] = Field(None, description="Maximum number of records to return")


class CRUDResponse(BaseModel):
    """Model for CRUD operation responses."""
    
    success: bool = Field(..., description="Whether the operation was successful")
    operation: str = Field(..., description="The operation that was performed")
    table: str = Field(..., description="The ServiceNow table")
    message: Optional[str] = Field(None, description="Success or error message")
    data: Optional[List[Dict[str, Any]]] = Field(None, description="Response data from ServiceNow")
    count: Optional[int] = Field(None, description="Number of records affected/returned")
    error: Optional[str] = Field(None, description="Error details if operation failed")