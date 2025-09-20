import logging
import json
from typing import Dict, Any, Optional

from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext

from .servicenow_client import ServiceNowClient
from .settings import ServiceNowSettings, AgentSettings
from .servicenow import CRUDRequest, CRUDResponse
from .logging_config import LogContext, get_logger


logger = get_logger(__name__)


def create_servicenow_tool(settings: ServiceNowSettings) -> FunctionTool:
    """Factory function to create a ServiceNow tool instance."""
    logger.info("Creating ServiceNow tool with configured settings")
    
    async def servicenow_crud(
        operation: str,
        table: str,
        tool_context: ToolContext,
        sys_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, Any]] = None,
        fields: Optional[list[str]] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Perform Create, Read, Update, and Delete operations on ServiceNow records.
        
        Args:
            operation: The operation to perform (create, read, update, delete)
            table: The ServiceNow table to operate on (e.g., 'incident', 'change_request')
            tool_context: The context containing authentication information.
            sys_id: The sys_id of the record (required for update and delete operations)
            data: Data for create or update operations
            query: Query parameters for read operations.
            fields: Fields to return in the response
            limit: Maximum number of records to return (for read operations)
        
        Returns:
            Dict containing the operation result
        """
        # Load AgentSettings at runtime to ensure environment variables are available
        agent_settings = AgentSettings()
        
        client = ServiceNowClient(settings)
        try:
            # Get access token from tool context
            access_token = tool_context.state.get(f"temp:{agent_settings.auth_id}")
            if not access_token:
                logger.error(f"No access token found for auth_id: {agent_settings.auth_id}")
                return {
                    "success": False,
                    "operation": operation,
                    "table": table,
                    "error": "Authentication error: Unable to retrieve access token.",
                }

            with LogContext(logger,
                           operation=operation.upper(),
                           table=table,
                           sys_id=sys_id if sys_id else None,
                           instance=settings.instance_url):
                
                logger.info(f"Starting ServiceNow {operation.upper()} operation")
                
                if isinstance(query, str):
                    query = json.loads(query)
                if isinstance(data, str):
                    data = json.loads(data)
                
                request = CRUDRequest(
                    operation=operation,
                    table=table,
                    sys_id=sys_id,
                    data=data,
                    query=query,
                    fields=fields,
                    limit=limit
                )
                
                if request.operation == "create":
                    if not request.data:
                        raise ValueError("'data' is required for create operations")
                    response = await client.create_record(
                        table=request.table,
                        data=request.data,
                        access_token=access_token,
                        fields=request.fields
                    )
                
                elif request.operation == "read":
                    response = await client.read_records(
                        table=request.table,
                        access_token=access_token,
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
                        access_token=access_token,
                        fields=request.fields
                    )
                
                elif request.operation == "delete":
                    if not request.sys_id:
                        raise ValueError("'sys_id' is required for delete operations")
                    response = await client.delete_record(
                        table=request.table,
                        sys_id=request.sys_id,
                        access_token=access_token
                    )
                
                else:
                    raise ValueError(f"Invalid operation: {request.operation}")
                
                if response.success:
                    return response.dict()
                else:
                    logger.error(f"Operation {request.operation.upper()} failed: {response.error}")
                    return {
                        "success": False,
                        "operation": request.operation,
                        "table": request.table,
                        "error": response.error or "Operation failed",
                    }
        
        except Exception as e:
            logger.error(f"Error in ServiceNow tool: {e}")
            return {
                "success": False,
                "operation": operation,
                "table": table,
                "error": str(e),
            }
        finally:
            await client.close()
    
    return FunctionTool(servicenow_crud)
