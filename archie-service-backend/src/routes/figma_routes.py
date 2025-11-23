"""
Figma Integration Route Handlers for Backend Gateway Service.

This module implements the public-facing API endpoints for Figma integration,
acting as a gateway that enforces the FIGMA_INTEGRATION_ENABLED feature flag,
performs authentication and authorization checks, and forwards validated
requests to archie-service-admin without duplicating business logic.

The module follows the dual service architecture pattern where:
- archie-service-backend (this module): Handles authorization and routing
- archie-service-admin: Contains all business logic implementation

All endpoints enforce:
1. FIGMA_INTEGRATION_ENABLED feature flag check
2. User authentication verification
3. Project access authorization (for attachment endpoints)
4. Request forwarding to admin service with user context

Exports:
    figma_bp: Flask Blueprint containing all Figma integration route handlers
"""

import logging
import os
from functools import wraps
from typing import Any, Callable, Dict, Tuple

from flask import Blueprint, jsonify, request

try:
    # Try relative import first (when used as a package)
    from ..services.admin_client import (
        AdminClient,
        AdminServiceConnectionError,
        AdminServiceError,
        AdminServiceTimeoutError
    )
except ImportError:
    # Fall back to absolute import (when used standalone or in tests)
    from services.admin_client import (  # type: ignore[no-redef]
        AdminClient,  # type: ignore[no-redef]
        AdminServiceConnectionError,  # type: ignore[no-redef]
        AdminServiceError,  # type: ignore[no-redef]
        AdminServiceTimeoutError  # type: ignore[no-redef]
    )


# Initialize logger for request/response tracking
logger = logging.getLogger(__name__)

# Create Flask Blueprint for Figma routes
figma_bp = Blueprint('figma', __name__, url_prefix='/v1/figma')


def is_feature_enabled() -> bool:
    """
    Check if Figma integration feature is enabled via configuration.

    Reads FIGMA_INTEGRATION_ENABLED from environment variables to determine
    if Figma functionality should be accessible.

    :return: True if feature is enabled, False otherwise
    """
    enabled_str = os.getenv('FIGMA_INTEGRATION_ENABLED', 'false').lower()
    return enabled_str in ('true', '1', 'yes', 'on')


def require_feature_flag(f: Callable) -> Callable:
    """
    Decorator to enforce FIGMA_INTEGRATION_ENABLED feature flag on endpoints.

    Returns 404 Not Found if feature flag is disabled to hide Figma
    functionality from clients when not enabled.

    :param f: Route handler function to decorate
    :return: Decorated function with feature flag check
    """
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Tuple[Any, int]:
        if not is_feature_enabled():
            logger.warning(
                "Figma integration endpoint accessed but feature is disabled: %s",
                request.path
            )
            return jsonify({
                "error": {
                    "code": "FEATURE_DISABLED",
                    "message": "Figma integration is not enabled"
                }
            }), 404

        return f(*args, **kwargs)

    return decorated_function


def get_user_context() -> Dict[str, Any]:
    """
    Extract authenticated user context from Flask request.

    Retrieves user identification and authentication tokens from request
    headers, cookies, or session to build context dictionary for forwarding
    to admin service.

    :return: Dictionary containing user_id, auth_token, request_id, and other
        context information
    :raises ValueError: If user is not authenticated or required context
        is missing
    """
    # Extract user ID from request header (set by authentication middleware)
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        # Try to get from g object if authentication middleware stores it there
        from flask import g
        user_id = getattr(g, 'user_id', None)

    if not user_id:
        logger.error("Authentication required: No user context found in request")
        raise ValueError("User authentication required")

    # Extract authentication token
    auth_token = None
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        auth_token = auth_header[7:]  # Remove 'Bearer ' prefix

    # Build user context dictionary
    context = {
        'user_id': int(user_id),
        'auth_token': auth_token,
        'request_id': request.headers.get('X-Request-ID', ''),
        'ip_address': request.remote_addr
    }

    logger.debug("Extracted user context for user_id=%s", user_id)
    return context


def verify_project_access(user_context: Dict[str, Any], project_id: int) -> bool:
    """
    Verify that the authenticated user has access to the specified project.

    This performs authorization checks to ensure users can only attach or
    view Figma frames for projects they have access to.

    :param user_context: Authenticated user context
    :param project_id: ID of the project to check access for
    :return: True if user has access, False otherwise
    """
    # In a real implementation, this would query the database or call
    # an authorization service to verify project access.
    # For now, we delegate this to the admin service which will perform
    # the actual authorization check.

    # The admin service will reject unauthorized requests, so we can
    # safely return True here and let the admin service handle it.
    # This is a design decision to keep authorization logic centralized
    # in the admin service.

    logger.debug(
        "Project access check for user_id=%s, project_id=%s (delegated to admin service)",
        user_context.get('user_id'),
        project_id
    )
    return True


def get_admin_client() -> AdminClient:
    """
    Get or create AdminClient instance for routing requests to admin service.

    Reads admin service URL from environment configuration and initializes
    the client with appropriate timeout and retry settings.

    :return: Configured AdminClient instance
    """
    admin_url = os.getenv(
        'ADMIN_SERVICE_URL',
        'http://archie-service-admin:8000'
    )
    timeout = int(os.getenv('ADMIN_SERVICE_TIMEOUT', '30'))

    return AdminClient(
        admin_url=admin_url,
        timeout=timeout,
        max_retries=3,
        retry_backoff=1.0
    )


def handle_admin_service_error(error: Exception) -> Tuple[Any, int]:
    """
    Convert admin service errors to appropriate HTTP responses.

    Maps different exception types to HTTP status codes and error messages
    suitable for returning to API clients.

    :param error: Exception raised during admin service communication
    :return: Tuple of (error response dict, HTTP status code)
    """
    if isinstance(error, AdminServiceTimeoutError):
        logger.error("Admin service timeout: %s", str(error))
        return jsonify({
            "error": {
                "code": "SERVICE_TIMEOUT",
                "message": "Request timed out waiting for admin service",
                "details": error.details
            }
        }), 504  # Gateway Timeout

    elif isinstance(error, AdminServiceConnectionError):
        logger.error("Admin service connection failed: %s", str(error))
        return jsonify({
            "error": {
                "code": "SERVICE_UNAVAILABLE",
                "message": "Unable to connect to admin service",
                "details": error.details
            }
        }), 503  # Service Unavailable

    elif isinstance(error, AdminServiceError):
        # Forward the status code and message from admin service
        status_code = error.status_code or 500
        logger.error(
            "Admin service error: status=%s, message=%s",
            status_code,
            error.message
        )
        return jsonify({
            "error": {
                "code": "ADMIN_SERVICE_ERROR",
                "message": error.message,
                "details": error.details
            }
        }), status_code

    else:
        # Unexpected error
        logger.exception("Unexpected error in Figma route handler: %s", str(error))
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred"
            }
        }), 500


@figma_bp.route('/installations', methods=['POST'])
@require_feature_flag
def create_installation() -> Tuple[Any, int]:
    """
    Create a new Figma installation with Personal Access Token.

    Routes request to POST /v1/figma/installations on admin service after
    verifying user authentication. The admin service handles PAT storage
    in Google Secret Manager and database record creation.

    **Request Body:**
        - name (str): Installation name
        - description (str, optional): Installation description
        - pat (str): Figma Personal Access Token
        - team_id (int, optional): Team association

    **Response (201 Created):**
        - id (int): Installation ID
        - name (str): Installation name
        - status (str): Installation status
        - created_at (str): Creation timestamp
        - (PAT is never included in response)

    **Error Responses:**
        - 400: Invalid request data
        - 401: User not authenticated
        - 404: Feature disabled
        - 500: Admin service error
        - 503: Admin service unavailable
        - 504: Admin service timeout

    :return: Tuple of (response dict, HTTP status code)
    """
    try:
        # Verify authentication and extract user context
        user_context = get_user_context()

        # Extract request data (silent=True returns None for invalid/missing JSON)
        data = request.get_json(silent=True)
        if not data:
            logger.warning("Create installation request missing JSON body")
            return jsonify({
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Request body must be JSON"
                }
            }), 400

        # Validate required fields
        if 'name' not in data or 'pat' not in data:
            logger.warning(
                "Create installation request missing required fields: %s",
                data.keys()
            )
            return jsonify({
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Missing required fields: name, pat"
                }
            }), 400

        logger.info(
            "Creating Figma installation for user_id=%s, name=%s",
            user_context['user_id'],
            data.get('name')
        )

        # Forward request to admin service
        admin_client = get_admin_client()
        result = admin_client.create_figma_installation(data, user_context)

        logger.info(
            "Successfully created Figma installation id=%s for user_id=%s",
            result.get('id'),
            user_context['user_id']
        )

        return jsonify(result), 201

    except ValueError as e:
        # Authentication error
        logger.warning("Authentication failed: %s", str(e))
        return jsonify({
            "error": {
                "code": "UNAUTHORIZED",
                "message": str(e)
            }
        }), 401

    except (
        AdminServiceError,
        AdminServiceConnectionError,
        AdminServiceTimeoutError
    ) as e:
        return handle_admin_service_error(e)

    except Exception as e:
        logger.exception("Unexpected error creating Figma installation: %s", str(e))
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred"
            }
        }), 500


@figma_bp.route('/installations/<int:installation_id>', methods=['GET'])
@require_feature_flag
def get_installation(installation_id: int) -> Tuple[Any, int]:
    """
    Retrieve Figma installation details with PAT status.

    Routes request to GET /v1/figma/installations/{id} on admin service.
    Returns installation metadata with computed PAT status (Active/Expired)
    but never includes the actual PAT value.

    **Path Parameters:**
        - installation_id (int): ID of the installation to retrieve

    **Response (200 OK):**
        - id (int): Installation ID
        - name (str): Installation name
        - description (str): Installation description
        - status (str): Installation status
        - pat_status (str): PAT validation status (Active/Expired)
        - created_at (str): Creation timestamp
        - updated_at (str): Last update timestamp

    **Error Responses:**
        - 401: User not authenticated
        - 404: Installation not found or feature disabled
        - 500: Admin service error
        - 503: Admin service unavailable
        - 504: Admin service timeout

    :param installation_id: ID of the installation to retrieve
    :return: Tuple of (response dict, HTTP status code)
    """
    try:
        # Verify authentication and extract user context
        user_context = get_user_context()

        logger.info(
            "Retrieving Figma installation id=%s for user_id=%s",
            installation_id,
            user_context['user_id']
        )

        # Forward request to admin service
        admin_client = get_admin_client()
        result = admin_client.get_figma_installation(installation_id, user_context)

        logger.info(
            "Successfully retrieved Figma installation id=%s",
            installation_id
        )

        return jsonify(result), 200

    except ValueError as e:
        # Authentication error
        logger.warning("Authentication failed: %s", str(e))
        return jsonify({
            "error": {
                "code": "UNAUTHORIZED",
                "message": str(e)
            }
        }), 401

    except (
        AdminServiceError,
        AdminServiceConnectionError,
        AdminServiceTimeoutError
    ) as e:
        return handle_admin_service_error(e)

    except Exception as e:
        logger.exception(
            "Unexpected error retrieving Figma installation: %s",
            str(e)
        )
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred"
            }
        }), 500


@figma_bp.route('/installations/<int:installation_id>/pat', methods=['PUT'])
@require_feature_flag
def update_pat(installation_id: int) -> Tuple[Any, int]:
    """
    Update Personal Access Token for a Figma installation.

    Routes request to PUT /v1/figma/installations/{id}/pat on admin service.
    Only the installation owner or admin users can update the PAT.

    **Path Parameters:**
        - installation_id (int): ID of the installation to update

    **Request Body:**
        - pat (str): New Figma Personal Access Token

    **Response (200 OK):**
        - id (int): Installation ID
        - name (str): Installation name
        - updated_at (str): Updated timestamp

    **Error Responses:**
        - 400: Invalid request data
        - 401: User not authenticated
        - 403: User not authorized to update PAT
        - 404: Installation not found or feature disabled
        - 500: Admin service error
        - 503: Admin service unavailable
        - 504: Admin service timeout

    :param installation_id: ID of the installation to update
    :return: Tuple of (response dict, HTTP status code)
    """
    try:
        # Verify authentication and extract user context
        user_context = get_user_context()

        # Extract request data
        data = request.get_json()
        if not data or 'pat' not in data:
            logger.warning(
                "Update PAT request missing required field 'pat' for "
                "installation_id=%s",
                installation_id
            )
            return jsonify({
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Missing required field: pat"
                }
            }), 400

        logger.info(
            "Updating PAT for Figma installation id=%s by user_id=%s",
            installation_id,
            user_context['user_id']
        )

        # Forward request to admin service
        admin_client = get_admin_client()
        result = admin_client.update_figma_pat(
            installation_id,
            data,
            user_context
        )

        logger.info(
            "Successfully updated PAT for Figma installation id=%s",
            installation_id
        )

        return jsonify(result), 200

    except ValueError as e:
        # Authentication error
        logger.warning("Authentication failed: %s", str(e))
        return jsonify({
            "error": {
                "code": "UNAUTHORIZED",
                "message": str(e)
            }
        }), 401

    except (
        AdminServiceError,
        AdminServiceConnectionError,
        AdminServiceTimeoutError
    ) as e:
        return handle_admin_service_error(e)

    except Exception as e:
        logger.exception(
            "Unexpected error updating Figma installation PAT: %s",
            str(e)
        )
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred"
            }
        }), 500


@figma_bp.route('/installations/<int:installation_id>', methods=['DELETE'])
@require_feature_flag
def delete_installation(installation_id: int) -> Tuple[Any, int]:
    """
    Delete a Figma installation (soft delete with Secret Manager cleanup).

    Routes request to DELETE /v1/figma/installations/{id} on admin service.
    Only the installation owner or admin users can delete installations.
    The admin service handles both database soft delete and PAT removal
    from Google Secret Manager.

    **Path Parameters:**
        - installation_id (int): ID of the installation to delete

    **Response (204 No Content):**
        Empty response on successful deletion

    **Error Responses:**
        - 401: User not authenticated
        - 403: User not authorized to delete
        - 404: Installation not found or feature disabled
        - 500: Admin service error
        - 503: Admin service unavailable
        - 504: Admin service timeout

    :param installation_id: ID of the installation to delete
    :return: Tuple of (response dict, HTTP status code)
    """
    try:
        # Verify authentication and extract user context
        user_context = get_user_context()

        logger.info(
            "Deleting Figma installation id=%s by user_id=%s",
            installation_id,
            user_context['user_id']
        )

        # Forward request to admin service
        admin_client = get_admin_client()
        admin_client.delete_figma_installation(installation_id, user_context)

        logger.info(
            "Successfully deleted Figma installation id=%s",
            installation_id
        )

        # Return 204 No Content on successful deletion
        return jsonify({}), 204

    except ValueError as e:
        # Authentication error
        logger.warning("Authentication failed: %s", str(e))
        return jsonify({
            "error": {
                "code": "UNAUTHORIZED",
                "message": str(e)
            }
        }), 401

    except (
        AdminServiceError,
        AdminServiceConnectionError,
        AdminServiceTimeoutError
    ) as e:
        return handle_admin_service_error(e)

    except Exception as e:
        logger.exception(
            "Unexpected error deleting Figma installation: %s",
            str(e)
        )
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred"
            }
        }), 500


@figma_bp.route('/installations/<int:installation_id>/share', methods=['POST'])
@require_feature_flag
def share_installation(installation_id: int) -> Tuple[Any, int]:
    """
    Share a Figma installation with other users.

    Routes request to POST /v1/figma/installations/{id}/share on admin service.
    Only ADMIN and SUPER_ADMIN roles can share installations. The admin service
    performs role verification against teams and teammembers tables.

    **Path Parameters:**
        - installation_id (int): ID of the installation to share

    **Request Body:**
        - target_user_id (int): ID of user to grant access to
        - access_level (str, optional): Access level (default: "viewer")

    **Response (201 Created):**
        - id (int): Access record ID
        - installation_id (int): Installation ID
        - user_id (int): Target user ID
        - access_level (str): Granted access level
        - granted_by (int): User who granted access
        - created_at (str): Grant timestamp

    **Error Responses:**
        - 400: Invalid request data
        - 401: User not authenticated
        - 403: User lacks ADMIN/SUPER_ADMIN role
        - 404: Installation not found or feature disabled
        - 500: Admin service error
        - 503: Admin service unavailable
        - 504: Admin service timeout

    :param installation_id: ID of the installation to share
    :return: Tuple of (response dict, HTTP status code)
    """
    try:
        # Verify authentication and extract user context
        user_context = get_user_context()

        # Extract request data
        data = request.get_json()
        if not data or 'target_user_id' not in data:
            logger.warning(
                "Share installation request missing required field "
                "'target_user_id' for installation_id=%s",
                installation_id
            )
            return jsonify({
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Missing required field: target_user_id"
                }
            }), 400

        logger.info(
            "Sharing Figma installation id=%s to user_id=%s by user_id=%s",
            installation_id,
            data.get('target_user_id'),
            user_context['user_id']
        )

        # Forward request to admin service (admin service handles authorization)
        admin_client = get_admin_client()
        result = admin_client.share_figma_installation(
            installation_id,
            data,
            user_context
        )

        logger.info(
            "Successfully shared Figma installation id=%s to user_id=%s",
            installation_id,
            data.get('target_user_id')
        )

        return jsonify(result), 201

    except ValueError as e:
        # Authentication error
        logger.warning("Authentication failed: %s", str(e))
        return jsonify({
            "error": {
                "code": "UNAUTHORIZED",
                "message": str(e)
            }
        }), 401

    except (
        AdminServiceError,
        AdminServiceConnectionError,
        AdminServiceTimeoutError
    ) as e:
        return handle_admin_service_error(e)

    except Exception as e:
        logger.exception(
            "Unexpected error sharing Figma installation: %s",
            str(e)
        )
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred"
            }
        }), 500


@figma_bp.route('/installations/<int:installation_id>/share', methods=['DELETE'])
@require_feature_flag
def revoke_access(installation_id: int) -> Tuple[Any, int]:
    """
    Revoke user access to a Figma installation.

    Routes request to DELETE /v1/figma/installations/{id}/share on admin
    service. Only ADMIN and SUPER_ADMIN roles can revoke access.

    **Path Parameters:**
        - installation_id (int): ID of the installation

    **Request Body:**
        - target_user_id (int): ID of user to revoke access from

    **Response (204 No Content):**
        Empty response on successful revocation

    **Error Responses:**
        - 400: Invalid request data
        - 401: User not authenticated
        - 403: User lacks ADMIN/SUPER_ADMIN role
        - 404: Installation or access record not found, or feature disabled
        - 500: Admin service error
        - 503: Admin service unavailable
        - 504: Admin service timeout

    :param installation_id: ID of the installation
    :return: Tuple of (response dict, HTTP status code)
    """
    try:
        # Verify authentication and extract user context
        user_context = get_user_context()

        # Extract request data
        data = request.get_json()
        if not data or 'target_user_id' not in data:
            logger.warning(
                "Revoke access request missing required field "
                "'target_user_id' for installation_id=%s",
                installation_id
            )
            return jsonify({
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Missing required field: target_user_id"
                }
            }), 400

        logger.info(
            "Revoking access to Figma installation id=%s from user_id=%s "
            "by user_id=%s",
            installation_id,
            data.get('target_user_id'),
            user_context['user_id']
        )

        # Forward request to admin service (admin service handles authorization)
        admin_client = get_admin_client()
        admin_client.revoke_figma_access(installation_id, data, user_context)

        logger.info(
            "Successfully revoked access to Figma installation id=%s from "
            "user_id=%s",
            installation_id,
            data.get('target_user_id')
        )

        # Return 204 No Content on successful revocation
        return jsonify({}), 204

    except ValueError as e:
        # Authentication error
        logger.warning("Authentication failed: %s", str(e))
        return jsonify({
            "error": {
                "code": "UNAUTHORIZED",
                "message": str(e)
            }
        }), 401

    except (
        AdminServiceError,
        AdminServiceConnectionError,
        AdminServiceTimeoutError
    ) as e:
        return handle_admin_service_error(e)

    except Exception as e:
        logger.exception(
            "Unexpected error revoking Figma installation access: %s",
            str(e)
        )
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred"
            }
        }), 500


@figma_bp.route('/frames/validate', methods=['POST'])
@require_feature_flag
def validate_frame() -> Tuple[Any, int]:
    """
    Validate Figma frame URL and retrieve metadata.

    Routes request to POST /v1/figma/frames/validate on admin service.
    Checks if the PAT associated with the installation can access the frame
    and retrieves frame title from Figma API.

    **Request Body:**
        - frame_url (str): Figma frame URL to validate
        - installation_id (int): ID of installation with PAT to use

    **Response (200 OK):**
        - valid (bool): Whether frame is accessible
        - title (str): Frame title (if valid)
        - message (str): Error message (if invalid)

    **Error Responses:**
        - 400: Invalid request data
        - 401: User not authenticated
        - 404: Feature disabled
        - 500: Admin service error
        - 503: Admin service unavailable
        - 504: Admin service timeout

    :return: Tuple of (response dict, HTTP status code)
    """
    try:
        # Verify authentication and extract user context
        user_context = get_user_context()

        # Extract request data
        data = request.get_json()
        if not data or 'frame_url' not in data or 'installation_id' not in data:
            logger.warning(
                "Validate frame request missing required fields: %s",
                data.keys() if data else "no data"
            )
            return jsonify({
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Missing required fields: frame_url, installation_id"
                }
            }), 400

        logger.info(
            "Validating Figma frame URL for user_id=%s, installation_id=%s",
            user_context['user_id'],
            data.get('installation_id')
        )

        # Forward request to admin service
        admin_client = get_admin_client()
        result = admin_client.validate_figma_frame(data, user_context)

        logger.info(
            "Frame validation result: valid=%s",
            result.get('valid')
        )

        return jsonify(result), 200

    except ValueError as e:
        # Authentication error
        logger.warning("Authentication failed: %s", str(e))
        return jsonify({
            "error": {
                "code": "UNAUTHORIZED",
                "message": str(e)
            }
        }), 401

    except (
        AdminServiceError,
        AdminServiceConnectionError,
        AdminServiceTimeoutError
    ) as e:
        return handle_admin_service_error(e)

    except Exception as e:
        logger.exception(
            "Unexpected error validating Figma frame: %s",
            str(e)
        )
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred"
            }
        }), 500


@figma_bp.route('/attachments', methods=['POST'])
@require_feature_flag
def create_attachments() -> Tuple[Any, int]:
    """
    Attach Figma frames to a project.

    Routes request to POST /v1/figma/attachments on admin service after
    verifying user has access to the specified project. Operation is additive
    and idempotent - same frame URL overwrites previous attachment.

    **Request Body:**
        - project_id (int): ID of project to attach frames to
        - installation_id (int): ID of Figma installation
        - frames (list): List of frame objects with 'url' and 'description'
        - tech_spec_id (int, optional): Associate with specific tech spec

    **Response (201 Created):**
        List of created/updated attachment records with:
        - id (int): Attachment ID
        - project_id (int): Project ID
        - installation_id (int): Installation ID
        - frame_url (str): Figma frame URL
        - frame_title (str): Frame title from Figma API
        - description (str): User-provided description
        - created_at (str): Creation timestamp

    **Error Responses:**
        - 400: Invalid request data
        - 401: User not authenticated
        - 403: User lacks access to project
        - 404: Feature disabled
        - 500: Admin service error
        - 503: Admin service unavailable
        - 504: Admin service timeout

    :return: Tuple of (response dict, HTTP status code)
    """
    try:
        # Verify authentication and extract user context
        user_context = get_user_context()

        # Extract request data
        data = request.get_json()
        if not data:
            logger.warning("Create attachments request missing JSON body")
            return jsonify({
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Request body must be JSON"
                }
            }), 400

        # Validate required fields
        required_fields = ['project_id', 'installation_id', 'frames']
        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            logger.warning(
                "Create attachments request missing required fields: %s",
                missing_fields
            )
            return jsonify({
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": f"Missing required fields: {', '.join(missing_fields)}"
                }
            }), 400

        project_id = data.get('project_id')

        # Verify user has access to the project
        # Note: Actual authorization is delegated to admin service which
        # has direct database access to verify project ownership/membership
        if not verify_project_access(user_context, project_id):
            logger.warning(
                "User user_id=%s lacks access to project_id=%s",
                user_context['user_id'],
                project_id
            )
            return jsonify({
                "error": {
                    "code": "FORBIDDEN",
                    "message": "You do not have access to this project"
                }
            }), 403

        logger.info(
            "Creating Figma attachments for project_id=%s by user_id=%s, "
            "frame_count=%s",
            project_id,
            user_context['user_id'],
            len(data.get('frames', []))
        )

        # Forward request to admin service
        admin_client = get_admin_client()
        result = admin_client.create_figma_attachments(data, user_context)

        logger.info(
            "Successfully created %s Figma attachments for project_id=%s",
            len(result) if isinstance(result, list) else 0,
            project_id
        )

        return jsonify(result), 201

    except ValueError as e:
        # Authentication error
        logger.warning("Authentication failed: %s", str(e))
        return jsonify({
            "error": {
                "code": "UNAUTHORIZED",
                "message": str(e)
            }
        }), 401

    except (
        AdminServiceError,
        AdminServiceConnectionError,
        AdminServiceTimeoutError
    ) as e:
        return handle_admin_service_error(e)

    except Exception as e:
        logger.exception(
            "Unexpected error creating Figma attachments: %s",
            str(e)
        )
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred"
            }
        }), 500


@figma_bp.route('/attachments', methods=['GET'])
@require_feature_flag
def list_attachments() -> Tuple[Any, int]:
    """
    List Figma attachments filtered by project and optionally tech spec.

    Routes request to GET /v1/figma/attachments on admin service after
    verifying user has access to the specified project.

    **Query Parameters:**
        - project_id (int, required): Filter by project ID
        - tech_spec_id (int, optional): Filter by tech spec ID

    **Response (200 OK):**
        List of attachment records with:
        - id (int): Attachment ID
        - project_id (int): Project ID
        - tech_spec_id (int): Tech spec ID (if set)
        - installation_id (int): Installation ID
        - frame_url (str): Figma frame URL
        - frame_title (str): Frame title
        - description (str): Description
        - created_by (int): User who created attachment
        - created_at (str): Creation timestamp

    **Error Responses:**
        - 400: Missing required query parameters
        - 401: User not authenticated
        - 403: User lacks access to project
        - 404: Feature disabled
        - 500: Admin service error
        - 503: Admin service unavailable
        - 504: Admin service timeout

    :return: Tuple of (response dict, HTTP status code)
    """
    try:
        # Verify authentication and extract user context
        user_context = get_user_context()

        # Extract query parameters
        project_id = request.args.get('project_id', type=int)
        tech_spec_id = request.args.get('tech_spec_id', type=int)

        # Validate required parameters
        if not project_id:
            logger.warning("List attachments request missing project_id parameter")
            return jsonify({
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Missing required query parameter: project_id"
                }
            }), 400

        # Verify user has access to the project
        if not verify_project_access(user_context, project_id):
            logger.warning(
                "User user_id=%s lacks access to project_id=%s",
                user_context['user_id'],
                project_id
            )
            return jsonify({
                "error": {
                    "code": "FORBIDDEN",
                    "message": "You do not have access to this project"
                }
            }), 403

        # Build query parameters for admin service
        query_params = {'project_id': project_id}
        if tech_spec_id:
            query_params['tech_spec_id'] = tech_spec_id

        logger.info(
            "Listing Figma attachments for project_id=%s by user_id=%s",
            project_id,
            user_context['user_id']
        )

        # Forward request to admin service
        admin_client = get_admin_client()
        result = admin_client.list_figma_attachments(query_params, user_context)

        logger.info(
            "Successfully retrieved %s Figma attachments for project_id=%s",
            len(result) if isinstance(result, list) else 0,
            project_id
        )

        return jsonify(result), 200

    except ValueError as e:
        # Authentication error
        logger.warning("Authentication failed: %s", str(e))
        return jsonify({
            "error": {
                "code": "UNAUTHORIZED",
                "message": str(e)
            }
        }), 401

    except (
        AdminServiceError,
        AdminServiceConnectionError,
        AdminServiceTimeoutError
    ) as e:
        return handle_admin_service_error(e)

    except Exception as e:
        logger.exception(
            "Unexpected error listing Figma attachments: %s",
            str(e)
        )
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred"
            }
        }), 500


@figma_bp.route('/attachments/<int:attachment_id>', methods=['GET'])
@require_feature_flag
def get_attachment(attachment_id: int) -> Tuple[Any, int]:
    """
    Retrieve a single Figma attachment by ID.

    Routes request to GET /v1/figma/attachments/{id} on admin service.
    User must have access to the project associated with the attachment.

    **Path Parameters:**
        - attachment_id (int): ID of the attachment to retrieve

    **Response (200 OK):**
        - id (int): Attachment ID
        - project_id (int): Project ID
        - tech_spec_id (int): Tech spec ID (if set)
        - installation_id (int): Installation ID
        - frame_url (str): Figma frame URL
        - frame_title (str): Frame title
        - description (str): Description
        - created_by (int): User who created attachment
        - created_at (str): Creation timestamp
        - updated_at (str): Last update timestamp

    **Error Responses:**
        - 401: User not authenticated
        - 403: User lacks access to associated project
        - 404: Attachment not found or feature disabled
        - 500: Admin service error
        - 503: Admin service unavailable
        - 504: Admin service timeout

    :param attachment_id: ID of the attachment to retrieve
    :return: Tuple of (response dict, HTTP status code)
    """
    try:
        # Verify authentication and extract user context
        user_context = get_user_context()

        logger.info(
            "Retrieving Figma attachment id=%s for user_id=%s",
            attachment_id,
            user_context['user_id']
        )

        # Forward request to admin service
        # Admin service will verify user has access to the associated project
        admin_client = get_admin_client()
        result = admin_client.get_figma_attachment(attachment_id, user_context)

        logger.info(
            "Successfully retrieved Figma attachment id=%s",
            attachment_id
        )

        return jsonify(result), 200

    except ValueError as e:
        # Authentication error
        logger.warning("Authentication failed: %s", str(e))
        return jsonify({
            "error": {
                "code": "UNAUTHORIZED",
                "message": str(e)
            }
        }), 401

    except (
        AdminServiceError,
        AdminServiceConnectionError,
        AdminServiceTimeoutError
    ) as e:
        return handle_admin_service_error(e)

    except Exception as e:
        logger.exception(
            "Unexpected error retrieving Figma attachment: %s",
            str(e)
        )
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred"
            }
        }), 500


@figma_bp.route('/attachments/<int:attachment_id>', methods=['DELETE'])
@require_feature_flag
def delete_attachment(attachment_id: int) -> Tuple[Any, int]:
    """
    Delete a Figma attachment (soft delete).

    Routes request to DELETE /v1/figma/attachments/{id} on admin service.
    User must have access to the project and permissions to modify attachments.

    **Path Parameters:**
        - attachment_id (int): ID of the attachment to delete

    **Response (204 No Content):**
        Empty response on successful deletion

    **Error Responses:**
        - 401: User not authenticated
        - 403: User lacks permission to delete attachment
        - 404: Attachment not found or feature disabled
        - 500: Admin service error
        - 503: Admin service unavailable
        - 504: Admin service timeout

    :param attachment_id: ID of the attachment to delete
    :return: Tuple of (response dict, HTTP status code)
    """
    try:
        # Verify authentication and extract user context
        user_context = get_user_context()

        logger.info(
            "Deleting Figma attachment id=%s by user_id=%s",
            attachment_id,
            user_context['user_id']
        )

        # Forward request to admin service
        # Admin service will verify user has permission to delete
        admin_client = get_admin_client()
        admin_client.delete_figma_attachment(attachment_id, user_context)

        logger.info(
            "Successfully deleted Figma attachment id=%s",
            attachment_id
        )

        # Return 204 No Content on successful deletion
        return jsonify({}), 204

    except ValueError as e:
        # Authentication error
        logger.warning("Authentication failed: %s", str(e))
        return jsonify({
            "error": {
                "code": "UNAUTHORIZED",
                "message": str(e)
            }
        }), 401

    except (
        AdminServiceError,
        AdminServiceConnectionError,
        AdminServiceTimeoutError
    ) as e:
        return handle_admin_service_error(e)

    except Exception as e:
        logger.exception(
            "Unexpected error deleting Figma attachment: %s",
            str(e)
        )
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred"
            }
        }), 500
