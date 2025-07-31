import asyncio
import logging
import json
from typing import Dict, Any, Optional

from google.adk.tools import FunctionTool

from .servicenow_client import ServiceNowClient
from ..config import ServiceNowSettings
from ..models import CRUDRequest, CRUDResponse


logger = logging.getLogger(__name__)


def create_servicenow_tool(settings: ServiceNowSettings) -> FunctionTool:
    """Factory function to create a ServiceNow tool instance."""
    client = ServiceNowClient(settings)
    
    async def servicenow_crud(
        operation: str,
        table: str,
        sys_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, Any]] = None,
        fields: Optional[list[str]] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Perform Create, Read, Update, and Delete operations on ServiceNow records.
        
        Args:
            operation: The CRUD operation to perform (create, read, update, delete)
            table: The ServiceNow table to operate on (e.g., 'incident', 'change_request')
            sys_id: The sys_id of the record (required for update and delete operations)
            data: Data for create or update operations
            query: Query parameters for read operations. Supports operators:
                   - Exact match: {'state': '1', 'assigned_to': 'user123'}
                   - Not equal: {'state': '!=6'} 
                   - Greater/Less than: {'priority': '>2', 'opened_at': '>=2025-06-01'}
                   - Date ranges: {'opened_at': 'BETWEEN2025-06-01@2025-07-31'}
            fields: Fields to return in the response
            limit: Maximum number of records to return (for read operations)
        
        Returns:
            Dict containing the operation result
        """
        try:
            # Handle JSON strings that might be passed instead of dictionaries
            if isinstance(query, str):
                try:
                    query = json.loads(query)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse query as JSON: {query}")
                    
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse data as JSON: {data}")
            
            # Validate and parse the request
            request = CRUDRequest(
                operation=operation,
                table=table,
                sys_id=sys_id,
                data=data,
                query=query,
                fields=fields,
                limit=limit
            )
            
            # Perform the operation
            if request.operation == "create":
                if not request.data:
                    raise ValueError("'data' is required for create operations")
                response = await client.create_record(
                    table=request.table,
                    data=request.data,
                    fields=request.fields
                )
            
            elif request.operation == "read":
                response = await client.read_records(
                    table=request.table,
                    query=request.query,
                    fields=request.fields,
                    limit=request.limit
                )
            
            elif request.operation == "update":
                if not request.sys_id:
                    raise ValueError("'sys_id' is required for update operations")
                if not request.data:
                    raise ValueError("'data' is required for update operations")
                response = await client.update_record(
                    table=request.table,
                    sys_id=request.sys_id,
                    data=request.data,
                    fields=request.fields
                )
            
            elif request.operation == "delete":
                if not request.sys_id:
                    raise ValueError("'sys_id' is required for delete operations")
                response = await client.delete_record(
                    table=request.table,
                    sys_id=request.sys_id
                )
            
            else:
                raise ValueError(f"Invalid operation: {request.operation}")
            
            # Return the result
            if response.success:
                return response.dict()
            else:
                raise RuntimeError(response.error or "Operation failed")
        
        except Exception as e:
            logger.error(f"Error in ServiceNow tool: {e}")
            raise RuntimeError(f"ServiceNow operation failed: {str(e)}")
    
    # Create and return the FunctionTool
    return FunctionTool(servicenow_crud)
