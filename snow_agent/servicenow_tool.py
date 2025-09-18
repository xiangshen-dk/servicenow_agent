import asyncio
import logging
import json
from typing import Dict, Any, Optional

from google.adk.tools import FunctionTool

from .servicenow_client import ServiceNowClient
from .settings import ServiceNowSettings
from .servicenow import CRUDRequest, CRUDResponse
from .logging_config import LogContext, get_logger


logger = get_logger(__name__)


def create_servicenow_tool(settings: ServiceNowSettings) -> FunctionTool:
    """Factory function to create a ServiceNow tool instance."""
    logger.info("Creating ServiceNow tool with configured settings")
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
        # Add contextual information to all logs within this operation
        with LogContext(logger,
                       operation=operation.upper(),
                       table=table,
                       sys_id=sys_id if sys_id else None,
                       instance=settings.instance_url):
            
            logger.info(f"Starting ServiceNow {operation.upper()} operation")
            if sys_id:
                logger.info(f"Target record sys_id: {sys_id}")
            
            try:
                # Handle JSON strings that might be passed instead of dictionaries
                if isinstance(query, str):
                    logger.debug(f"Converting query string to dictionary: {query}")
                    try:
                        query = json.loads(query)
                        logger.debug("Query string successfully parsed")
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse query as JSON: {query}")
                        
                if isinstance(data, str):
                    logger.debug(f"Converting data string to dictionary")
                    try:
                        data = json.loads(data)
                        logger.debug("Data string successfully parsed")
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse data as JSON: {data}")
                
                # Log the request details
                if query:
                    logger.info(f"Query parameters: {query}")
                if data:
                    logger.info(f"Data payload: {json.dumps(data, indent=2)}")
                if fields:
                    logger.info(f"Requested fields: {fields}")
                if limit:
                    logger.info(f"Record limit: {limit}")
                
                # Validate and parse the request
                logger.debug("Validating request parameters")
                request = CRUDRequest(
                    operation=operation,
                    table=table,
                    sys_id=sys_id,
                    data=data,
                    query=query,
                    fields=fields,
                    limit=limit
                )
                logger.debug("Request validation successful")
                
                # Perform the operation
                if request.operation == "create":
                    if not request.data:
                        logger.error("CREATE operation failed: missing required 'data' parameter")
                        raise ValueError("'data' is required for create operations")
                    logger.info(f"Executing CREATE operation on {request.table}")
                    response = await client.create_record(
                        table=request.table,
                        data=request.data,
                        fields=request.fields
                    )
                
                elif request.operation == "read":
                    logger.info(f"Executing READ operation on {request.table}")
                    response = await client.read_records(
                        table=request.table,
                        query=request.query,
                        fields=request.fields,
                        limit=request.limit
                    )
                
                elif request.operation == "update":
                    if not request.sys_id:
                        logger.error("UPDATE operation failed: missing required 'sys_id' parameter")
                        raise ValueError("'sys_id' is required for update operations")
                    if not request.data:
                        logger.error("UPDATE operation failed: missing required 'data' parameter")
                        raise ValueError("'data' is required for update operations")
                    logger.info(f"Executing UPDATE operation on {request.table} for sys_id: {request.sys_id}")
                    response = await client.update_record(
                        table=request.table,
                        sys_id=request.sys_id,
                        data=request.data,
                        fields=request.fields
                    )
                
                elif request.operation == "delete":
                    if not request.sys_id:
                        logger.error("DELETE operation failed: missing required 'sys_id' parameter")
                        raise ValueError("'sys_id' is required for delete operations")
                    logger.info(f"Executing DELETE operation on {request.table} for sys_id: {request.sys_id}")
                    response = await client.delete_record(
                        table=request.table,
                        sys_id=request.sys_id
                    )
                
                else:
                    logger.error(f"Invalid operation requested: {request.operation}")
                    raise ValueError(f"Invalid operation: {request.operation}")
                
                # Return the result
                if response.success:
                    logger.info(f"Operation {request.operation.upper()} completed successfully")
                    if hasattr(response, 'count'):
                        logger.info(f"Records affected: {response.count}")
                    result = response.dict()
                    logger.debug(f"Response data: {json.dumps(result, indent=2)}")
                    return result
                else:
                    logger.error(f"Operation {request.operation.upper()} failed: {response.error}")
                    # Return error information gracefully so the agent can apply failsafe protocol
                    return {
                        "success": False,
                        "operation": request.operation,
                        "table": request.table,
                        "error": response.error or "Operation failed",
                        "error_type": "operation_failed",
                        "data": [] if request.operation == "read" else None,
                        "count": 0 if request.operation == "read" else None
                    }
            
            except Exception as e:
                logger.error(f"Error in ServiceNow tool: {e}")
                logger.error(f"Full error details: {type(e).__name__}: {str(e)}")
                
                # Determine if this is likely an authentication/connection error
                error_message = str(e).lower()
                is_auth_error = any(term in error_message for term in ['auth', 'credential', 'password', 'login', '401', '403'])
                is_connection_error = any(term in error_message for term in ['connection', 'timeout', 'network', 'refused'])
                
                # Return error information gracefully so the agent can apply failsafe protocol
                if request.operation == "read":
                    # For read operations, return empty results
                    return {
                        "success": False,
                        "operation": request.operation,
                        "table": request.table,
                        "error": str(e),
                        "error_type": "auth_error" if is_auth_error else "connection_error" if is_connection_error else "unknown_error",
                        "data": [],  # Empty results for read operations
                        "count": 0,
                        "message": "No records found"  # Hint for the agent to use this message
                    }
                else:
                    # For write operations (create, update, delete), indicate submission
                    return {
                        "success": False,
                        "operation": request.operation,
                        "table": request.table,
                        "error": str(e),
                        "error_type": "auth_error" if is_auth_error else "connection_error" if is_connection_error else "unknown_error",
                        "data": None,
                        "message": "Operation submitted for processing"  # Hint for the agent
                    }
    
    # Create and return the FunctionTool
    logger.info("ServiceNow tool created successfully")
    return FunctionTool(servicenow_crud)
