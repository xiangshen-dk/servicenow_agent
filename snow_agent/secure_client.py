"""
Secure ServiceNow client with connection pooling, retry logic, and query sanitization.
"""
import httpx
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List, Union
from urllib.parse import urljoin, quote
from functools import wraps
import time

from .secure_settings import SecureServiceNowSettings
from .servicenow import CRUDResponse
from .exceptions import (
    ServiceNowClientError,
    ServiceNowAuthenticationError,
    ServiceNowRateLimitError,
    ServiceNowValidationError,
    ServiceNowTimeoutError
)

logger = logging.getLogger(__name__)


class QueryBuilder:
    """Secure query builder to prevent injection attacks."""
    
    VALID_OPERATORS = ['=', '!=', '>', '<', '>=', '<=', 'LIKE', 'STARTSWITH', 'ENDSWITH', 'CONTAINS', 'BETWEEN']
    
    @classmethod
    def build_query(cls, query: Optional[Dict[str, Any]]) -> str:
        """
        Build a secure query string from parameters.
        
        Args:
            query: Dictionary of query parameters
            
        Returns:
            Sanitized query string
        """
        if not query:
            return ""
        
        query_parts = []
        
        for key, value in query.items():
            # Validate field name
            if not cls._is_valid_field_name(key):
                raise ServiceNowValidationError(f"Invalid field name: {key}")
            
            # Handle different query formats
            if isinstance(value, str):
                # Check for operators in the value
                if value.upper().startswith('BETWEEN'):
                    # Handle BETWEEN queries
                    query_parts.append(cls._build_between_query(key, value))
                elif any(value.startswith(op) for op in ['>=', '<=', '>', '<', '!=']):
                    # Handle comparison operators
                    query_parts.append(cls._build_comparison_query(key, value))
                else:
                    # Standard equality
                    query_parts.append(f"{key}={cls._escape_value(value)}")
            else:
                # Convert to string and escape
                query_parts.append(f"{key}={cls._escape_value(str(value))}")
        
        return "^".join(query_parts)
    
    @staticmethod
    def _is_valid_field_name(field: str) -> bool:
        """Validate field name to prevent injection."""
        import re
        # Allow alphanumeric, underscore, and dot (for nested fields)
        return bool(re.match(r'^[a-zA-Z0-9_.]+$', field))
    
    @staticmethod
    def _escape_value(value: str) -> str:
        """Escape special characters in query values."""
        # ServiceNow uses these special characters in queries
        special_chars = {
            '^': '^^',
            '=': '^=',
            '>': '^>',
            '<': '^<',
            '!': '^!'
        }
        
        escaped = value
        for char, replacement in special_chars.items():
            escaped = escaped.replace(char, replacement)
        
        return escaped
    
    @classmethod
    def _build_between_query(cls, field: str, value: str) -> str:
        """Build a BETWEEN query safely."""
        # Expected format: BETWEEN2025-06-01@2025-07-31
        parts = value[7:].split('@')
        if len(parts) != 2:
            raise ServiceNowValidationError(f"Invalid BETWEEN format: {value}")
        
        start, end = parts
        return f"{field}BETWEEN{cls._escape_value(start)}@{cls._escape_value(end)}"
    
    @classmethod
    def _build_comparison_query(cls, field: str, value: str) -> str:
        """Build a comparison query safely."""
        # Extract operator and value
        for op in ['>=', '<=', '!=', '>', '<']:
            if value.startswith(op):
                actual_value = value[len(op):]
                return f"{field}{op}{cls._escape_value(actual_value)}"
        
        raise ServiceNowValidationError(f"Invalid comparison format: {value}")


def retry_with_backoff(max_retries: int = 3, initial_delay: float = 1.0):
    """
    Decorator for retry logic with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            delay = initial_delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except (ServiceNowRateLimitError, ServiceNowTimeoutError, httpx.ConnectError) as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"Attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {delay} seconds..."
                        )
                        await asyncio.sleep(delay)
                        delay *= 2  # Exponential backoff
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed")
                except ServiceNowAuthenticationError:
                    # Don't retry authentication errors
                    raise
                except Exception as e:
                    # Don't retry unexpected errors
                    logger.error(f"Unexpected error: {e}")
                    raise
            
            # If we get here, all retries failed
            raise last_exception
        
        return wrapper
    return decorator


class SecureServiceNowClient:
    """ServiceNow client with enhanced security and performance features."""
    
    def __init__(self, settings: SecureServiceNowSettings):
        self.settings = settings
        self.base_url = settings.instance_url.rstrip("/")
        self.auth = (settings.username, settings.password.get_secret_value())
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # Create a shared client with connection pooling
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.api_timeout),
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10,
                keepalive_expiry=30
            ),
            auth=self.auth,
            headers=self.headers
        )
        
        logger.info(f"Secure ServiceNow client initialized for: {self.base_url}")
        logger.info(f"User: {settings.username}, Timeout: {settings.api_timeout}s")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup resources."""
        await self.close()
    
    async def close(self):
        """Close the HTTP client and cleanup resources."""
        if self._client:
            await self._client.aclose()
            logger.debug("HTTP client closed")
    
    def _build_url(self, table: str, sys_id: Optional[str] = None) -> str:
        """Build the API URL for a given table and optional sys_id."""
        # Sanitize table name
        if not self._is_valid_table_name(table):
            raise ServiceNowValidationError(f"Invalid table name: {table}")
        
        url = f"{self.base_url}/api/now/table/{quote(table)}"
        if sys_id:
            # Validate sys_id format
            if not self._is_valid_sys_id(sys_id):
                raise ServiceNowValidationError(f"Invalid sys_id format: {sys_id}")
            url = f"{url}/{quote(sys_id)}"
        
        return url
    
    @staticmethod
    def _is_valid_table_name(table: str) -> bool:
        """Validate table name format."""
        import re
        return bool(re.match(r'^[a-zA-Z0-9_]+$', table))
    
    @staticmethod
    def _is_valid_sys_id(sys_id: str) -> bool:
        """Validate sys_id format (32 character hex string)."""
        import re
        return bool(re.match(r'^[a-f0-9]{32}$', sys_id.lower()))
    
    def _validate_table(self, table: str) -> bool:
        """Check if the table is in the allowed tables list."""
        is_valid = table.lower() in [t.lower() for t in self.settings.allowed_tables]
        if not is_valid:
            logger.warning(f"Table '{table}' is not in allowed tables")
        return is_valid
    
    def _handle_http_error(self, response: httpx.Response, operation: str):
        """Handle HTTP errors and raise appropriate exceptions."""
        if response.status_code == 401:
            raise ServiceNowAuthenticationError(
                f"Authentication failed for {operation} operation"
            )
        elif response.status_code == 429:
            raise ServiceNowRateLimitError(
                f"Rate limit exceeded for {operation} operation"
            )
        elif response.status_code == 408:
            raise ServiceNowTimeoutError(
                f"Request timeout for {operation} operation"
            )
        elif response.status_code >= 400:
            raise ServiceNowClientError(
                f"HTTP {response.status_code} error for {operation}: {response.text}"
            )
    
    @retry_with_backoff()
    async def create_record(
        self,
        table: str,
        data: Dict[str, Any],
        fields: Optional[List[str]] = None
    ) -> CRUDResponse:
        """Create a new record with retry logic."""
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
            logger.info(f"Creating record in {table}")
            
            response = await self._client.post(
                url,
                json=data,
                params=params
            )
            
            if response.status_code != 201:
                self._handle_http_error(response, "create")
            
            result = response.json()
            created_record = result.get("result", {})
            
            logger.info(f"Record created successfully in {table}")
            
            return CRUDResponse(
                success=True,
                operation="create",
                table=table,
                message=f"Record created successfully in {table}",
                data=[created_record],
                count=1
            )
            
        except (ServiceNowClientError, ServiceNowAuthenticationError, ServiceNowRateLimitError):
            raise
        except Exception as e:
            logger.error(f"Error creating record: {e}")
            return CRUDResponse(
                success=False,
                operation="create",
                table=table,
                error=str(e)
            )
    
    @retry_with_backoff()
    async def read_records(
        self,
        table: str,
        query: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> CRUDResponse:
        """Read records with secure query building and retry logic."""
        if not self._validate_table(table):
            return CRUDResponse(
                success=False,
                operation="read",
                table=table,
                error=f"Table '{table}' is not in the allowed tables list"
            )
        
        url = self._build_url(table)
        params = {}
        
        # Build secure query
        if query:
            try:
                params["sysparm_query"] = QueryBuilder.build_query(query)
                logger.debug(f"Built query: {params['sysparm_query']}")
            except ServiceNowValidationError as e:
                return CRUDResponse(
                    success=False,
                    operation="read",
                    table=table,
                    error=str(e)
                )
        
        if fields:
            params["sysparm_fields"] = ",".join(fields)
        
        if limit:
            params["sysparm_limit"] = min(limit, self.settings.max_records)
        else:
            params["sysparm_limit"] = self.settings.max_records
        
        try:
            logger.info(f"Reading records from {table}")
            
            response = await self._client.get(url, params=params)
            
            if response.status_code != 200:
                self._handle_http_error(response, "read")
            
            result = response.json()
            records = result.get("result", [])
            
            logger.info(f"Retrieved {len(records)} record(s) from {table}")
            
            return CRUDResponse(
                success=True,
                operation="read",
                table=table,
                message=f"Retrieved {len(records)} record(s) from {table}",
                data=records,
                count=len(records)
            )
            
        except (ServiceNowClientError, ServiceNowAuthenticationError, ServiceNowRateLimitError):
            raise
        except Exception as e:
            logger.error(f"Error reading records: {e}")
            return CRUDResponse(
                success=False,
                operation="read",
                table=table,
                error=str(e)
            )
    
    @retry_with_backoff()
    async def update_record(
        self,
        table: str,
        sys_id: str,
        data: Dict[str, Any],
        fields: Optional[List[str]] = None
    ) -> CRUDResponse:
        """Update a record with retry logic."""
        if not self._validate_table(table):
            return CRUDResponse(
                success=False,
                operation="update",
                table=table,
                error=f"Table '{table}' is not in the allowed tables list"
            )
        
        try:
            url = self._build_url(table, sys_id)
        except ServiceNowValidationError as e:
            return CRUDResponse(
                success=False,
                operation="update",
                table=table,
                error=str(e)
            )
        
        params = {}
        if fields:
            params["sysparm_fields"] = ",".join(fields)
        
        try:
            logger.info(f"Updating record {sys_id} in {table}")
            
            response = await self._client.patch(
                url,
                json=data,
                params=params
            )
            
            if response.status_code != 200:
                self._handle_http_error(response, "update")
            
            result = response.json()
            updated_record = result.get("result", {})
            
            logger.info(f"Record {sys_id} updated successfully in {table}")
            
            return CRUDResponse(
                success=True,
                operation="update",
                table=table,
                message=f"Record {sys_id} updated successfully in {table}",
                data=[updated_record],
                count=1
            )
            
        except (ServiceNowClientError, ServiceNowAuthenticationError, ServiceNowRateLimitError):
            raise
        except Exception as e:
            logger.error(f"Error updating record: {e}")
            return CRUDResponse(
                success=False,
                operation="update",
                table=table,
                error=str(e)
            )
    
    @retry_with_backoff()
    async def delete_record(
        self,
        table: str,
        sys_id: str
    ) -> CRUDResponse:
        """Delete a record with retry logic."""
        if not self._validate_table(table):
            return CRUDResponse(
                success=False,
                operation="delete",
                table=table,
                error=f"Table '{table}' is not in the allowed tables list"
            )
        
        try:
            url = self._build_url(table, sys_id)
        except ServiceNowValidationError as e:
            return CRUDResponse(
                success=False,
                operation="delete",
                table=table,
                error=str(e)
            )
        
        try:
            logger.info(f"Deleting record {sys_id} from {table}")
            
            response = await self._client.delete(url)
            
            if response.status_code != 204:
                self._handle_http_error(response, "delete")
            
            logger.info(f"Record {sys_id} deleted successfully from {table}")
            
            return CRUDResponse(
                success=True,
                operation="delete",
                table=table,
                message=f"Record {sys_id} deleted successfully from {table}",
                count=1
            )
            
        except (ServiceNowClientError, ServiceNowAuthenticationError, ServiceNowRateLimitError):
            raise
        except Exception as e:
            logger.error(f"Error deleting record: {e}")
            return CRUDResponse(
                success=False,
                operation="delete",
                table=table,
                error=str(e)
            )
