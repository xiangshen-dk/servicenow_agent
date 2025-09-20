import httpx
import json
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin

from .settings import ServiceNowSettings
from .servicenow import CRUDResponse


logger = logging.getLogger(__name__)


class ServiceNowClient:
    """Client for interacting with ServiceNow REST API."""
    
    def __init__(self, settings: ServiceNowSettings):
        self.settings = settings
        self.base_url = settings.instance_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=settings.api_timeout)
        logger.info(f"ServiceNow client initialized for instance: {self.base_url}")

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    def _get_auth_headers(self, access_token: str) -> Dict[str, str]:
        """Get headers for authentication."""
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _build_url(self, table: str, sys_id: Optional[str] = None) -> str:
        """Build the API URL for a given table and optional sys_id."""
        url = f"{self.base_url}/api/now/table/{table}"
        if sys_id:
            url = f"{url}/{sys_id}"
        return url
    
    def _validate_table(self, table: str) -> bool:
        """Check if the table is in the allowed tables list."""
        is_valid = table.lower() in [t.lower() for t in self.settings.allowed_tables]
        if not is_valid:
            logger.warning(f"Table '{table}' is not in allowed tables: {self.settings.allowed_tables}")
        return is_valid
    
    async def create_record(
        self,
        table: str,
        data: Dict[str, Any],
        access_token: str,
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
            headers = self._get_auth_headers(access_token)
            response = await self._client.post(
                url,
                json=data,
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            result = response.json().get("result", {})
            return CRUDResponse(
                success=True,
                operation="create",
                table=table,
                message=f"Record created successfully in {table}",
                data=[result],
                count=1
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error creating record: {e.response.text}")
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
        access_token: str,
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
            query_parts = []
            for key, value in query.items():
                if any(op in key for op in ['>=', '<=', '>', '<', '!=']):
                    query_parts.append(f"{key}{value}")
                elif isinstance(value, str) and value.startswith(('>=', '<=', '>', '<', '!=')):
                    query_parts.append(f"{key}{value}")
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
            headers = self._get_auth_headers(access_token)
            response = await self._client.get(
                url,
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            records = response.json().get("result", [])
            return CRUDResponse(
                success=True,
                operation="read",
                table=table,
                message=f"Retrieved {len(records)} record(s) from {table}",
                data=records,
                count=len(records)
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error reading records: {e.response.text}")
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
        access_token: str,
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
            headers = self._get_auth_headers(access_token)
            response = await self._client.patch(
                url,
                json=data,
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            updated_record = response.json().get("result", {})
            return CRUDResponse(
                success=True,
                operation="update",
                table=table,
                message=f"Record {sys_id} updated successfully in {table}",
                data=[updated_record],
                count=1
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error updating record: {e.response.text}")
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
        sys_id: str,
        access_token: str
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
            headers = self._get_auth_headers(access_token)
            response = await self._client.delete(
                url,
                headers=headers
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
            logger.error(f"HTTP error deleting record: {e.response.text}")
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