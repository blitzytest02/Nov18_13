"""
Flask route handlers for Figma integration API endpoints.

This module implements all HTTP route handlers for the Figma integration feature
in archie-service-admin. It follows a thin controller pattern where route handlers
contain NO business logic - only request validation, authentication, authorization,
and delegation to FigmaService.

Architecture Pattern:
    Route handlers implement a three-step pattern:
    1. Feature flag check (FIGMA_INTEGRATION_ENABLED)
    2. Request validation and user authentication/authorization
    3. Delegation to FigmaService with proper error handling

Route handlers MUST NOT contain:
    - Business logic or data manipulation
    - Direct database access
    - Direct Secret Manager operations
    - Direct Figma API calls
    - Complex calculations or transformations

All business logic resides in FigmaService, which coordinates operations across
repositories while maintaining transactional consistency.

Security Model:
    - All public endpoints check FIGMA_INTEGRATION_ENABLED feature flag
    - User authentication verified via get_current_user() helper
    - Authorization checks delegated to service layer (e.g., ADMIN/SUPER_ADMIN for sharing)
    - PAT values NEVER included in responses (except internal endpoint)
    - Standardized error responses prevent information leakage

Error Response Format:
    All errors return JSON in the standard format:
    {
        "error": {
            "code": "ERROR_CODE",
            "message": "Human-readable message",
            "details": {}
        }
    }

Internal Endpoint:
    GET /internal/figma/installations/by-project/{project_id}
    This endpoint is INTERNAL ONLY and returns the actual PAT value. It must NOT
    be exposed through archie-service-backend. Used by platform-event-listener
    and other internal services.

Blueprint Registration:
    The figma_blueprint is registered in src/routes/__init__.py with the prefix
    '/v1/figma' for public endpoints and '/internal/figma' for internal endpoints.
"""

import logging
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple, Union

from flask import Blueprint, make_response, request, Response

# Import service layer for business logic delegation
from ..services.figma_service import FigmaService

# Import configuration repository for feature flag access
from ..repositories.config_repository import ConfigRepository


# Configure module logger for request/response tracking
logger = logging.getLogger(__name__)

# Initialize configuration repository for feature flag checks
config_repo = ConfigRepository()

# Create Flask Blueprint for Figma routes
# This blueprint will be registered in src/routes/__init__.py
figma_blueprint = Blueprint('figma', __name__)


def require_feature_flag(func: Callable) -> Callable:
    """
    Decorator to enforce FIGMA_INTEGRATION_ENABLED feature flag on route handlers.

    This decorator checks the configuration for the FIGMA_INTEGRATION_ENABLED boolean
    flag before allowing the route handler to execute. If the flag is disabled (False
    or not set), returns a 404 Not Found response indicating the feature is not available.

    Why 404 instead of 403:
        Returning 404 for disabled features prevents information disclosure about
        available endpoints. It makes the feature appear as if it doesn't exist
        when disabled, which is appropriate security behavior.

    Usage:
        @figma_blueprint.route('/installations', methods=['POST'])
        @require_feature_flag
        def create_installation():
            # Route implementation

    :param func: Route handler function to wrap
    :type func: Callable
    :return: Wrapped function with feature flag check
    :rtype: Callable
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        """
        Wrapper function that checks feature flag before executing route handler.

        :param args: Positional arguments passed to route handler
        :param kwargs: Keyword arguments passed to route handler
        :return: Route handler result or error response
        """
        # Check if Figma integration is enabled in configuration
        # Default to False if not set for fail-safe behavior
        is_enabled = config_repo.get_bool('FIGMA_INTEGRATION_ENABLED', default=False)

        if not is_enabled:
            logger.warning(
                f"Attempt to access Figma endpoint {request.path} while "
                f"FIGMA_INTEGRATION_ENABLED is disabled"
            )
            return _error_response(
                code="FEATURE_DISABLED",
                message="Figma integration is not enabled",
                status=404
            )

        # Feature flag is enabled - proceed with route handler
        return func(*args, **kwargs)

    return wrapper


def get_current_user() -> Optional[Dict[str, Any]]:
    """
    Extract authenticated user context from request.

    This helper function retrieves user information from the Flask request context.
    In a production Flask application, this typically involves:
    - Extracting JWT token from Authorization header
    - Validating token signature and expiration
    - Decoding user claims (user_id, email, roles, etc.)
    - Returning user dict or None if not authenticated

    Implementation Note:
        This is a placeholder implementation that would need to integrate with
        the actual authentication middleware used by archie-service-admin.
        Common patterns include Flask-JWT-Extended, Flask-Login, or custom
        JWT validation middleware.

    :return: Dictionary with user information (user_id, email, roles) or None
    :rtype: Optional[Dict[str, Any]]
    """
    # TODO: Integrate with actual authentication middleware
    # This is a functional placeholder that extracts user_id from request context
    # In production, this would validate JWT tokens and extract user claims

    # Example implementation pattern:
    # from flask import g
    # return g.current_user if hasattr(g, 'current_user') else None

    # For functional implementation, check if user_id is provided
    # This would be set by authentication middleware
    user_id = getattr(request, 'user_id', None)

    if user_id:
        return {'user_id': user_id}

    # Check request JSON for user_id (for testing/development)
    # Remove this in production - auth should be via headers/middleware
    if request.json and 'user_id' in request.json:
        return {'user_id': request.json['user_id']}

    return None


def require_authentication(func: Callable) -> Callable:
    """
    Decorator to enforce user authentication on route handlers.

    Verifies that the request contains valid authentication credentials by checking
    for current user context. Returns 401 Unauthorized if authentication fails.

    :param func: Route handler function to wrap
    :type func: Callable
    :return: Wrapped function with authentication check
    :rtype: Callable
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        """
        Wrapper function that checks authentication before executing route handler.

        :param args: Positional arguments passed to route handler
        :param kwargs: Keyword arguments passed to route handler
        :return: Route handler result or error response
        """
        user = get_current_user()

        if not user:
            logger.warning(f"Unauthenticated attempt to access {request.path}")
            return _error_response(
                code="UNAUTHORIZED",
                message="Authentication required",
                status=401
            )

        # Store user in request context for route handlers to access
        # Using setattr to avoid mypy attribute-defined errors
        setattr(request, 'current_user', user)

        return func(*args, **kwargs)

    return wrapper


def _get_request_user() -> Dict[str, Any]:
    """
    Safely get current user from request context.

    This helper function retrieves the current_user attribute that was set by
    the require_authentication decorator. Uses getattr to avoid mypy errors.

    :return: Dictionary with user information (user_id, etc.)
    :rtype: Dict[str, Any]
    """
    return getattr(request, 'current_user', {})


def _error_response(
    code: str,
    message: str,
    status: int = 400,
    details: Optional[Dict[str, Any]] = None
) -> Tuple[Dict[str, Any], int]:
    """
    Create standardized error response following API contract.

    All error responses follow the format:
    {
        "error": {
            "code": "ERROR_CODE",
            "message": "Human-readable message",
            "details": {}
        }
    }

    This standardization enables:
    - Consistent error handling in client applications
    - Automated error monitoring and alerting
    - Clear distinction between error types via error codes

    Error Codes:
        - FEATURE_DISABLED: FIGMA_INTEGRATION_ENABLED is false
        - UNAUTHORIZED: User not authenticated
        - INSTALLATION_NOT_FOUND: Installation ID does not exist
        - PAT_STORAGE_FAILED: Secret Manager operation failed
        - INVALID_PAT: PAT format or value invalid
        - FRAME_VALIDATION_FAILED: Cannot access frame with provided PAT
        - INVALID_REQUEST: Request validation failed
        - PERMISSION_DENIED: User lacks required permissions
        - INTERNAL_ERROR: Unexpected server error

    :param code: Error code identifying the error type
    :type code: str
    :param message: Human-readable error message
    :type message: str
    :param status: HTTP status code (default 400)
    :type status: int
    :param details: Optional additional error details
    :type details: Optional[Dict[str, Any]]
    :return: Tuple of (error dict, status code) for Flask response
    :rtype: Tuple[Dict[str, Any], int]
    """
    error_response = {
        "error": {
            "code": code,
            "message": message,
            "details": details or {}
        }
    }

    return error_response, status


def _success_response(
    data: Any,
    status: int = 200,
    message: Optional[str] = None
) -> Tuple[Dict[str, Any], int]:
    """
    Create standardized success response with optional message.

    :param data: Response data (dict, list, or primitive type)
    :type data: Any
    :param status: HTTP status code (default 200)
    :type status: int
    :param message: Optional success message
    :type message: Optional[str]
    :return: Tuple of (response dict, status code) for Flask response
    :rtype: Tuple[Dict[str, Any], int]
    """
    if message:
        return {"data": data, "message": message}, status
    return data, status


# =============================================================================
# Route Handlers - Installation Management
# =============================================================================

@figma_blueprint.route('/installations', methods=['POST'])
@require_feature_flag
@require_authentication
def create_installation() -> Tuple[Dict[str, Any], int]:
    """
    Create new Figma installation with PAT stored in Secret Manager.

    This endpoint implements the "Connect Figma Integration" feature (A.1), allowing
    users to register their Figma Personal Access Tokens for use within the platform.
    The PAT is securely stored in Google Secret Manager and never returned in responses.

    Request Body:
        {
            "name": "string (required)",
            "description": "string (optional)",
            "pat": "string (required)",
            "team_id": integer (optional)
        }

    Response (201 Created):
        {
            "id": integer,
            "user_id": integer,
            "team_id": integer or null,
            "name": "string",
            "description": "string or null",
            "status": "active",
            "created_at": "ISO 8601 timestamp",
            "updated_at": "ISO 8601 timestamp"
        }

    Note: PAT value is NOT included in response for security reasons.

    Error Responses:
        400 Bad Request: Missing required fields or validation failure
        401 Unauthorized: User not authenticated
        500 Internal Server Error: Secret Manager operation failed

    :return: Tuple of (response dict, status code)
    :rtype: Tuple[Dict[str, Any], int]
    """
    logger.info(f"POST /installations - User: {_get_request_user().get('user_id')}")

    try:
        # Extract and validate request data
        data = request.get_json()

        if not data:
            return _error_response(
                code="INVALID_REQUEST",
                message="Request body is required",
                status=400
            )

        # Validate required fields
        name = data.get('name', '').strip()
        pat = data.get('pat', '').strip()

        if not name:
            return _error_response(
                code="INVALID_REQUEST",
                message="name is required and cannot be empty",
                status=400
            )

        if not pat:
            return _error_response(
                code="INVALID_REQUEST",
                message="pat is required and cannot be empty",
                status=400
            )

        # Extract optional fields
        description = data.get('description', '').strip() if data.get('description') else None
        team_id = data.get('team_id')

        # Delegate to service layer for business logic
        # Service handles: PAT storage, transaction management, error handling
        service = FigmaService()
        installation = service.create_installation(
            user_id=_get_request_user()['user_id'],
            name=name,
            pat=pat,
            description=description,
            team_id=team_id
        )

        logger.info(f"Successfully created installation {installation['id']}")

        # Return 201 Created with installation metadata (no PAT)
        return _success_response(installation, status=201)

    except ValueError as e:
        # Validation error from service layer
        logger.error(f"Validation error creating installation: {e}")
        return _error_response(
            code="INVALID_REQUEST",
            message=str(e),
            status=400
        )
    except Exception as e:
        # Unexpected error (Secret Manager failure, database error, etc.)
        logger.error(f"Error creating installation: {e}", exc_info=True)
        return _error_response(
            code="PAT_STORAGE_FAILED",
            message="Failed to create installation. Please try again.",
            status=500
        )


@figma_blueprint.route('/installations/<int:installation_id>', methods=['GET'])
@require_feature_flag
@require_authentication
def get_installation(installation_id: int) -> Tuple[Dict[str, Any], int]:
    """
    Retrieve Figma installation with computed PAT status.

    This endpoint implements the "Get Figma Integration" feature (A.4), returning
    installation metadata with computed PAT status (Active/Expired) determined by
    validating the PAT against the Figma API.

    Path Parameters:
        installation_id: Integer ID of installation to retrieve

    Response (200 OK):
        {
            "id": integer,
            "user_id": integer,
            "team_id": integer or null,
            "name": "string",
            "description": "string or null",
            "status": "active",
            "pat_status": "Active" or "Expired",
            "created_at": "ISO 8601 timestamp",
            "updated_at": "ISO 8601 timestamp"
        }

    Note: PAT value is NOT included - only status (Active/Expired).

    Error Responses:
        401 Unauthorized: User not authenticated
        404 Not Found: Installation does not exist or is deleted

    :param installation_id: ID of installation to retrieve
    :type installation_id: int
    :return: Tuple of (response dict, status code)
    :rtype: Tuple[Dict[str, Any], int]
    """
    logger.info(
        f"GET /installations/{installation_id} - User: {_get_request_user().get('user_id')}"
    )

    try:
        # Delegate to service layer
        # Service handles: PAT retrieval, validation, status computation
        service = FigmaService()
        installation = service.get_installation(installation_id)

        if not installation:
            logger.info(f"Installation {installation_id} not found")
            return _error_response(
                code="INSTALLATION_NOT_FOUND",
                message=f"Installation {installation_id} not found",
                status=404
            )

        logger.info(
            f"Retrieved installation {installation_id} with PAT status: "
            f"{installation.get('pat_status')}"
        )

        return _success_response(installation, status=200)

    except ValueError as e:
        logger.error(f"Validation error retrieving installation: {e}")
        return _error_response(
            code="INVALID_REQUEST",
            message=str(e),
            status=400
        )
    except Exception as e:
        logger.error(f"Error retrieving installation {installation_id}: {e}", exc_info=True)
        return _error_response(
            code="INTERNAL_ERROR",
            message="Failed to retrieve installation",
            status=500
        )


@figma_blueprint.route('/installations/<int:installation_id>/pat', methods=['PUT'])
@require_feature_flag
@require_authentication
def update_pat(installation_id: int) -> Tuple[Dict[str, Any], int]:
    """
    Update PAT for Figma installation.

    This endpoint implements the "Update PAT" feature (A.5), allowing users to rotate
    their Figma Personal Access Tokens. Only the installation owner can update the PAT.
    The operation is atomic - if Secret Manager update fails, database changes are
    rolled back.

    Path Parameters:
        installation_id: Integer ID of installation to update

    Request Body:
        {
            "new_pat": "string (required)"
        }

    Response (200 OK):
        {
            "id": integer,
            "user_id": integer,
            "team_id": integer or null,
            "name": "string",
            "description": "string or null",
            "status": "active",
            "updated_at": "ISO 8601 timestamp"
        }

    Error Responses:
        400 Bad Request: Missing or invalid new_pat
        401 Unauthorized: User not authenticated
        403 Forbidden: User does not own this installation
        404 Not Found: Installation does not exist
        500 Internal Server Error: Secret Manager update failed

    :param installation_id: ID of installation to update
    :type installation_id: int
    :return: Tuple of (response dict, status code)
    :rtype: Tuple[Dict[str, Any], int]
    """
    logger.info(
        f"PUT /installations/{installation_id}/pat - User: {_get_request_user().get('user_id')}"
    )

    try:
        # Extract and validate request data
        data = request.get_json()

        if not data:
            return _error_response(
                code="INVALID_REQUEST",
                message="Request body is required",
                status=400
            )

        new_pat = data.get('new_pat', '').strip()

        if not new_pat:
            return _error_response(
                code="INVALID_REQUEST",
                message="new_pat is required and cannot be empty",
                status=400
            )

        # Delegate to service layer
        # Service handles: Authorization check, Secret Manager update, transaction management
        service = FigmaService()
        updated_installation = service.update_pat(
            installation_id=installation_id,
            new_pat=new_pat,
            user_id=_get_request_user()['user_id']
        )

        logger.info(f"Successfully updated PAT for installation {installation_id}")

        return _success_response(updated_installation, status=200)

    except ValueError as e:
        # Validation error or installation not found
        logger.error(f"Validation error updating PAT: {e}")
        return _error_response(
            code="INVALID_REQUEST",
            message=str(e),
            status=404 if "not found" in str(e).lower() else 400
        )
    except PermissionError as e:
        # User does not own this installation
        logger.warning(f"Permission denied updating PAT: {e}")
        return _error_response(
            code="PERMISSION_DENIED",
            message="You do not have permission to update this installation",
            status=403
        )
    except Exception as e:
        # Secret Manager failure or unexpected error
        logger.error(f"Error updating PAT for installation {installation_id}: {e}", exc_info=True)
        return _error_response(
            code="PAT_STORAGE_FAILED",
            message="Failed to update PAT. Please try again.",
            status=500
        )


@figma_blueprint.route('/installations/<int:installation_id>', methods=['DELETE'])
@require_feature_flag
@require_authentication
def delete_installation(installation_id: int) -> Union[Tuple[Dict[str, Any], int], Response]:
    """
    Soft delete Figma installation and remove PAT from Secret Manager.

    This endpoint implements the "Disconnect Figma Integration" feature (A.3), soft
    deleting the installation record and removing the PAT from Secret Manager. Only
    the installation owner can delete the installation.

    Path Parameters:
        installation_id: Integer ID of installation to delete

    Response (204 No Content):
        Empty response body

    Error Responses:
        401 Unauthorized: User not authenticated
        403 Forbidden: User does not own this installation
        404 Not Found: Installation does not exist
        500 Internal Server Error: Secret Manager deletion failed

    :param installation_id: ID of installation to delete
    :type installation_id: int
    :return: Tuple of (response dict, status code) or Response object
    :rtype: Union[Tuple[Dict[str, Any], int], Response]
    """
    logger.info(
        f"DELETE /installations/{installation_id} - User: {_get_request_user().get('user_id')}"
    )

    try:
        # Delegate to service layer
        # Service handles: Authorization check, soft delete, Secret Manager cleanup
        service = FigmaService()
        success = service.delete_installation(
            installation_id=installation_id,
            user_id=_get_request_user()['user_id']
        )

        if success:
            logger.info(f"Successfully deleted installation {installation_id}")
            # Return 204 No Content for successful deletion
            return make_response('', 204)
        else:
            return _error_response(
                code="INTERNAL_ERROR",
                message="Failed to delete installation",
                status=500
            )

    except ValueError as e:
        # Installation not found
        logger.error(f"Validation error deleting installation: {e}")
        return _error_response(
            code="INSTALLATION_NOT_FOUND",
            message=str(e),
            status=404
        )
    except PermissionError as e:
        # User does not own this installation
        logger.warning(f"Permission denied deleting installation: {e}")
        return _error_response(
            code="PERMISSION_DENIED",
            message="You do not have permission to delete this installation",
            status=403
        )
    except Exception as e:
        # Secret Manager failure or unexpected error
        logger.error(f"Error deleting installation {installation_id}: {e}", exc_info=True)
        return _error_response(
            code="PAT_STORAGE_FAILED",
            message="Failed to delete installation. Please try again.",
            status=500
        )


@figma_blueprint.route('/installations', methods=['GET'])
@require_feature_flag
@require_authentication
def list_installations() -> Tuple[Dict[str, Any], int]:
    """
    List Figma installations with optional filtering.

    Returns all active (not soft-deleted) installations, optionally filtered by
    user ownership or team association.

    Query Parameters:
        user_id: Optional integer to filter by installation owner
        team_id: Optional integer to filter by team association

    Response (200 OK):
        [
            {
                "id": integer,
                "user_id": integer,
                "team_id": integer or null,
                "name": "string",
                "description": "string or null",
                "status": "active",
                "created_at": "ISO 8601 timestamp",
                "updated_at": "ISO 8601 timestamp"
            },
            ...
        ]

    Note: PAT and PAT status are NOT included for performance reasons.
          Use GET /installations/{id} for individual installation details.

    Error Responses:
        400 Bad Request: Invalid query parameters
        401 Unauthorized: User not authenticated

    :return: Tuple of (response dict, status code)
    :rtype: Tuple[Dict[str, Any], int]
    """
    logger.info(f"GET /installations - User: {_get_request_user().get('user_id')}")

    try:
        # Extract optional query parameters
        user_id = request.args.get('user_id', type=int)
        team_id = request.args.get('team_id', type=int)

        # Delegate to service layer
        service = FigmaService()
        installations = service.list_installations(user_id=user_id, team_id=team_id)

        logger.info(f"Retrieved {len(installations)} installations")

        return _success_response(installations, status=200)

    except ValueError as e:
        logger.error(f"Validation error listing installations: {e}")
        return _error_response(
            code="INVALID_REQUEST",
            message=str(e),
            status=400
        )
    except Exception as e:
        logger.error(f"Error listing installations: {e}", exc_info=True)
        return _error_response(
            code="INTERNAL_ERROR",
            message="Failed to list installations",
            status=500
        )


# =============================================================================
# Route Handlers - Installation Sharing
# =============================================================================

@figma_blueprint.route('/installations/<int:installation_id>/share', methods=['POST'])
@require_feature_flag
@require_authentication
def share_installation(installation_id: int) -> Tuple[Dict[str, Any], int]:
    """
    Share Figma installation with user (ADMIN/SUPER_ADMIN only).

    This endpoint implements the "Share Figma Integration" feature (A.2), allowing
    administrators to grant other users access to use an installation's PAT. Only
    users with ADMIN or SUPER_ADMIN roles can share installations.

    Path Parameters:
        installation_id: Integer ID of installation to share

    Request Body:
        {
            "target_user_id": integer (required),
            "access_level": "viewer" | "editor" | "admin" (optional, default: "viewer")
        }

    Response (200 OK):
        {
            "id": integer,
            "installation_id": integer,
            "user_id": integer,
            "access_level": "string",
            "granted_by": integer,
            "created_at": "ISO 8601 timestamp"
        }

    Error Responses:
        400 Bad Request: Missing or invalid request data
        401 Unauthorized: User not authenticated
        403 Forbidden: User lacks ADMIN or SUPER_ADMIN role
        404 Not Found: Installation does not exist

    :param installation_id: ID of installation to share
    :type installation_id: int
    :return: Tuple of (response dict, status code)
    :rtype: Tuple[Dict[str, Any], int]
    """
    logger.info(
        f"POST /installations/{installation_id}/share - User: {_get_request_user().get('user_id')}"
    )

    try:
        # Extract and validate request data
        data = request.get_json()

        if not data:
            return _error_response(
                code="INVALID_REQUEST",
                message="Request body is required",
                status=400
            )

        target_user_id = data.get('target_user_id')
        access_level = data.get('access_level', 'viewer')

        if not target_user_id:
            return _error_response(
                code="INVALID_REQUEST",
                message="target_user_id is required",
                status=400
            )

        if access_level not in ['viewer', 'editor', 'admin']:
            return _error_response(
                code="INVALID_REQUEST",
                message="access_level must be viewer, editor, or admin",
                status=400
            )

        # Delegate to service layer
        # Service handles: Role verification (ADMIN/SUPER_ADMIN), access grant creation
        service = FigmaService()
        access_grant = service.share_installation(
            installation_id=installation_id,
            target_user_id=target_user_id,
            requesting_user_id=_get_request_user()['user_id'],
            access_level=access_level
        )

        logger.info(
            f"Successfully shared installation {installation_id} with user {target_user_id}"
        )

        return _success_response(access_grant, status=200)

    except ValueError as e:
        # Validation error or installation not found
        logger.error(f"Validation error sharing installation: {e}")
        return _error_response(
            code="INVALID_REQUEST",
            message=str(e),
            status=404 if "not found" in str(e).lower() else 400
        )
    except PermissionError as e:
        # User lacks ADMIN or SUPER_ADMIN role
        logger.warning(f"Permission denied sharing installation: {e}")
        return _error_response(
            code="PERMISSION_DENIED",
            message="Only ADMIN and SUPER_ADMIN users can share installations",
            status=403
        )
    except Exception as e:
        logger.error(f"Error sharing installation {installation_id}: {e}", exc_info=True)
        return _error_response(
            code="INTERNAL_ERROR",
            message="Failed to share installation",
            status=500
        )


@figma_blueprint.route('/installations/<int:installation_id>/share', methods=['DELETE'])
@require_feature_flag
@require_authentication
def revoke_access(installation_id: int) -> Union[Tuple[Dict[str, Any], int], Response]:
    """
    Revoke user access to Figma installation.

    Soft deletes the access grant record, preventing the specified user from using
    the installation's PAT.

    Path Parameters:
        installation_id: Integer ID of installation

    Request Body:
        {
            "user_id": integer (required)
        }

    Response (204 No Content):
        Empty response body

    Error Responses:
        400 Bad Request: Missing user_id
        401 Unauthorized: User not authenticated
        404 Not Found: Installation or access grant not found

    :param installation_id: ID of installation
    :type installation_id: int
    :return: Tuple of (response dict, status code) or Response object
    :rtype: Union[Tuple[Dict[str, Any], int], Response]
    """
    logger.info(
        f"DELETE /installations/{installation_id}/share - "
        f"User: {_get_request_user().get('user_id')}"
    )

    try:
        # Extract and validate request data
        data = request.get_json()

        if not data:
            return _error_response(
                code="INVALID_REQUEST",
                message="Request body is required",
                status=400
            )

        user_id = data.get('user_id')

        if not user_id:
            return _error_response(
                code="INVALID_REQUEST",
                message="user_id is required",
                status=400
            )

        # Delegate to service layer
        service = FigmaService()
        revoked = service.revoke_access(installation_id=installation_id, user_id=user_id)

        if revoked:
            logger.info(f"Successfully revoked access for user {user_id}")
            return make_response('', 204)
        else:
            return _error_response(
                code="INSTALLATION_NOT_FOUND",
                message="No active access found to revoke",
                status=404
            )

    except ValueError as e:
        logger.error(f"Validation error revoking access: {e}")
        return _error_response(
            code="INVALID_REQUEST",
            message=str(e),
            status=400
        )
    except Exception as e:
        logger.error(
            f"Error revoking access for installation {installation_id}: {e}",
            exc_info=True
        )
        return _error_response(
            code="INTERNAL_ERROR",
            message="Failed to revoke access",
            status=500
        )


@figma_blueprint.route('/installations/<int:installation_id>/access', methods=['GET'])
@require_feature_flag
@require_authentication
def list_access(installation_id: int) -> Tuple[Dict[str, Any], int]:
    """
    List all users with access to Figma installation.

    Returns all active (not revoked) access grants for the specified installation.

    Path Parameters:
        installation_id: Integer ID of installation

    Response (200 OK):
        [
            {
                "id": integer,
                "installation_id": integer,
                "user_id": integer,
                "access_level": "string",
                "granted_by": integer,
                "created_at": "ISO 8601 timestamp"
            },
            ...
        ]

    Error Responses:
        400 Bad Request: Invalid installation_id
        401 Unauthorized: User not authenticated

    :param installation_id: ID of installation
    :type installation_id: int
    :return: Tuple of (response dict, status code)
    :rtype: Tuple[Dict[str, Any], int]
    """
    logger.info(
        f"GET /installations/{installation_id}/access - User: {_get_request_user().get('user_id')}"
    )

    try:
        # Delegate to service layer
        service = FigmaService()
        access_list = service.list_installation_access(installation_id)

        logger.info(
            f"Retrieved {len(access_list)} access grants "
            f"for installation {installation_id}"
        )

        return _success_response(access_list, status=200)

    except ValueError as e:
        logger.error(f"Validation error listing access: {e}")
        return _error_response(
            code="INVALID_REQUEST",
            message=str(e),
            status=400
        )
    except Exception as e:
        logger.error(f"Error listing access for installation {installation_id}: {e}", exc_info=True)
        return _error_response(
            code="INTERNAL_ERROR",
            message="Failed to list access grants",
            status=500
        )


# =============================================================================
# Route Handlers - Frame Management
# =============================================================================

@figma_blueprint.route('/frames/validate', methods=['POST'])
@require_feature_flag
@require_authentication
def validate_frame() -> Tuple[Dict[str, Any], int]:
    """
    Validate Figma frame URL and retrieve frame title.

    This endpoint implements frame validation (A.7.1.1), verifying that the
    installation's PAT can successfully access the specified frame URL.

    Request Body:
        {
            "frame_url": "string (required)",
            "installation_id": integer (required)
        }

    Response (200 OK):
        {
            "valid": boolean,
            "title": "string",
            "message": "string"
        }

    Note: If valid=false, title will be empty and message will contain error details.

    Error Responses:
        400 Bad Request: Missing required fields
        401 Unauthorized: User not authenticated
        404 Not Found: Installation does not exist

    :return: Tuple of (response dict, status code)
    :rtype: Tuple[Dict[str, Any], int]
    """
    logger.info(f"POST /frames/validate - User: {_get_request_user().get('user_id')}")

    try:
        # Extract and validate request data
        data = request.get_json()

        if not data:
            return _error_response(
                code="INVALID_REQUEST",
                message="Request body is required",
                status=400
            )

        frame_url = data.get('frame_url', '').strip()
        installation_id = data.get('installation_id')

        if not frame_url:
            return _error_response(
                code="INVALID_REQUEST",
                message="frame_url is required",
                status=400
            )

        if not installation_id:
            return _error_response(
                code="INVALID_REQUEST",
                message="installation_id is required",
                status=400
            )

        # Delegate to service layer
        # Service handles: PAT retrieval, Figma API validation
        service = FigmaService()
        validation_result = service.validate_frame(
            frame_url=frame_url,
            installation_id=installation_id
        )

        logger.info(f"Frame validation result: valid={validation_result.get('valid')}")

        return _success_response(validation_result, status=200)

    except Exception as e:
        logger.error(f"Error validating frame: {e}", exc_info=True)
        return _error_response(
            code="FRAME_VALIDATION_FAILED",
            message="Failed to validate frame",
            status=500
        )


@figma_blueprint.route('/attachments', methods=['POST'])
@require_feature_flag
@require_authentication
def create_attachments() -> Tuple[Dict[str, Any], int]:
    """
    Attach Figma frames to project.

    This endpoint implements frame attachment (A.7.1.2), creating attachment records
    for each frame URL after validating access. The operation is additive and
    idempotent - same URL overwrites previous attachment.

    Request Body:
        {
            "project_id": integer (required),
            "installation_id": integer (required),
            "frames": [
                {
                    "url": "string (required)",
                    "description": "string (optional)"
                },
                ...
            ],
            "tech_spec_id": integer (optional)
        }

    Response (201 Created):
        [
            {
                "success": boolean,
                "attachment_id": integer (if success=true),
                "frame_url": "string",
                "frame_title": "string" (if success=true),
                "description": "string",
                "message": "string" (if success=false)
            },
            ...
        ]

    Error Responses:
        400 Bad Request: Missing required fields or validation failure
        401 Unauthorized: User not authenticated
        403 Forbidden: User lacks project access
        404 Not Found: Installation does not exist

    :return: Tuple of (response dict, status code)
    :rtype: Tuple[Dict[str, Any], int]
    """
    logger.info(f"POST /attachments - User: {_get_request_user().get('user_id')}")

    try:
        # Extract and validate request data
        data = request.get_json()

        if not data:
            return _error_response(
                code="INVALID_REQUEST",
                message="Request body is required",
                status=400
            )

        project_id = data.get('project_id')
        installation_id = data.get('installation_id')
        frames = data.get('frames', [])
        tech_spec_id = data.get('tech_spec_id')

        if not project_id:
            return _error_response(
                code="INVALID_REQUEST",
                message="project_id is required",
                status=400
            )

        if not installation_id:
            return _error_response(
                code="INVALID_REQUEST",
                message="installation_id is required",
                status=400
            )

        if not frames or not isinstance(frames, list):
            return _error_response(
                code="INVALID_REQUEST",
                message="frames must be a non-empty array",
                status=400
            )

        # Delegate to service layer
        # Service handles: Frame validation, attachment creation
        service = FigmaService()
        results = service.attach_frames(
            project_id=project_id,
            installation_id=installation_id,
            frames=frames,
            created_by=_get_request_user()['user_id'],
            tech_spec_id=tech_spec_id
        )

        logger.info(
            f"Attached {len([r for r in results if r['success']])} frames "
            f"to project {project_id}"
        )

        return _success_response(results, status=201)

    except ValueError as e:
        logger.error(f"Validation error attaching frames: {e}")
        return _error_response(
            code="INVALID_REQUEST",
            message=str(e),
            status=400
        )
    except Exception as e:
        logger.error(f"Error attaching frames: {e}", exc_info=True)
        return _error_response(
            code="INTERNAL_ERROR",
            message="Failed to attach frames",
            status=500
        )


@figma_blueprint.route('/attachments', methods=['GET'])
@require_feature_flag
@require_authentication
def list_attachments() -> Tuple[Dict[str, Any], int]:
    """
    List Figma attachments filtered by project and optionally tech spec.

    Query Parameters:
        project_id: Integer (required) - Project ID to filter by
        tech_spec_id: Integer (optional) - Tech spec ID to filter by

    Response (200 OK):
        [
            {
                "id": integer,
                "project_id": integer,
                "tech_spec_id": integer or null,
                "installation_id": integer,
                "frame_url": "string",
                "frame_title": "string",
                "description": "string or null",
                "created_by": integer,
                "created_at": "ISO 8601 timestamp",
                "updated_at": "ISO 8601 timestamp"
            },
            ...
        ]

    Error Responses:
        400 Bad Request: Missing project_id parameter
        401 Unauthorized: User not authenticated
        403 Forbidden: User lacks project access

    :return: Tuple of (response dict, status code)
    :rtype: Tuple[Dict[str, Any], int]
    """
    logger.info(f"GET /attachments - User: {_get_request_user().get('user_id')}")

    try:
        # Extract and validate query parameters
        project_id = request.args.get('project_id', type=int)
        tech_spec_id = request.args.get('tech_spec_id', type=int)

        if not project_id:
            return _error_response(
                code="INVALID_REQUEST",
                message="project_id query parameter is required",
                status=400
            )

        # Delegate to service layer
        service = FigmaService()
        attachments = service.list_attachments(
            project_id=project_id,
            tech_spec_id=tech_spec_id
        )

        logger.info(f"Retrieved {len(attachments)} attachments for project {project_id}")

        return _success_response(attachments, status=200)

    except ValueError as e:
        logger.error(f"Validation error listing attachments: {e}")
        return _error_response(
            code="INVALID_REQUEST",
            message=str(e),
            status=400
        )
    except Exception as e:
        logger.error(f"Error listing attachments: {e}", exc_info=True)
        return _error_response(
            code="INTERNAL_ERROR",
            message="Failed to list attachments",
            status=500
        )


@figma_blueprint.route('/attachments/<int:attachment_id>', methods=['GET'])
@require_feature_flag
@require_authentication
def get_attachment(attachment_id: int) -> Tuple[Dict[str, Any], int]:
    """
    Retrieve single Figma attachment by ID.

    Path Parameters:
        attachment_id: Integer ID of attachment to retrieve

    Response (200 OK):
        {
            "id": integer,
            "project_id": integer,
            "tech_spec_id": integer or null,
            "installation_id": integer,
            "frame_url": "string",
            "frame_title": "string",
            "description": "string or null",
            "created_by": integer,
            "created_at": "ISO 8601 timestamp",
            "updated_at": "ISO 8601 timestamp"
        }

    Error Responses:
        401 Unauthorized: User not authenticated
        403 Forbidden: User lacks project access
        404 Not Found: Attachment does not exist

    :param attachment_id: ID of attachment to retrieve
    :type attachment_id: int
    :return: Tuple of (response dict, status code)
    :rtype: Tuple[Dict[str, Any], int]
    """
    logger.info(
        f"GET /attachments/{attachment_id} - User: {_get_request_user().get('user_id')}"
    )

    try:
        # Delegate to service layer
        service = FigmaService()
        attachment = service.get_attachment(attachment_id)

        if not attachment:
            logger.info(f"Attachment {attachment_id} not found")
            return _error_response(
                code="INSTALLATION_NOT_FOUND",
                message=f"Attachment {attachment_id} not found",
                status=404
            )

        logger.info(f"Retrieved attachment {attachment_id}")

        return _success_response(attachment, status=200)

    except ValueError as e:
        logger.error(f"Validation error retrieving attachment: {e}")
        return _error_response(
            code="INVALID_REQUEST",
            message=str(e),
            status=400
        )
    except Exception as e:
        logger.error(f"Error retrieving attachment {attachment_id}: {e}", exc_info=True)
        return _error_response(
            code="INTERNAL_ERROR",
            message="Failed to retrieve attachment",
            status=500
        )


@figma_blueprint.route('/attachments/<int:attachment_id>', methods=['DELETE'])
@require_feature_flag
@require_authentication
def delete_attachment(attachment_id: int) -> Union[Tuple[Dict[str, Any], int], Response]:
    """
    Soft delete Figma attachment.

    Path Parameters:
        attachment_id: Integer ID of attachment to delete

    Response (204 No Content):
        Empty response body

    Error Responses:
        401 Unauthorized: User not authenticated
        403 Forbidden: User lacks permission to delete
        404 Not Found: Attachment does not exist

    :param attachment_id: ID of attachment to delete
    :type attachment_id: int
    :return: Tuple of (response dict, status code) or Response object
    :rtype: Union[Tuple[Dict[str, Any], int], Response]
    """
    logger.info(
        f"DELETE /attachments/{attachment_id} - User: {_get_request_user().get('user_id')}"
    )

    try:
        # Delegate to service layer
        service = FigmaService()
        deleted = service.delete_attachment(attachment_id)

        if deleted:
            logger.info(f"Successfully deleted attachment {attachment_id}")
            return make_response('', 204)
        else:
            return _error_response(
                code="INSTALLATION_NOT_FOUND",
                message=f"Attachment {attachment_id} not found",
                status=404
            )

    except ValueError as e:
        logger.error(f"Validation error deleting attachment: {e}")
        return _error_response(
            code="INVALID_REQUEST",
            message=str(e),
            status=400
        )
    except Exception as e:
        logger.error(f"Error deleting attachment {attachment_id}: {e}", exc_info=True)
        return _error_response(
            code="INTERNAL_ERROR",
            message="Failed to delete attachment",
            status=500
        )


# =============================================================================
# Internal Endpoint - PAT Retrieval for Internal Services
# =============================================================================

@figma_blueprint.route('/internal/installations/by-project/<int:project_id>', methods=['GET'])
def get_installation_by_project_internal(project_id: int) -> Tuple[Dict[str, Any], int]:
    """
    INTERNAL ONLY: Retrieve installation with actual PAT for project.

    This endpoint implements the internal API feature (A.9) for platform-event-listener
    and other internal services that need direct access to the PAT value for Figma API
    operations. This endpoint must NOT be exposed through archie-service-backend.

    SECURITY WARNING:
        This endpoint returns the actual PAT value and should ONLY be accessible from
        internal services within the same private network. Never expose this endpoint
        through the public-facing backend service.

    Path Parameters:
        project_id: Integer ID of project

    Response (200 OK):
        {
            "id": integer,
            "user_id": integer,
            "team_id": integer or null,
            "name": "string",
            "description": "string or null",
            "status": "active",
            "pat": "string",  <-- ACTUAL PAT VALUE INCLUDED
            "created_at": "ISO 8601 timestamp",
            "updated_at": "ISO 8601 timestamp"
        }

    Error Responses:
        404 Not Found: No installation found for project

    Note: This endpoint does NOT check FIGMA_INTEGRATION_ENABLED feature flag
          because it's for internal service-to-service communication.

    :param project_id: ID of project to get installation for
    :type project_id: int
    :return: Tuple of (response dict, status code)
    :rtype: Tuple[Dict[str, Any], int]
    """
    logger.info(f"INTERNAL GET /internal/installations/by-project/{project_id}")

    try:
        # Delegate to service layer
        # Service handles: Query attachments, retrieve installation, get PAT
        service = FigmaService()
        installation = service.get_installation_by_project(project_id)

        if not installation:
            logger.info(f"No installation found for project {project_id}")
            return _error_response(
                code="INSTALLATION_NOT_FOUND",
                message=f"No Figma installation found for project {project_id}",
                status=404
            )

        logger.info(
            f"Retrieved installation {installation['id']} with PAT for project {project_id}"
        )

        # Return installation WITH PAT for internal use
        return _success_response(installation, status=200)

    except ValueError as e:
        logger.error(f"Validation error retrieving installation by project: {e}")
        return _error_response(
            code="INVALID_REQUEST",
            message=str(e),
            status=400
        )
    except Exception as e:
        logger.error(
            f"Error retrieving installation for project {project_id}: {e}",
            exc_info=True
        )
        return _error_response(
            code="INTERNAL_ERROR",
            message="Failed to retrieve installation",
            status=500
        )
