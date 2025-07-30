import httpx
import json
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin

from ..config import ServiceNowSettings
from ..models import CRUDResponse


logger = logging.getLogger(__name__)


class ServiceNowClient:
    """Client for interacting with ServiceNow REST API."""
    
    def __init__(self, settings: ServiceNowSettings):
        self.settings = settings
        self.base_url = settings.instance_url.rstrip("/")
        self.auth = (settings.username, settings.password.get_secret_value())
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    def _build_url(self, table: str, sys_id: Optional[str] = None) -> str:
        """Build the API URL for a given table and optional sys_id."""
        url = f"{self.base_url}/api/now/table/{table}"
        if sys_id:
            url = f"{url}/{sys_id}"
        return url
    
    def _validate_table(self, table: str) -> bool:
        """Check if the table is in the allowed tables list."""
        return table.lower() in [t.lower() for t in self.settings.allowed_tables]
    
    async def create_record(
        self,
        table: str,
        data: Dict[str, Any],
        fields: Optional[List[str]] = None
    ) -> CRUDResponse:
        """Create a new record in ServiceNow."""
        if not self._validate_table(table):
            return CRUDResponse(
                success=False,
                operation="create",
                table=table,
                error=f"Table '{table}' is not in the allowed tables list"
            )
        
        url = self._build_url(table)
        params = {}
        if fields:
            params["sysparm_fields"] = ",".join(fields)
        
        try:
            async with httpx.AsyncClient(timeout=self.settings.api_timeout) as client:
                response = await client.post(
                    url,
                    json=data,
                    auth=self.auth,
                    headers=self.headers,
                    params=params
                )
                response.raise_for_status()
                
                result = response.json()
                return CRUDResponse(
                    success=True,
                    operation="create",
                    table=table,
                    message=f"Record created successfully in {table}",
                    data=[result.get("result", {})],
                    count=1
                )
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error creating record: {e}")
            return CRUDResponse(
                success=False,
                operation="create",
                table=table,
                error=f"HTTP {e.response.status_code}: {e.response.text}"
            )
        except Exception as e:
            logger.error(f"Error creating record: {e}")
            return CRUDResponse(
                success=False,
                operation="create",
                table=table,
                error=str(e)
            )
    
    async def read_records(
        self,
        table: str,
        query: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> CRUDResponse:
        """Read records from ServiceNow."""
        if not self._validate_table(table):
            return CRUDResponse(
                success=False,
                operation="read",
                table=table,
                error=f"Table '{table}' is not in the allowed tables list"
            )
        
        url = self._build_url(table)
        params = {}
        
        if query:
            # Build query string
            query_parts = []
            for key, value in query.items():
                # Support operators in the key (e.g., "opened_at>=2025-06-01")
                if any(op in key for op in ['>=', '<=', '>', '<', '!=']):
                    query_parts.append(f"{key}{value}")
                # Support special query syntax in value (e.g., {"state": "!=6"})
                elif isinstance(value, str) and value.startswith(('>=', '<=', '>', '<', '!=')):
                    query_parts.append(f"{key}{value}")
                # Support BETWEEN queries (e.g., {"opened_at": "BETWEEN2025-06-01@2025-07-31"})
                elif isinstance(value, str) and value.upper().startswith('BETWEEN'):
                    query_parts.append(f"{key}{value}")
                else:
                    query_parts.append(f"{key}={value}")
            params["sysparm_query"] = "^".join(query_parts)
        
        if fields:
            params["sysparm_fields"] = ",".join(fields)
        
        if limit:
            params["sysparm_limit"] = min(limit, self.settings.max_records)
        else:
            params["sysparm_limit"] = self.settings.max_records
        
        try:
            async with httpx.AsyncClient(timeout=self.settings.api_timeout) as client:
                response = await client.get(
                    url,
                    auth=self.auth,
                    headers=self.headers,
                    params=params
                )
                response.raise_for_status()
                
                result = response.json()
                records = result.get("result", [])
                
                return CRUDResponse(
                    success=True,
                    operation="read",
                    table=table,
                    message=f"Retrieved {len(records)} record(s) from {table}",
                    data=records,
                    count=len(records)
                )
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error reading records: {e}")
            return CRUDResponse(
                success=False,
                operation="read",
                table=table,
                error=f"HTTP {e.response.status_code}: {e.response.text}"
            )
        except Exception as e:
            logger.error(f"Error reading records: {e}")
            return CRUDResponse(
                success=False,
                operation="read",
                table=table,
                error=str(e)
            )
    
    async def update_record(
        self,
        table: str,
        sys_id: str,
        data: Dict[str, Any],
        fields: Optional[List[str]] = None
    ) -> CRUDResponse:
        """Update an existing record in ServiceNow."""
        if not self._validate_table(table):
            return CRUDResponse(
                success=False,
                operation="update",
                table=table,
                error=f"Table '{table}' is not in the allowed tables list"
            )
        
        url = self._build_url(table, sys_id)
        params = {}
        if fields:
            params["sysparm_fields"] = ",".join(fields)
        
        try:
            async with httpx.AsyncClient(timeout=self.settings.api_timeout) as client:
                response = await client.patch(
                    url,
                    json=data,
                    auth=self.auth,
                    headers=self.headers,
                    params=params
                )
                response.raise_for_status()
                
                result = response.json()
                return CRUDResponse(
                    success=True,
                    operation="update",
                    table=table,
                    message=f"Record {sys_id} updated successfully in {table}",
                    data=[result.get("result", {})],
                    count=1
                )
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error updating record: {e}")
            return CRUDResponse(
                success=False,
                operation="update",
                table=table,
                error=f"HTTP {e.response.status_code}: {e.response.text}"
            )
        except Exception as e:
            logger.error(f"Error updating record: {e}")
            return CRUDResponse(
                success=False,
                operation="update",
                table=table,
                error=str(e)
            )
    
    async def delete_record(
        self,
        table: str,
        sys_id: str
    ) -> CRUDResponse:
        """Delete a record from ServiceNow."""
        if not self._validate_table(table):
            return CRUDResponse(
                success=False,
                operation="delete",
                table=table,
                error=f"Table '{table}' is not in the allowed tables list"
            )
        
        url = self._build_url(table, sys_id)
        
        try:
            async with httpx.AsyncClient(timeout=self.settings.api_timeout) as client:
                response = await client.delete(
                    url,
                    auth=self.auth,
                    headers=self.headers
                )
                response.raise_for_status()
                
                return CRUDResponse(
                    success=True,
                    operation="delete",
                    table=table,
                    message=f"Record {sys_id} deleted successfully from {table}",
                    count=1
                )
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error deleting record: {e}")
            return CRUDResponse(
                success=False,
                operation="delete",
                table=table,
                error=f"HTTP {e.response.status_code}: {e.response.text}"
            )
        except Exception as e:
            logger.error(f"Error deleting record: {e}")
            return CRUDResponse(
                success=False,
                operation="delete",
                table=table,
                error=str(e)
            )
