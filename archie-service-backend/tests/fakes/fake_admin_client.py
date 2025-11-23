"""
Fake implementation of the admin service HTTP client for testing.

This module provides a FakeAdminClient class that simulates HTTP responses
from archie-service-admin without requiring actual service-to-service
communication. It maintains configurable response patterns for success,
error, and timeout scenarios to enable comprehensive route handler testing
in isolation.

The fake client tracks all requests made during tests and provides methods
to configure responses for different endpoints and scenarios. This enables
testing of error handling, timeouts, and various response codes without
depending on the actual admin service being available.
"""

from typing import Any, Dict, List, Optional, Tuple


class FakeResponse:
    """
    Simulates an HTTP response object.
    
    Provides the same interface as requests.Response for compatibility
    with code that expects standard HTTP response objects.
    """
    
    def __init__(self, status_code: int, data: Optional[Dict[str, Any]] = None, text: str = ""):
        """
        Initialize a fake HTTP response.
        
        :param status_code: HTTP status code to return
        :param data: JSON response data (will be returned by json() method)
        :param text: Raw text response content
        """
        self.status_code = status_code
        self._json_data = data or {}
        self.text = text or str(data)
        self.ok = 200 <= status_code < 300
    
    def json(self) -> Dict[str, Any]:
        """
        Return the JSON response data.
        
        :return: Dictionary containing response data
        """
        return self._json_data
    
    def raise_for_status(self) -> None:
        """
        Raise an exception for error status codes.
        
        Mimics the behavior of requests.Response.raise_for_status()
        """
        if not self.ok:
            raise Exception(f"HTTP Error {self.status_code}")


class FakeAdminClient:
    """
    Fake implementation of the admin service HTTP client.
    
    This fake simulates communication with archie-service-admin for testing
    purposes. It maintains in-memory state for request tracking and provides
    configurable response patterns without requiring actual HTTP connections.
    
    Example usage in tests::
    
        # Setup fake with success response
        fake_client = FakeAdminClient()
        fake_client.set_success({'id': 1, 'name': 'Test Installation'})
        
        # Use in test
        response = fake_client.post('/v1/figma/installations', json={...})
        assert response.status_code == 201
        
        # Verify request was made
        assert fake_client.request_count == 1
        assert fake_client.last_request[0] == 'POST'
        
        # Configure error response for next request
        fake_client.set_error(404, 'Installation not found')
        response = fake_client.get('/v1/figma/installations/999')
        assert response.status_code == 404
    
    The fake maintains state across method calls within a test but should be
    reset between tests using the reset() method or by creating a new instance.
    """
    
    def __init__(self):
        """
        Initialize the fake admin client with default response patterns.
        
        Sets up in-memory state for request tracking and configures default
        successful responses for common Figma endpoints.
        """
        self._default_status_code = 200
        self._default_data: Dict[str, Any] = {}
        self._configured_status_code: Optional[int] = None
        self._configured_data: Optional[Dict[str, Any]] = None
        self._simulate_timeout_flag = False
        self._simulate_connection_error_flag = False
        
        # Request tracking
        self.requests_made: List[Tuple[str, str, Optional[Dict[str, Any]]]] = []
        
        # Default responses for Figma endpoints
        self._endpoint_defaults = {
            '/v1/figma/installations': {
                'POST': (201, {
                    'id': 1,
                    'name': 'Test Installation',
                    'description': 'Test description',
                    'user_id': 1,
                    'status': 'active',
                    'created_at': '2024-01-01T00:00:00Z',
                    'updated_at': '2024-01-01T00:00:00Z'
                }),
                'GET': (200, {
                    'installations': [
                        {
                            'id': 1,
                            'name': 'Test Installation',
                            'status': 'active',
                            'pat_status': 'Active'
                        }
                    ]
                })
            },
            '/v1/figma/installations/{id}': {
                'GET': (200, {
                    'id': 1,
                    'name': 'Test Installation',
                    'description': 'Test description',
                    'user_id': 1,
                    'status': 'active',
                    'pat_status': 'Active',
                    'created_at': '2024-01-01T00:00:00Z',
                    'updated_at': '2024-01-01T00:00:00Z'
                }),
                'DELETE': (204, {})
            },
            '/v1/figma/installations/{id}/pat': {
                'PUT': (200, {
                    'id': 1,
                    'name': 'Test Installation',
                    'status': 'active',
                    'pat_status': 'Active',
                    'updated_at': '2024-01-01T00:00:00Z'
                })
            },
            '/v1/figma/installations/{id}/share': {
                'POST': (201, {
                    'id': 1,
                    'figma_installation_id': 1,
                    'user_id': 2,
                    'access_level': 'viewer',
                    'granted_by': 1,
                    'created_at': '2024-01-01T00:00:00Z'
                }),
                'DELETE': (204, {})
            },
            '/v1/figma/installations/{id}/access': {
                'GET': (200, {
                    'access_records': [
                        {
                            'id': 1,
                            'user_id': 2,
                            'access_level': 'viewer',
                            'granted_by': 1
                        }
                    ]
                })
            },
            '/v1/figma/frames/validate': {
                'POST': (200, {
                    'valid': True,
                    'title': 'Design Frame Title',
                    'message': 'Frame is accessible'
                })
            },
            '/v1/figma/attachments': {
                'POST': (201, {
                    'attachments': [
                        {
                            'id': 1,
                            'project_id': 100,
                            'figma_installation_id': 1,
                            'frame_url': 'https://www.figma.com/file/ABC123/DesignFile?node-id=1:2',
                            'frame_title': 'Design Frame',
                            'description': 'Test frame',
                            'created_by': 1,
                            'created_at': '2024-01-01T00:00:00Z'
                        }
                    ]
                }),
                'GET': (200, {
                    'attachments': [
                        {
                            'id': 1,
                            'project_id': 100,
                            'frame_url': 'https://www.figma.com/file/ABC123/DesignFile?node-id=1:2',
                            'frame_title': 'Design Frame'
                        }
                    ]
                })
            },
            '/v1/figma/attachments/{id}': {
                'GET': (200, {
                    'id': 1,
                    'project_id': 100,
                    'figma_installation_id': 1,
                    'frame_url': 'https://www.figma.com/file/ABC123/DesignFile?node-id=1:2',
                    'frame_title': 'Design Frame',
                    'description': 'Test frame',
                    'created_by': 1,
                    'created_at': '2024-01-01T00:00:00Z'
                }),
                'DELETE': (204, {})
            },
            '/internal/figma/installations/by-project/{project_id}': {
                'GET': (200, {
                    'id': 1,
                    'name': 'Test Installation',
                    'pat': 'figd_test_token_12345',  # Internal endpoint includes PAT
                    'status': 'active',
                    'created_at': '2024-01-01T00:00:00Z'
                })
            }
        }
    
    def _track_request(self, method: str, path: str, data: Optional[Dict[str, Any]] = None) -> None:
        """
        Track a request for later verification in tests.
        
        :param method: HTTP method (GET, POST, PUT, DELETE)
        :param path: Request path
        :param data: Request body data (JSON)
        """
        self.requests_made.append((method, path, data))
    
    def _get_default_response(self, method: str, path: str) -> Tuple[int, Dict[str, Any]]:
        """
        Get the default response for a given endpoint.
        
        :param method: HTTP method
        :param path: Request path
        :return: Tuple of (status_code, response_data)
        """
        # Try exact match first
        if path in self._endpoint_defaults:
            endpoint_config = self._endpoint_defaults[path]
            if method in endpoint_config:
                return endpoint_config[method]
        
        # Try pattern matching for parameterized paths
        for pattern, methods in self._endpoint_defaults.items():
            if '{id}' in pattern or '{project_id}' in pattern:
                # Simple pattern matching - replace {id} or {project_id} with regex-like match
                pattern_parts = pattern.split('/')
                path_parts = path.split('/')
                
                if len(pattern_parts) == len(path_parts):
                    match = True
                    for pp, pth in zip(pattern_parts, path_parts):
                        if pp.startswith('{') and pp.endswith('}'):
                            # This is a parameter, accept any value
                            continue
                        elif pp != pth:
                            match = False
                            break
                    
                    if match and method in methods:
                        return methods[method]
        
        # Default fallback
        return (200, {})
    
    def _execute_request(
        self,
        method: str,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> FakeResponse:
        """
        Execute a fake HTTP request.
        
        :param method: HTTP method
        :param path: Request path
        :param data: Request body data
        :param params: Query parameters
        :param headers: Request headers
        :return: FakeResponse object
        :raises: Exception for timeout or connection error scenarios
        """
        # Track the request
        self._track_request(method, path, data)
        
        # Simulate timeout
        if self._simulate_timeout_flag:
            self._simulate_timeout_flag = False  # Reset after use
            raise TimeoutError("Request timed out")
        
        # Simulate connection error
        if self._simulate_connection_error_flag:
            self._simulate_connection_error_flag = False  # Reset after use
            raise ConnectionError("Connection refused - admin service unavailable")
        
        # Use configured response if set
        if self._configured_status_code is not None:
            status_code = self._configured_status_code
            response_data = self._configured_data or {}
            # Clear configuration after use (single-use)
            self._configured_status_code = None
            self._configured_data = None
            return FakeResponse(status_code, response_data)
        
        # Use default response for endpoint
        status_code, response_data = self._get_default_response(method, path)
        return FakeResponse(status_code, response_data)
    
    def post(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> FakeResponse:
        """
        Simulate a POST request to the admin service.
        
        :param path: Request path (e.g., '/v1/figma/installations')
        :param json: Request body as JSON dictionary
        :param headers: Optional HTTP headers
        :return: FakeResponse object with configured status and data
        """
        return self._execute_request('POST', path, data=json, headers=headers)
    
    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> FakeResponse:
        """
        Simulate a GET request to the admin service.
        
        :param path: Request path (e.g., '/v1/figma/installations/1')
        :param params: Query parameters
        :param headers: Optional HTTP headers
        :return: FakeResponse object with configured status and data
        """
        return self._execute_request('GET', path, params=params, headers=headers)
    
    def put(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> FakeResponse:
        """
        Simulate a PUT request to the admin service.
        
        :param path: Request path (e.g., '/v1/figma/installations/1/pat')
        :param json: Request body as JSON dictionary
        :param headers: Optional HTTP headers
        :return: FakeResponse object with configured status and data
        """
        return self._execute_request('PUT', path, data=json, headers=headers)
    
    def delete(
        self,
        path: str,
        headers: Optional[Dict[str, str]] = None
    ) -> FakeResponse:
        """
        Simulate a DELETE request to the admin service.
        
        :param path: Request path (e.g., '/v1/figma/installations/1')
        :param headers: Optional HTTP headers
        :return: FakeResponse object with configured status and data
        """
        return self._execute_request('DELETE', path, headers=headers)
    
    def set_response(self, status_code: int, data: Optional[Dict[str, Any]] = None) -> None:
        """
        Configure the response for the next request.
        
        This configuration is single-use and will be cleared after the next request.
        
        :param status_code: HTTP status code to return
        :param data: Response data to return
        """
        self._configured_status_code = status_code
        self._configured_data = data or {}
    
    def set_success(self, data: Dict[str, Any]) -> None:
        """
        Configure a successful 200 OK response for the next request.
        
        :param data: Response data to return
        """
        self.set_response(200, data)
    
    def set_error(self, status_code: int, error_message: str) -> None:
        """
        Configure an error response for the next request.
        
        :param status_code: HTTP error status code (e.g., 400, 404, 500)
        :param error_message: Error message to include in response
        """
        error_data = {
            'error': {
                'code': f'ERROR_{status_code}',
                'message': error_message
            }
        }
        self.set_response(status_code, error_data)
    
    def simulate_timeout(self) -> None:
        """
        Configure the next request to simulate a connection timeout.
        
        The next request will raise a TimeoutError instead of returning a response.
        """
        self._simulate_timeout_flag = True
    
    def simulate_admin_service_down(self) -> None:
        """
        Configure the next request to simulate admin service being unavailable.
        
        The next request will raise a ConnectionError instead of returning a response.
        """
        self._simulate_connection_error_flag = True
    
    def simulate_401(self) -> None:
        """Configure a 401 Unauthorized response for the next request."""
        self.set_error(401, 'Unauthorized - authentication required')
    
    def simulate_403(self) -> None:
        """Configure a 403 Forbidden response for the next request."""
        self.set_error(403, 'Forbidden - insufficient permissions')
    
    def simulate_404(self) -> None:
        """Configure a 404 Not Found response for the next request."""
        self.set_error(404, 'Resource not found')
    
    def simulate_500(self) -> None:
        """Configure a 500 Internal Server Error response for the next request."""
        self.set_error(500, 'Internal server error')
    
    def reset(self) -> None:
        """
        Reset the fake client to its initial state.
        
        Clears all request history and configured responses. Should be called
        between tests to ensure clean state.
        """
        self._configured_status_code = None
        self._configured_data = None
        self._simulate_timeout_flag = False
        self._simulate_connection_error_flag = False
        self.requests_made = []
    
    @property
    def last_request(self) -> Optional[Tuple[str, str, Optional[Dict[str, Any]]]]:
        """
        Get the most recent request made to the fake client.
        
        :return: Tuple of (method, path, data) or None if no requests made
        """
        if self.requests_made:
            return self.requests_made[-1]
        return None
    
    @property
    def request_count(self) -> int:
        """
        Get the total number of requests made to the fake client.
        
        :return: Number of requests tracked
        """
        return len(self.requests_made)
    
    def get_request(self, index: int) -> Optional[Tuple[str, str, Optional[Dict[str, Any]]]]:
        """
        Get a specific request by index.
        
        :param index: Index of the request (0-based)
        :return: Tuple of (method, path, data) or None if index out of range
        """
        if 0 <= index < len(self.requests_made):
            return self.requests_made[index]
        return None
    
    def clear_requests(self) -> None:
        """
        Clear all tracked requests.
        
        Useful when you want to reset request tracking without resetting
        configured responses.
        """
        self.requests_made = []
