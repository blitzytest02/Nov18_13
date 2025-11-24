"""
HTTP Client for Archie Service Admin Communication.

This module implements the gateway pattern where archie-service-backend acts
as a public-facing proxy that performs authorization checks before forwarding
requests to archie-service-admin which contains all business logic.

The AdminClient provides methods for routing Figma-related API requests to
the admin service without duplicating any business logic, maintaining clean
separation between the gateway layer and business logic layer.
"""

import logging
import time
import json
from typing import Dict, Optional, Any, List, Union, cast
from urllib.parse import urljoin

import requests
from requests.exceptions import (
    RequestException,
    Timeout,
    ConnectionError as RequestsConnectionError
)


logger = logging.getLogger(__name__)


class AdminServiceError(Exception):
    """
    Base exception for admin service communication errors.

    Raised when the admin service returns an error response or when
    communication with the admin service fails.
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        details: Optional[Dict] = None
    ):
        """
        Initialize AdminServiceError.

        :param message: Human-readable error message
        :param status_code: HTTP status code from admin service response
        :param details: Additional error details from admin service
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class AdminServiceConnectionError(AdminServiceError):
    """
    Exception raised when connection to admin service fails.

    This typically indicates network issues, DNS resolution failures,
    or the admin service being unavailable.
    """


class AdminServiceTimeoutError(AdminServiceError):
    """
    Exception raised when admin service request times out.

    This indicates the admin service took too long to respond,
    potentially due to high load or downstream service issues.
    """


class AdminClient:
    """
    HTTP client for communicating with archie-service-admin microservice.

    Provides methods for routing Figma-related API requests from the backend
    gateway to the admin service. Implements retry logic, error handling, and
    user context propagation without duplicating business logic.

    Example usage::

        client = AdminClient(admin_url="http://admin-service:8000", timeout=30)

        user_context = {"user_id": 123, "auth_token": "..."}
        installation_data = {
            "name": "My Figma",
            "pat": "figd_...",
            "description": "..."
        }

        result = client.create_figma_installation(
            installation_data, user_context
        )
    """

    def __init__(
        self,
        admin_url: str,
        timeout: int = 30,
        max_retries: int = 3,
        retry_backoff: float = 1.0
    ):
        """
        Initialize AdminClient with configuration.

        :param admin_url: Base URL of archie-service-admin
            (e.g., 'http://admin-service:8000')
        :param timeout: Request timeout in seconds (default: 30)
        :param max_retries: Maximum number of retry attempts for
            transient failures (default: 3)
        :param retry_backoff: Initial backoff delay in seconds,
            doubles with each retry (default: 1.0)
        """
        self.admin_url = admin_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.session = requests.Session()

        logger.info(
            "AdminClient initialized with admin_url=%s, timeout=%s",
            self.admin_url,
            self.timeout
        )

    def _build_headers(self, user_context: Dict[str, Any]) -> Dict[str, str]:
        """
        Build HTTP headers with user context for admin service requests.

        Propagates user authentication and authorization context from the
        backend gateway to the admin service via HTTP headers.

        :param user_context: Dictionary containing user_id, auth tokens,
            and other context
        :return: Dictionary of HTTP headers
        """
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        # Propagate user ID if present
        if 'user_id' in user_context:
            headers['X-User-ID'] = str(user_context['user_id'])

        # Propagate authentication token if present
        if 'auth_token' in user_context:
            headers['Authorization'] = f"Bearer {user_context['auth_token']}"

        # Propagate any additional context headers
        if 'request_id' in user_context:
            headers['X-Request-ID'] = str(user_context['request_id'])

        return headers

    def _make_request(
        self,
        method: str,
        path: str,
        user_context: Dict[str, Any],
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Union[Dict[str, Any], List[Any]]:
        """
        Make HTTP request to admin service with retry logic.

        Handles transient network failures with exponential backoff retry.
        Maps admin service errors to appropriate exception types.

        :param method: HTTP method (GET, POST, PUT, DELETE)
        :param path: API endpoint path (e.g., '/v1/figma/installations')
        :param user_context: User context to propagate via headers
        :param data: Request body data (for POST/PUT)
        :param params: Query parameters (for GET)
        :return: Response data as dictionary or list (depending on endpoint)
        :raises AdminServiceError: For general admin service errors
        :raises AdminServiceConnectionError: For connection failures
        :raises AdminServiceTimeoutError: For timeout errors
        """
        url = urljoin(self.admin_url, path)
        headers = self._build_headers(user_context)

        attempt = 0
        last_exception: Optional[Exception] = None

        while attempt < self.max_retries:
            try:
                logger.debug(
                    "Making %s request to %s (attempt %d/%d)",
                    method,
                    url,
                    attempt + 1,
                    self.max_retries
                )

                response = self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                    params=params,
                    timeout=self.timeout
                )

                # Handle successful responses (2xx)
                if 200 <= response.status_code < 300:
                    # Handle empty responses (e.g., 204 No Content)
                    if response.status_code == 204 or not response.content:
                        return {}

                    try:
                        return response.json()
                    except json.JSONDecodeError as e:
                        logger.error(
                            "Failed to decode JSON response from admin "
                            "service: %s",
                            e
                        )
                        raise AdminServiceError(
                            "Invalid JSON response from admin service",
                            status_code=response.status_code
                        ) from e

                # Handle error responses
                error_data: Dict[str, Any] = {}
                try:
                    error_data = response.json() if response.content else {}
                except json.JSONDecodeError:
                    error_data = {"message": response.text}

                error_message = error_data.get('error', {}).get(
                    'message', error_data.get('message', 'Unknown error')
                )

                logger.error(
                    "Admin service returned error: status=%s, message=%s, "
                    "url=%s",
                    response.status_code,
                    error_message,
                    url
                )

                raise AdminServiceError(
                    message=error_message,
                    status_code=response.status_code,
                    details=error_data
                )

            except Timeout as e:
                last_exception = e
                logger.warning(
                    "Request to admin service timed out (attempt %d/%d): %s",
                    attempt + 1, self.max_retries, url
                )

                # Don't retry on timeout for the last attempt
                if attempt == self.max_retries - 1:
                    raise AdminServiceTimeoutError(
                        f"Admin service request timed out after "
                        f"{self.timeout}s",
                        details={"url": url, "timeout": self.timeout}
                    ) from e

            except RequestsConnectionError as e:
                last_exception = e
                logger.warning(
                    "Connection to admin service failed (attempt %d/%d): %s",
                    attempt + 1, self.max_retries, url
                )

                # Don't retry on connection error for the last attempt
                if attempt == self.max_retries - 1:
                    raise AdminServiceConnectionError(
                        f"Failed to connect to admin service at "
                        f"{self.admin_url}",
                        details={"url": url, "error": str(e)}
                    ) from e

            except AdminServiceError:
                # Don't retry on explicit admin service errors (4xx, 5xx)
                # Re-raise immediately to skip retry logic for
                # non-transient errors
                raise

            except RequestException as e:
                last_exception = e
                logger.warning(
                    "Request to admin service failed (attempt %d/%d): %s",
                    attempt + 1, self.max_retries, e
                )

                if attempt == self.max_retries - 1:
                    raise AdminServiceError(
                        f"Admin service request failed: {str(e)}",
                        details={"url": url, "error": str(e)}
                    ) from e

            # Exponential backoff before retry
            if attempt < self.max_retries - 1:
                backoff_delay = self.retry_backoff * (2 ** attempt)
                logger.debug("Retrying after %ss backoff", backoff_delay)
                time.sleep(backoff_delay)

            attempt += 1

        # Should not reach here, but handle it just in case
        raise AdminServiceError(
            f"Admin service request failed after {self.max_retries} attempts",
            details={"url": url, "last_error": str(last_exception)}
        )

    def create_figma_installation(
        self,
        data: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new Figma installation.

        Routes request to POST /v1/figma/installations on admin service.

        :param data: Installation data containing name, description, pat,
            team_id (optional)
        :param user_context: User context for authorization and tracking
        :return: Created installation record (without PAT)
        :raises AdminServiceError: If creation fails

        Example::

            data = {
                "name": "My Figma Integration",
                "description": "Team design files",
                "pat": "figd_AbCdEf...",
                "team_id": 42
            }
            result = client.create_figma_installation(data, user_context)
        """
        logger.info(
            "Routing create_figma_installation request for user %s",
            user_context.get("user_id")
        )
        result = self._make_request(
            method='POST',
            path='/v1/figma/installations',
            user_context=user_context,
            data=data
        )
        return cast(Dict[str, Any], result)

    def get_figma_installation(
        self,
        installation_id: int,
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Retrieve a Figma installation by ID.

        Routes request to GET /v1/figma/installations/{id} on admin service.
        Returns installation with computed PAT status (Active/Expired).

        :param installation_id: ID of the installation to retrieve
        :param user_context: User context for authorization
        :return: Installation record with PAT status (never includes
            actual PAT)
        :raises AdminServiceError: If retrieval fails or installation not found

        Example::

            installation = client.get_figma_installation(123, user_context)
            print(f"Status: {installation['pat_status']}")
        """
        logger.info(
            "Routing get_figma_installation request for installation %s",
            installation_id
        )
        result = self._make_request(
            method='GET',
            path=f'/v1/figma/installations/{installation_id}',
            user_context=user_context
        )
        return cast(Dict[str, Any], result)

    def update_figma_pat(
        self,
        installation_id: int,
        data: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update the Personal Access Token for a Figma installation.

        Routes request to PUT /v1/figma/installations/{id}/pat on admin
        service.

        :param installation_id: ID of the installation to update
        :param data: New PAT data containing 'pat' field
        :param user_context: User context for authorization
        :return: Updated installation record
        :raises AdminServiceError: If update fails or user unauthorized

        Example::

            data = {"pat": "figd_NewToken123..."}
            result = client.update_figma_pat(123, data, user_context)
        """
        logger.info(
            "Routing update_figma_pat request for installation %s",
            installation_id
        )
        result = self._make_request(
            method='PUT',
            path=f'/v1/figma/installations/{installation_id}/pat',
            user_context=user_context,
            data=data
        )
        return cast(Dict[str, Any], result)

    def delete_figma_installation(
        self,
        installation_id: int,
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Delete a Figma installation (soft delete).

        Routes request to DELETE /v1/figma/installations/{id} on admin service.
        Also removes the associated PAT from Google Secret Manager.

        :param installation_id: ID of the installation to delete
        :param user_context: User context for authorization
        :return: Empty dict on success
        :raises AdminServiceError: If deletion fails or user unauthorized

        Example::

            client.delete_figma_installation(123, user_context)
        """
        logger.info(
            "Routing delete_figma_installation request for "
            "installation %s",
            installation_id
        )
        result = self._make_request(
            method='DELETE',
            path=f'/v1/figma/installations/{installation_id}',
            user_context=user_context
        )
        return cast(Dict[str, Any], result)

    def share_figma_installation(
        self,
        installation_id: int,
        data: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Share a Figma installation with other users.

        Routes request to POST /v1/figma/installations/{id}/share on
        admin service.
        Requires ADMIN or SUPER_ADMIN role.

        :param installation_id: ID of the installation to share
        :param data: Share data containing target_user_id and access_level
        :param user_context: User context for role verification
        :return: Created access record
        :raises AdminServiceError: If sharing fails or user lacks
            ADMIN/SUPER_ADMIN role

        Example::

            data = {
                "target_user_id": 456,
                "access_level": "viewer"
            }
            result = client.share_figma_installation(123, data, user_context)
        """
        logger.info(
            "Routing share_figma_installation request for installation "
            "%s by user %s",
            installation_id,
            user_context.get("user_id")
        )
        result = self._make_request(
            method='POST',
            path=f'/v1/figma/installations/{installation_id}/share',
            user_context=user_context,
            data=data
        )
        return cast(Dict[str, Any], result)

    def revoke_figma_access(
        self,
        installation_id: int,
        data: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Revoke user access to a Figma installation.

        Routes request to DELETE /v1/figma/installations/{id}/share on
        admin service.
        Requires ADMIN or SUPER_ADMIN role.

        :param installation_id: ID of the installation
        :param data: Revocation data containing target_user_id
        :param user_context: User context for role verification
        :return: Empty dict on success
        :raises AdminServiceError: If revocation fails or user lacks
            ADMIN/SUPER_ADMIN role

        Example::

            data = {"target_user_id": 456}
            client.revoke_figma_access(123, data, user_context)
        """
        logger.info(
            "Routing revoke_figma_access request for installation %s "
            "by user %s",
            installation_id,
            user_context.get("user_id")
        )
        result = self._make_request(
            method='DELETE',
            path=f'/v1/figma/installations/{installation_id}/share',
            user_context=user_context,
            data=data
        )
        return cast(Dict[str, Any], result)

    def validate_figma_frame(
        self,
        data: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate Figma frame URL and retrieve metadata.

        Routes request to POST /v1/figma/frames/validate on admin
        service. Checks if the PAT associated with the installation can
        access the frame.

        :param data: Validation data containing frame_url and
            installation_id
        :param user_context: User context for authorization
        :return: Validation result with valid (bool), title (str), and
            message (str)
        :raises AdminServiceError: If validation request fails

        Example::

            data = {
                "frame_url": (
                    "https://www.figma.com/file/ABC123/Design?node-id=1:2"
                ),
                "installation_id": 123
            }
            result = client.validate_figma_frame(data, user_context)
            if result['valid']:
                print(f"Frame title: {result['title']}")
        """
        logger.info(
            "Routing validate_figma_frame request for user %s",
            user_context.get("user_id")
        )
        result = self._make_request(
            method='POST',
            path='/v1/figma/frames/validate',
            user_context=user_context,
            data=data
        )
        return cast(Dict[str, Any], result)

    def create_figma_attachments(
        self,
        data: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Attach Figma frames to a project.

        Routes request to POST /v1/figma/attachments on admin service.
        Operation is additive and idempotent - same frame URL overwrites
        previous attachment.

        :param data: Attachment data containing project_id,
            installation_id, frames list, tech_spec_id (optional)
        :param user_context: User context for authorization and tracking
        :return: List of created/updated attachment records
        :raises AdminServiceError: If attachment creation fails

        Example::

            data = {
                "project_id": 100,
                "installation_id": 123,
                "tech_spec_id": 200,  # optional
                "frames": [
                    {
                        "url": (
                            "https://www.figma.com/file/ABC/Design?"
                            "node-id=1:2"
                        ),
                        "description": "Homepage"
                    },
                    {
                        "url": (
                            "https://www.figma.com/file/ABC/Design?"
                            "node-id=3:4"
                        ),
                        "description": "Login"
                    }
                ]
            }
            attachments = client.create_figma_attachments(data, user_context)
        """
        logger.info(
            "Routing create_figma_attachments request for project %s "
            "by user %s",
            data.get("project_id"),
            user_context.get("user_id")
        )
        result = self._make_request(
            method='POST',
            path='/v1/figma/attachments',
            user_context=user_context,
            data=data
        )
        return cast(List[Dict[str, Any]], result)

    def list_figma_attachments(
        self,
        query_params: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        List Figma attachments filtered by project and optionally tech_spec.

        Routes request to GET /v1/figma/attachments on admin service.

        :param query_params: Query parameters containing project_id
            (required) and tech_spec_id (optional)
        :param user_context: User context for authorization
        :return: List of attachment records
        :raises AdminServiceError: If listing fails

        Example::

            # List all attachments for a project
            params = {"project_id": 100}
            attachments = client.list_figma_attachments(params, user_context)

            # List attachments for specific tech spec
            params = {"project_id": 100, "tech_spec_id": 200}
            attachments = client.list_figma_attachments(params, user_context)
        """
        logger.info(
            "Routing list_figma_attachments request for project %s",
            query_params.get("project_id")
        )
        result = self._make_request(
            method='GET',
            path='/v1/figma/attachments',
            user_context=user_context,
            params=query_params
        )
        return cast(List[Dict[str, Any]], result)

    def get_figma_attachment(
        self,
        attachment_id: int,
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Retrieve a single Figma attachment by ID.

        Routes request to GET /v1/figma/attachments/{id} on admin service.

        :param attachment_id: ID of the attachment to retrieve
        :param user_context: User context for authorization
        :return: Attachment record
        :raises AdminServiceError: If retrieval fails or attachment not found

        Example::

            attachment = client.get_figma_attachment(789, user_context)
            print(f"Frame URL: {attachment['frame_url']}")
        """
        logger.info(
            "Routing get_figma_attachment request for attachment %s",
            attachment_id
        )
        result = self._make_request(
            method='GET',
            path=f'/v1/figma/attachments/{attachment_id}',
            user_context=user_context
        )
        return cast(Dict[str, Any], result)

    def delete_figma_attachment(
        self,
        attachment_id: int,
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Delete a Figma attachment (soft delete).

        Routes request to DELETE /v1/figma/attachments/{id} on admin service.

        :param attachment_id: ID of the attachment to delete
        :param user_context: User context for authorization
        :return: Empty dict on success
        :raises AdminServiceError: If deletion fails or user unauthorized

        Example::

            client.delete_figma_attachment(789, user_context)
        """
        logger.info(
            "Routing delete_figma_attachment request for attachment %s",
            attachment_id
        )
        result = self._make_request(
            method='DELETE',
            path=f'/v1/figma/attachments/{attachment_id}',
            user_context=user_context
        )
        return cast(Dict[str, Any], result)
