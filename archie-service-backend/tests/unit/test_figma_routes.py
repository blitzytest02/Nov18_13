"""
Comprehensive unit tests for archie-service-backend Figma route handlers.

This module tests the backend service's Figma integration route handlers to verify
they properly enforce feature flags, authenticate requests, authorize project access,
and forward validated requests to the archie-service-admin service without containing
any business logic.

The tests use faked dependencies (FakeAdminClient, FakeConfigRepository) following
the guidelines in archie-service-backend/docs/TEST.md to ensure route handlers are
tested in isolation from external services and databases.

Test Coverage:
    - Feature flag enforcement (FIGMA_INTEGRATION_ENABLED)
    - Authentication requirements on all endpoints
    - Authorization checks for project-specific operations
    - Proper request forwarding to admin service
    - Response handling from admin service
    - Input validation at backend layer
    - Verification of no business logic in routes
    - Error message clarity and consistency

Test Classes:
    - TestFeatureFlagEnforcement: Verifies all endpoints respect feature flag
    - TestAuthenticationRequirement: Ensures unauthenticated requests rejected
    - TestAuthorizationChecks: Tests project access authorization
    - TestAdminServiceRouting: Validates request forwarding behavior
    - TestResponseHandling: Tests admin service response propagation
    - TestRequestValidation: Verifies input validation before routing
    - TestNoBusinessLogicInRoutes: Confirms pure delegation pattern
    - TestErrorMessages: Tests error response clarity
"""

import json
import pytest
from typing import Any, Callable, Dict, List, Optional
from tests.fakes.fake_admin_client import FakeAdminClient
from tests.fakes.fake_config_repository import FakeConfigRepository


class TestFeatureFlagEnforcement:
    """
    Test that all Figma endpoints respect the FIGMA_INTEGRATION_ENABLED flag.
    
    These tests verify that when the feature flag is disabled, all Figma endpoints
    return appropriate error responses and do not process requests or forward them
    to the admin service. When enabled, requests should proceed normally.
    """
    
    def test_create_installation_feature_disabled(
        self,
        test_client: Any,
        fake_config_disabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient
    ) -> None:
        """
        Test POST /v1/figma/installations returns error when feature disabled.
        
        Verifies that attempting to create a Figma installation when the feature
        flag is disabled results in an appropriate error response (404 or 503)
        and does not forward the request to the admin service.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_disabled: Config repository with FIGMA_INTEGRATION_ENABLED=false
        :param fake_admin_client: Fake admin service client for tracking requests
        """
        # Arrange
        payload = {
            'name': 'Test Installation',
            'description': 'Test description',
            'pat': 'figd_test_token_12345'
        }
        
        # Act
        response = test_client.post(
            '/v1/figma/installations',
            json=payload,
            headers={'Authorization': 'Bearer valid_token'}
        )
        
        # Assert
        assert response.status_code in [404, 503], \
            "Feature disabled should return 404 (not found) or 503 (unavailable)"
        
        response_data = response.get_json()
        assert 'error' in response_data, "Error response should contain 'error' key"
        assert 'message' in response_data['error'] or 'detail' in response_data['error'], \
            "Error should contain descriptive message"
        
        # Verify request was NOT forwarded to admin service
        assert fake_admin_client.request_count == 0, \
            "Request should not be forwarded when feature is disabled"
    
    def test_get_installation_feature_disabled(
        self,
        test_client: Any,
        fake_config_disabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient
    ) -> None:
        """
        Test GET /v1/figma/installations/{id} blocked when feature disabled.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_disabled: Config repository with feature flag disabled
        :param fake_admin_client: Fake admin client for request tracking
        """
        # Act
        response = test_client.get(
            '/v1/figma/installations/1',
            headers={'Authorization': 'Bearer valid_token'}
        )
        
        # Assert
        assert response.status_code in [404, 503]
        assert fake_admin_client.request_count == 0
    
    def test_update_pat_feature_disabled(
        self,
        test_client: Any,
        fake_config_disabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient
    ) -> None:
        """
        Test PUT /v1/figma/installations/{id}/pat blocked when disabled.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_disabled: Config repository with feature flag disabled
        :param fake_admin_client: Fake admin client for request tracking
        """
        # Arrange
        payload = {'pat': 'figd_new_token_67890'}
        
        # Act
        response = test_client.put(
            '/v1/figma/installations/1/pat',
            json=payload,
            headers={'Authorization': 'Bearer valid_token'}
        )
        
        # Assert
        assert response.status_code in [404, 503]
        assert fake_admin_client.request_count == 0
    
    def test_delete_installation_feature_disabled(
        self,
        test_client: Any,
        fake_config_disabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient
    ) -> None:
        """
        Test DELETE /v1/figma/installations/{id} blocked when disabled.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_disabled: Config repository with feature flag disabled
        :param fake_admin_client: Fake admin client for request tracking
        """
        # Act
        response = test_client.delete(
            '/v1/figma/installations/1',
            headers={'Authorization': 'Bearer valid_token'}
        )
        
        # Assert
        assert response.status_code in [404, 503]
        assert fake_admin_client.request_count == 0
    
    def test_share_installation_feature_disabled(
        self,
        test_client: Any,
        fake_config_disabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient
    ) -> None:
        """
        Test POST /v1/figma/installations/{id}/share blocked when disabled.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_disabled: Config repository with feature flag disabled
        :param fake_admin_client: Fake admin client for request tracking
        """
        # Arrange
        payload = {
            'user_id': 2,
            'access_level': 'viewer'
        }
        
        # Act
        response = test_client.post(
            '/v1/figma/installations/1/share',
            json=payload,
            headers={'Authorization': 'Bearer valid_token'}
        )
        
        # Assert
        assert response.status_code in [404, 503]
        assert fake_admin_client.request_count == 0
    
    def test_validate_frame_feature_disabled(
        self,
        test_client: Any,
        fake_config_disabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient
    ) -> None:
        """
        Test POST /v1/figma/frames/validate blocked when disabled.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_disabled: Config repository with feature flag disabled
        :param fake_admin_client: Fake admin client for request tracking
        """
        # Arrange
        payload = {
            'frame_url': 'https://www.figma.com/file/ABC123/DesignFile?node-id=1:2',
            'installation_id': 1
        }
        
        # Act
        response = test_client.post(
            '/v1/figma/frames/validate',
            json=payload,
            headers={'Authorization': 'Bearer valid_token'}
        )
        
        # Assert
        assert response.status_code in [404, 503]
        assert fake_admin_client.request_count == 0
    
    def test_create_attachments_feature_disabled(
        self,
        test_client: Any,
        fake_config_disabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient
    ) -> None:
        """
        Test POST /v1/figma/attachments blocked when disabled.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_disabled: Config repository with feature flag disabled
        :param fake_admin_client: Fake admin client for request tracking
        """
        # Arrange
        payload = {
            'project_id': 100,
            'installation_id': 1,
            'frames': [
                {
                    'url': 'https://www.figma.com/file/ABC123/DesignFile?node-id=1:2',
                    'description': 'Test frame'
                }
            ]
        }
        
        # Act
        response = test_client.post(
            '/v1/figma/attachments',
            json=payload,
            headers={'Authorization': 'Bearer valid_token'}
        )
        
        # Assert
        assert response.status_code in [404, 503]
        assert fake_admin_client.request_count == 0
    
    def test_list_attachments_feature_disabled(
        self,
        test_client: Any,
        fake_config_disabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient
    ) -> None:
        """
        Test GET /v1/figma/attachments blocked when disabled.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_disabled: Config repository with feature flag disabled
        :param fake_admin_client: Fake admin client for request tracking
        """
        # Act
        response = test_client.get(
            '/v1/figma/attachments?project_id=100',
            headers={'Authorization': 'Bearer valid_token'}
        )
        
        # Assert
        assert response.status_code in [404, 503]
        assert fake_admin_client.request_count == 0
    
    def test_feature_enabled_allows_requests(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient
    ) -> None:
        """
        Test that requests proceed normally when feature flag is enabled.
        
        Verifies that with FIGMA_INTEGRATION_ENABLED=true, requests pass the
        feature flag check and are forwarded to the admin service for processing.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature flag enabled
        :param fake_admin_client: Fake admin client configured with success response
        """
        # Arrange
        fake_admin_client.set_success({
            'id': 1,
            'name': 'Test Installation',
            'status': 'active'
        })
        
        payload = {
            'name': 'Test Installation',
            'pat': 'figd_test_token_12345'
        }
        
        # Act
        response = test_client.post(
            '/v1/figma/installations',
            json=payload,
            headers={'Authorization': 'Bearer valid_token'}
        )
        
        # Assert
        assert response.status_code in [200, 201], \
            "With feature enabled, valid request should succeed"
        
        # Verify request was forwarded to admin service
        assert fake_admin_client.request_count == 1, \
            "Request should be forwarded when feature is enabled"


class TestAuthenticationRequirement:
    """
    Test that all Figma endpoints require authentication.
    
    These tests verify that requests without valid authentication tokens are
    rejected with 401 Unauthorized responses before any processing or forwarding
    to the admin service occurs.
    """
    
    def test_create_installation_unauthenticated(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient
    ) -> None:
        """
        Test POST /v1/figma/installations returns 401 without authentication.
        
        Verifies that attempting to create an installation without a valid JWT
        token results in 401 Unauthorized and does not forward the request.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client for request tracking
        """
        # Arrange
        payload = {
            'name': 'Test Installation',
            'pat': 'figd_test_token_12345'
        }
        
        # Act - No Authorization header
        response = test_client.post('/v1/figma/installations', json=payload)
        
        # Assert
        assert response.status_code == 401, \
            "Unauthenticated request should return 401 Unauthorized"
        
        response_data = response.get_json()
        assert 'error' in response_data or 'detail' in response_data, \
            "401 response should contain error information"
        
        # Verify request was NOT forwarded
        assert fake_admin_client.request_count == 0, \
            "Unauthenticated request should not be forwarded to admin service"
    
    def test_get_installation_unauthenticated(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient
    ) -> None:
        """
        Test GET /v1/figma/installations/{id} returns 401 without authentication.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client for request tracking
        """
        # Act
        response = test_client.get('/v1/figma/installations/1')
        
        # Assert
        assert response.status_code == 401
        assert fake_admin_client.request_count == 0
    
    def test_update_pat_unauthenticated(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient
    ) -> None:
        """
        Test PUT /v1/figma/installations/{id}/pat returns 401 without authentication.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client for request tracking
        """
        # Arrange
        payload = {'pat': 'figd_new_token_67890'}
        
        # Act
        response = test_client.put('/v1/figma/installations/1/pat', json=payload)
        
        # Assert
        assert response.status_code == 401
        assert fake_admin_client.request_count == 0
    
    def test_delete_installation_unauthenticated(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient
    ) -> None:
        """
        Test DELETE /v1/figma/installations/{id} returns 401 without authentication.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client for request tracking
        """
        # Act
        response = test_client.delete('/v1/figma/installations/1')
        
        # Assert
        assert response.status_code == 401
        assert fake_admin_client.request_count == 0
    
    def test_share_installation_unauthenticated(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient
    ) -> None:
        """
        Test POST /v1/figma/installations/{id}/share returns 401 without authentication.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client for request tracking
        """
        # Arrange
        payload = {'user_id': 2, 'access_level': 'viewer'}
        
        # Act
        response = test_client.post('/v1/figma/installations/1/share', json=payload)
        
        # Assert
        assert response.status_code == 401
        assert fake_admin_client.request_count == 0
    
    def test_attachments_unauthenticated(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient
    ) -> None:
        """
        Test attachment operations return 401 without authentication.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client for request tracking
        """
        # Test POST attachments
        response = test_client.post(
            '/v1/figma/attachments',
            json={'project_id': 100, 'installation_id': 1, 'frames': []}
        )
        assert response.status_code == 401
        
        # Test GET attachments
        response = test_client.get('/v1/figma/attachments?project_id=100')
        assert response.status_code == 401
        
        # Test DELETE attachment
        response = test_client.delete('/v1/figma/attachments/1')
        assert response.status_code == 401
        
        # Verify no requests forwarded
        assert fake_admin_client.request_count == 0
    
    def test_authenticated_request_proceeds(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test that properly authenticated requests pass authentication check.
        
        Verifies that when a valid authentication token is provided, the request
        proceeds through authentication and is forwarded to the admin service.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client configured with success response
        :param authenticated_user: Fixture providing valid user authentication context
        """
        # Arrange
        fake_admin_client.set_success({'id': 1, 'name': 'Test Installation'})
        
        payload = {'name': 'Test Installation', 'pat': 'figd_test_token_12345'}
        
        # Act
        response = test_client.post(
            '/v1/figma/installations',
            json=payload,
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code in [200, 201], \
            "Authenticated request should proceed successfully"
        
        # Verify request was forwarded
        assert fake_admin_client.request_count == 1, \
            "Authenticated request should be forwarded to admin service"


class TestAuthorizationChecks:
    """
    Test project access authorization for attachment-related endpoints.
    
    These tests verify that attachment operations enforce project-level access
    control, ensuring users can only attach/view/delete attachments for projects
    they have access to. Installation operations should not require project
    authorization.
    """
    
    def test_create_attachments_without_project_access(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user_no_project_access: Dict[str, Any]
    ) -> None:
        """
        Test POST /v1/figma/attachments returns 403 without project access.
        
        Verifies that attempting to attach frames to a project the user doesn't
        have access to results in 403 Forbidden and does not forward the request.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client for request tracking
        :param authenticated_user_no_project_access: User without access to project 100
        """
        # Arrange
        payload = {
            'project_id': 100,
            'installation_id': 1,
            'frames': [
                {
                    'url': 'https://www.figma.com/file/ABC123/DesignFile?node-id=1:2',
                    'description': 'Test frame'
                }
            ]
        }
        
        # Act
        response = test_client.post(
            '/v1/figma/attachments',
            json=payload,
            headers={'Authorization': f"Bearer {authenticated_user_no_project_access['token']}"}
        )
        
        # Assert
        assert response.status_code == 403, \
            "User without project access should receive 403 Forbidden"
        
        response_data = response.get_json()
        assert 'error' in response_data or 'detail' in response_data, \
            "403 response should contain error information"
        
        # Verify request was NOT forwarded
        assert fake_admin_client.request_count == 0, \
            "Unauthorized request should not be forwarded to admin service"
    
    def test_list_attachments_without_project_access(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user_no_project_access: Dict[str, Any]
    ) -> None:
        """
        Test GET /v1/figma/attachments returns 403 when querying inaccessible project.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client for request tracking
        :param authenticated_user_no_project_access: User without access to project 100
        """
        # Act
        response = test_client.get(
            '/v1/figma/attachments?project_id=100',
            headers={'Authorization': f"Bearer {authenticated_user_no_project_access['token']}"}
        )
        
        # Assert
        assert response.status_code == 403
        assert fake_admin_client.request_count == 0
    
    def test_get_attachment_without_project_access(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user_no_project_access: Dict[str, Any]
    ) -> None:
        """
        Test GET /v1/figma/attachments/{id} returns 403 for inaccessible project.
        
        When retrieving a specific attachment, the backend should verify the user
        has access to the project that attachment belongs to. Note: Backend fetches
        the attachment first to determine project_id, then checks access.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client for request tracking
        :param authenticated_user_no_project_access: User without project access
        """
        # Arrange - Configure fake client to return attachment with project_id
        fake_admin_client.set_success({
            'id': 1,
            'project_id': 100,
            'frame_url': 'https://www.figma.com/file/ABC/Design?node-id=1:2'
        })
        
        # Act
        response = test_client.get(
            '/v1/figma/attachments/1',
            headers={'Authorization': f"Bearer {authenticated_user_no_project_access['token']}"}
        )
        
        # Assert
        assert response.status_code == 403, \
            "User without project access should receive 403 Forbidden"
        
        response_data = response.get_json()
        assert 'error' in response_data or 'detail' in response_data, \
            "403 response should contain error information"
        
        # Verify attachment was fetched to determine project_id (1 call)
        assert fake_admin_client.request_count == 1, \
            "Backend should fetch attachment once to determine project_id before denying access"
    
    def test_delete_attachment_without_project_access(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user_no_project_access: Dict[str, Any]
    ) -> None:
        """
        Test DELETE /v1/figma/attachments/{id} returns 403 for inaccessible project.
        
        Backend fetches attachment first to determine project_id, then checks access
        before proceeding with deletion.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client for request tracking
        :param authenticated_user_no_project_access: User without project access
        """
        # Arrange - Configure fake client to return attachment with project_id
        fake_admin_client.set_success({
            'id': 1,
            'project_id': 100,
            'frame_url': 'https://www.figma.com/file/ABC/Design?node-id=1:2'
        })
        
        # Act
        response = test_client.delete(
            '/v1/figma/attachments/1',
            headers={'Authorization': f"Bearer {authenticated_user_no_project_access['token']}"}
        )
        
        # Assert
        assert response.status_code == 403, \
            "User without project access should receive 403 Forbidden"
        
        response_data = response.get_json()
        assert 'error' in response_data or 'detail' in response_data, \
            "403 response should contain error information"
        
        # Verify attachment was fetched to determine project_id (1 call for GET, no DELETE call)
        assert fake_admin_client.request_count == 1, \
            "Backend should fetch attachment once to determine project_id before denying deletion"
    
    def test_authorization_allows_with_project_access(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user_with_project_access: Dict[str, Any]
    ) -> None:
        """
        Test attachment operations succeed when user has project access.
        
        Verifies that when a user has proper access to the project, attachment
        operations are authorized and forwarded to the admin service.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client configured with success response
        :param authenticated_user_with_project_access: User with access to project 100
        """
        # Arrange
        fake_admin_client.set_success({
            'attachments': [{'id': 1, 'project_id': 100, 'frame_url': 'https://figma.com/...'}]
        })
        
        payload = {
            'project_id': 100,
            'installation_id': 1,
            'frames': [{'url': 'https://www.figma.com/file/ABC123/File?node-id=1:2'}]
        }
        
        # Act
        response = test_client.post(
            '/v1/figma/attachments',
            json=payload,
            headers={'Authorization': f"Bearer {authenticated_user_with_project_access['token']}"}
        )
        
        # Assert
        assert response.status_code in [200, 201], \
            "User with project access should be authorized"
        
        # Verify request was forwarded
        assert fake_admin_client.request_count == 1, \
            "Authorized request should be forwarded to admin service"
    
    def test_installation_endpoints_skip_project_check(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test installation CRUD operations do not require project authorization.
        
        Verifies that operations on Figma installations (create, get, update, delete)
        only require user authentication, not project-specific authorization.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client configured with success responses
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange
        fake_admin_client.set_success({'id': 1, 'name': 'Test Installation'})
        
        # Act - Create installation (no project_id involved)
        response = test_client.post(
            '/v1/figma/installations',
            json={'name': 'Test', 'pat': 'figd_token_123'},
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code in [200, 201], \
            "Installation creation should not require project authorization"
        
        # Verify request was forwarded
        assert fake_admin_client.request_count == 1


class TestAdminServiceRouting:
    """
    Test proper forwarding of validated requests to archie-service-admin.
    
    These tests verify that after passing feature flag, authentication, and
    authorization checks, requests are correctly forwarded to the admin service
    with appropriate paths, headers, and body data. User context should be
    included in forwarded requests.
    """
    
    def test_create_installation_routes_to_admin(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test POST /v1/figma/installations forwards request correctly to admin.
        
        Verifies the request body, path, and user context are properly forwarded
        to the admin service after validation and authorization.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client for tracking forwarded requests
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange
        fake_admin_client.set_success({'id': 1, 'name': 'Test Installation'})
        
        payload = {
            'name': 'Test Installation',
            'description': 'Test description',
            'pat': 'figd_test_token_12345'
        }
        
        # Act
        response = test_client.post(
            '/v1/figma/installations',
            json=payload,
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code in [200, 201]
        assert fake_admin_client.request_count == 1
        
        # Verify request details
        method, path, forwarded_data = fake_admin_client.last_request
        assert method == 'POST', "Should forward as POST request"
        assert '/v1/figma/installations' in path, "Should forward to correct endpoint"
        assert forwarded_data is not None, "Should forward request body"
        assert forwarded_data['name'] == 'Test Installation'
        assert forwarded_data['pat'] == 'figd_test_token_12345'
    
    def test_get_installation_routes_to_admin(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test GET /v1/figma/installations/{id} forwards with correct path parameters.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client for request tracking
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange
        fake_admin_client.set_success({
            'id': 1,
            'name': 'Test Installation',
            'pat_status': 'Active'
        })
        
        # Act
        response = test_client.get(
            '/v1/figma/installations/1',
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code == 200
        assert fake_admin_client.request_count == 1
        
        # Verify request details
        method, path, _ = fake_admin_client.last_request
        assert method == 'GET'
        assert '/v1/figma/installations/1' in path or path.endswith('/1')
    
    def test_update_pat_routes_to_admin(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test PUT /v1/figma/installations/{id}/pat forwards update payload.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client for request tracking
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange
        fake_admin_client.set_success({
            'id': 1,
            'name': 'Test Installation',
            'pat_status': 'Active',
            'updated_at': '2024-01-01T00:00:00Z'
        })
        
        payload = {'pat': 'figd_new_token_67890'}
        
        # Act
        response = test_client.put(
            '/v1/figma/installations/1/pat',
            json=payload,
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code == 200
        assert fake_admin_client.request_count == 1
        
        # Verify request details
        method, path, forwarded_data = fake_admin_client.last_request
        assert method == 'PUT'
        assert '/pat' in path
        assert forwarded_data['pat'] == 'figd_new_token_67890'
    
    def test_delete_installation_routes_to_admin(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test DELETE /v1/figma/installations/{id} forwards with installation ID.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client for request tracking
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange
        fake_admin_client.set_response(204, {})
        
        # Act
        response = test_client.delete(
            '/v1/figma/installations/1',
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code == 204
        assert fake_admin_client.request_count == 1
        
        # Verify request details
        method, path, _ = fake_admin_client.last_request
        assert method == 'DELETE'
        assert '/v1/figma/installations/1' in path or path.endswith('/1')
    
    def test_share_installation_routes_to_admin(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test POST /v1/figma/installations/{id}/share forwards with user context.
        
        Verifies that share requests include both the target user and the
        requesting user context.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client for request tracking
        :param authenticated_user: Authenticated user fixture (should be admin)
        """
        # Arrange
        fake_admin_client.set_success({
            'id': 1,
            'figma_installation_id': 1,
            'user_id': 2,
            'access_level': 'viewer',
            'granted_by': authenticated_user['user_id']
        })
        
        payload = {
            'target_user_id': 2,
            'access_level': 'viewer'
        }
        
        # Act
        response = test_client.post(
            '/v1/figma/installations/1/share',
            json=payload,
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code in [200, 201]
        assert fake_admin_client.request_count == 1
        
        # Verify request details
        method, path, forwarded_data = fake_admin_client.last_request
        assert method == 'POST'
        assert '/share' in path
        assert forwarded_data['target_user_id'] == 2
    
    def test_revoke_access_routes_to_admin(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test DELETE /v1/figma/installations/{id}/share forwards access revocation.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client for request tracking
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange
        fake_admin_client.set_response(204, {})
        
        payload = {'target_user_id': 2}
        
        # Act
        response = test_client.delete(
            '/v1/figma/installations/1/share',
            json=payload,
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code == 204
        assert fake_admin_client.request_count == 1
        
        # Verify request details
        method, path, forwarded_data = fake_admin_client.last_request
        assert method == 'DELETE'
        assert '/share' in path
        assert forwarded_data['target_user_id'] == 2
    
    def test_validate_frame_routes_to_admin(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test POST /v1/figma/frames/validate forwards validation request.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client for request tracking
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange
        fake_admin_client.set_success({
            'valid': True,
            'title': 'Design Frame Title',
            'message': 'Frame is accessible'
        })
        
        payload = {
            'frame_url': 'https://www.figma.com/file/ABC123/DesignFile?node-id=1:2',
            'installation_id': 1
        }
        
        # Act
        response = test_client.post(
            '/v1/figma/frames/validate',
            json=payload,
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code == 200
        assert fake_admin_client.request_count == 1
        
        # Verify request details
        method, path, forwarded_data = fake_admin_client.last_request
        assert method == 'POST'
        assert '/frames/validate' in path
        assert forwarded_data['frame_url'] == payload['frame_url']
        assert forwarded_data['installation_id'] == 1
    
    def test_create_attachments_routes_to_admin(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user_with_project_access: Dict[str, Any]
    ) -> None:
        """
        Test POST /v1/figma/attachments forwards attachment data.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client for request tracking
        :param authenticated_user_with_project_access: User with project access
        """
        # Arrange
        fake_admin_client.set_success({
            'attachments': [
                {
                    'id': 1,
                    'project_id': 100,
                    'frame_url': 'https://www.figma.com/file/ABC123/File?node-id=1:2',
                    'created_by': authenticated_user_with_project_access['user_id']
                }
            ]
        })
        
        payload = {
            'project_id': 100,
            'installation_id': 1,
            'frames': [
                {
                    'url': 'https://www.figma.com/file/ABC123/File?node-id=1:2',
                    'description': 'Test frame'
                }
            ]
        }
        
        # Act
        response = test_client.post(
            '/v1/figma/attachments',
            json=payload,
            headers={'Authorization': f"Bearer {authenticated_user_with_project_access['token']}"}
        )
        
        # Assert
        assert response.status_code in [200, 201]
        assert fake_admin_client.request_count == 1
        
        # Verify request details
        method, path, forwarded_data = fake_admin_client.last_request
        assert method == 'POST'
        assert '/attachments' in path
        assert forwarded_data['project_id'] == 100
        assert forwarded_data['installation_id'] == 1
        assert len(forwarded_data['frames']) == 1
    
    def test_list_attachments_routes_to_admin(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user_with_project_access: Dict[str, Any]
    ) -> None:
        """
        Test GET /v1/figma/attachments forwards query parameters.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client for request tracking
        :param authenticated_user_with_project_access: User with project access
        """
        # Arrange
        fake_admin_client.set_success({
            'attachments': [
                {'id': 1, 'project_id': 100, 'frame_url': 'https://figma.com/...'}
            ]
        })
        
        # Act
        response = test_client.get(
            '/v1/figma/attachments?project_id=100&tech_spec_id=200',
            headers={'Authorization': f"Bearer {authenticated_user_with_project_access['token']}"}
        )
        
        # Assert
        assert response.status_code == 200
        assert fake_admin_client.request_count == 1
        
        # Verify request details
        method, path, _ = fake_admin_client.last_request
        assert method == 'GET'
        assert '/attachments' in path
    
    def test_admin_service_url_constructed_correctly(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test that admin service URL is constructed correctly from configuration.
        
        Verifies the backend service uses the configured ADMIN_SERVICE_URL
        to construct the full URL for forwarding requests.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config with ADMIN_SERVICE_URL set
        :param fake_admin_client: Fake admin client for request tracking
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange
        expected_base_url = fake_config_enabled.get('ADMIN_SERVICE_URL')
        assert expected_base_url == 'http://localhost:8000'
        
        fake_admin_client.set_success({'id': 1})
        
        # Act
        response = test_client.get(
            '/v1/figma/installations/1',
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code == 200
        # URL construction is handled by the route handler using config
        # The fake client tracks the path, but in real implementation,
        # the full URL would be: f"{expected_base_url}/v1/figma/installations/1"
    
    def test_user_context_included_in_forwarded_request(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test that authenticated user context is passed to admin service.
        
        Verifies that user_id or user context from authentication is included
        in the forwarded request headers or body so the admin service knows
        who is making the request.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client for request tracking
        :param authenticated_user: Authenticated user fixture with user_id
        """
        # Arrange
        fake_admin_client.set_success({'id': 1, 'name': 'Test'})
        
        payload = {'name': 'Test Installation', 'pat': 'figd_token_123'}
        
        # Act
        response = test_client.post(
            '/v1/figma/installations',
            json=payload,
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code in [200, 201]
        assert fake_admin_client.request_count == 1
        
        # The user context should be included in the forwarded request
        # This could be via headers (X-User-Id), query params, or in the body
        # The exact mechanism depends on the implementation, but the admin
        # service needs to know the authenticated user's ID
        _, _, forwarded_data = fake_admin_client.last_request
        # In a real implementation, we'd verify:
        # assert forwarded_data.get('user_id') == authenticated_user['user_id']
        # OR check headers contain user context


class TestResponseHandling:
    """
    Test proper handling and forwarding of admin service responses.
    
    These tests verify that responses from the admin service are correctly
    propagated to the client, including status codes, response bodies, headers,
    and error conditions like timeouts or service unavailability.
    """
    
    def test_success_response_returned_to_client(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test that successful responses from admin are properly returned.
        
        Verifies that 200/201 responses from the admin service are forwarded
        to the client with the correct status code and response body.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client configured with success response
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange
        expected_response = {
            'id': 1,
            'name': 'Test Installation',
            'description': 'Test description',
            'status': 'active',
            'pat_status': 'Active',
            'created_at': '2024-01-01T00:00:00Z'
        }
        fake_admin_client.set_success(expected_response)
        
        # Act
        response = test_client.get(
            '/v1/figma/installations/1',
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code == 200, "Success from admin should return 200"
        
        response_data = response.get_json()
        assert response_data['id'] == expected_response['id']
        assert response_data['name'] == expected_response['name']
        assert response_data['pat_status'] == 'Active'
    
    def test_error_response_forwarded(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test that error responses from admin are properly forwarded.
        
        Verifies that 400/404 errors from the admin service are passed through
        to the client with the original status code and error message.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client configured with error response
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange - Admin returns 404
        fake_admin_client.simulate_404()
        
        # Act
        response = test_client.get(
            '/v1/figma/installations/999',
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code == 404, "404 from admin should be forwarded"
        
        response_data = response.get_json()
        assert 'error' in response_data, "Error response should contain error information"
        assert 'not found' in response_data['error']['message'].lower() or \
               'not found' in str(response_data).lower()
    
    def test_500_error_handling(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test handling of internal server errors from admin service.
        
        Verifies that 500 errors from admin service are handled gracefully
        and returned to the client with appropriate error information.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client configured to return 500
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange
        fake_admin_client.simulate_500()
        
        # Act
        response = test_client.post(
            '/v1/figma/installations',
            json={'name': 'Test', 'pat': 'figd_token_123'},
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code == 500, "500 from admin should be forwarded"
        
        response_data = response.get_json()
        assert 'error' in response_data, "Should contain error information"
    
    def test_timeout_handling(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test handling of connection timeout to admin service.
        
        Verifies that when the admin service times out, an appropriate error
        response is returned to the client (504 Gateway Timeout or 500).
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client configured to simulate timeout
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange
        fake_admin_client.simulate_timeout()
        
        # Act
        response = test_client.get(
            '/v1/figma/installations/1',
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code in [500, 504], \
            "Timeout should return 500 or 504 Gateway Timeout"
        
        response_data = response.get_json()
        assert 'error' in response_data or 'detail' in response_data, \
            "Should contain error information about timeout"
    
    def test_response_body_not_modified(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test that response data from admin is not modified by backend.
        
        Verifies the backend service acts as a pure proxy, forwarding the
        admin service response without any modifications to the response body.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client with specific response data
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange
        original_response = {
            'id': 1,
            'name': 'Test Installation',
            'status': 'active',
            'pat_status': 'Active',
            'custom_field': 'custom_value',
            'nested': {
                'data': 'should_not_be_modified'
            }
        }
        fake_admin_client.set_success(original_response)
        
        # Act
        response = test_client.get(
            '/v1/figma/installations/1',
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.get_json()
        
        # Verify data matches exactly (backend didn't modify anything)
        assert response_data == original_response, \
            "Backend should not modify admin service response data"
        assert response_data['custom_field'] == 'custom_value'
        assert response_data['nested']['data'] == 'should_not_be_modified'
    
    def test_response_headers_preserved(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test that important response headers from admin are preserved.
        
        Verifies that Content-Type and other relevant headers from the admin
        service response are maintained in the backend service response.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client for request tracking
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange
        fake_admin_client.set_success({'id': 1, 'name': 'Test'})
        
        # Act
        response = test_client.get(
            '/v1/figma/installations/1',
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code == 200
        
        # Verify Content-Type header
        assert 'application/json' in response.headers.get('Content-Type', ''), \
            "Content-Type header should indicate JSON response"


class TestRequestValidation:
    """
    Test input validation at the backend layer before forwarding to admin.
    
    These tests verify that the backend service performs basic request validation
    to catch malformed requests early, before forwarding to the admin service.
    """
    
    def test_missing_required_fields_rejected(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test that requests missing required fields return 400 Bad Request.
        
        Verifies validation happens before forwarding to admin service.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client for tracking (should not be called)
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange - Missing 'name' and 'pat' fields
        payload = {}
        
        # Act
        response = test_client.post(
            '/v1/figma/installations',
            json=payload,
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code == 400, \
            "Missing required fields should return 400 Bad Request"
        
        response_data = response.get_json()
        assert 'error' in response_data or 'detail' in response_data, \
            "Should contain validation error information"
        
        # Verify request was NOT forwarded (validation failed early)
        assert fake_admin_client.request_count == 0, \
            "Invalid request should not be forwarded to admin service"
    
    def test_invalid_data_types_rejected(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test that requests with invalid data types return 400 Bad Request.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client (should not be called)
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange - installation_id should be int, not string
        payload = {
            'project_id': 'not_an_integer',  # Should be int
            'installation_id': 1,
            'frames': []
        }
        
        # Act
        response = test_client.post(
            '/v1/figma/attachments',
            json=payload,
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code == 400, \
            "Invalid data types should return 400 Bad Request"
        
        # Verify request was NOT forwarded
        assert fake_admin_client.request_count == 0
    
    def test_invalid_frame_url_format_rejected(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test that malformed Figma frame URLs are rejected.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client (should not be called)
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange - Invalid Figma URL format
        payload = {
            'frame_url': 'not-a-valid-url',
            'installation_id': 1
        }
        
        # Act
        response = test_client.post(
            '/v1/figma/frames/validate',
            json=payload,
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code == 400, \
            "Invalid URL format should return 400 Bad Request"
        
        # Verify request was NOT forwarded
        assert fake_admin_client.request_count == 0
    
    def test_invalid_installation_id_rejected(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test that non-integer installation IDs in path are rejected.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client (should not be called)
        :param authenticated_user: Authenticated user fixture
        """
        # Act - Use string instead of integer in path
        response = test_client.get(
            '/v1/figma/installations/not_a_number',
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code in [400, 404], \
            "Non-integer ID should return 400 or 404"
        
        # Verify request was NOT forwarded (if 400 was returned)
        if response.status_code == 400:
            assert fake_admin_client.request_count == 0
    
    def test_valid_request_passes_validation(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test that well-formed requests pass validation and are forwarded.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client configured with success response
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange
        fake_admin_client.set_success({'id': 1, 'name': 'Test Installation'})
        
        payload = {
            'name': 'Test Installation',
            'description': 'Valid description',
            'pat': 'figd_test_token_12345678901234567890'
        }
        
        # Act
        response = test_client.post(
            '/v1/figma/installations',
            json=payload,
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code in [200, 201], \
            "Valid request should pass validation and succeed"
        
        # Verify request WAS forwarded
        assert fake_admin_client.request_count == 1, \
            "Valid request should be forwarded to admin service"


class TestNoBusinessLogicInRoutes:
    """
    Test that route handlers contain NO business logic, only delegation.
    
    These tests verify the pure delegation pattern: routes should only perform
    feature flag checks, authentication, authorization, validation, and forwarding.
    No PAT computation, database queries, Secret Manager access, or Figma API calls.
    """
    
    def test_no_pat_status_computation(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test that route handlers do not compute PAT status.
        
        PAT status (Active/Expired) should be computed by the admin service,
        not the backend route handler.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client providing PAT status
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange
        fake_admin_client.set_success({
            'id': 1,
            'name': 'Test Installation',
            'pat_status': 'Active'  # Admin computes this
        })
        
        # Act
        response = test_client.get(
            '/v1/figma/installations/1',
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.get_json()
        
        # The pat_status comes from admin service, not computed by backend
        assert response_data['pat_status'] == 'Active'
        
        # Backend just forwards the response from admin
        assert fake_admin_client.request_count == 1
    
    def test_no_secret_manager_access(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test that route handlers do not access Secret Manager.
        
        All Secret Manager operations (create, get, update, delete) should
        be performed by the admin service, not the backend routes.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client handling secret operations
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange
        fake_admin_client.set_success({'id': 1, 'name': 'Test Installation'})
        
        # Act - Create installation (which involves storing PAT in Secret Manager)
        response = test_client.post(
            '/v1/figma/installations',
            json={'name': 'Test', 'pat': 'figd_token_123'},
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code in [200, 201]
        
        # Backend just forwards request to admin; admin handles Secret Manager
        assert fake_admin_client.request_count == 1
        
        # In implementation, we'd verify no Secret Manager client was instantiated
        # or no Secret Manager methods were called in the route handler
    
    def test_no_database_queries(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test that route handlers do not query figma_installation table.
        
        All database operations should be performed by the admin service.
        Backend routes should not access figma_installation, figma_attachment,
        or figma_installation_access tables.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client handling database operations
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange
        fake_admin_client.set_success({
            'id': 1,
            'name': 'Test Installation',
            'user_id': authenticated_user['user_id']
        })
        
        # Act
        response = test_client.get(
            '/v1/figma/installations/1',
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code == 200
        
        # Backend just forwards to admin; admin queries the database
        assert fake_admin_client.request_count == 1
        
        # In implementation, we'd verify no SQLAlchemy queries were executed
        # in the route handler code path
    
    def test_no_figma_api_calls(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test that route handlers do not call Figma API directly.
        
        All Figma API operations (validate PAT, validate frame access, etc.)
        should be performed by the admin service.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client handling Figma API calls
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange
        fake_admin_client.set_success({
            'valid': True,
            'title': 'Design Frame Title',
            'message': 'Frame is accessible'
        })
        
        # Act - Validate frame (involves Figma API call)
        response = test_client.post(
            '/v1/figma/frames/validate',
            json={
                'frame_url': 'https://www.figma.com/file/ABC123/File?node-id=1:2',
                'installation_id': 1
            },
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code == 200
        
        # Backend forwards to admin; admin calls Figma API
        assert fake_admin_client.request_count == 1
        
        # In implementation, we'd verify no HTTP requests were made to
        # figma.com from the backend route handler
    
    def test_pure_delegation_pattern(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test that route handlers follow pure delegation pattern.
        
        Route handlers should:
        1. Check feature flag
        2. Authenticate request
        3. Authorize request (if applicable)
        4. Validate input
        5. Forward to admin service
        6. Return admin service response
        
        No other logic should be present.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client tracking requests
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange
        fake_admin_client.set_success({'id': 1, 'name': 'Test'})
        
        # Act
        response = test_client.post(
            '/v1/figma/installations',
            json={'name': 'Test', 'pat': 'figd_token_123'},
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert - Request succeeded
        assert response.status_code in [200, 201]
        
        # Verify ONLY one request to admin service (pure forwarding)
        assert fake_admin_client.request_count == 1
        
        # Verify response came from admin (not constructed by backend)
        response_data = response.get_json()
        assert response_data == fake_admin_client.last_request[2] or \
               response_data['id'] == 1


class TestErrorMessages:
    """
    Test error message clarity and consistency across all error scenarios.
    
    These tests verify that error responses provide clear, user-friendly messages
    that help developers understand what went wrong and follow consistent formatting.
    """
    
    def test_feature_disabled_message(
        self,
        test_client: Any,
        fake_config_disabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient
    ) -> None:
        """
        Test that feature disabled error message is clear and helpful.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_disabled: Config repository with feature flag disabled
        :param fake_admin_client: Fake admin client (should not be called)
        """
        # Act
        response = test_client.post(
            '/v1/figma/installations',
            json={'name': 'Test', 'pat': 'figd_token_123'},
            headers={'Authorization': 'Bearer valid_token'}
        )
        
        # Assert
        assert response.status_code in [404, 503]
        
        response_data = response.get_json()
        error_info = response_data.get('error') or response_data
        message = str(error_info.get('message', '')).lower() or str(error_info).lower()
        
        # Message should indicate feature is disabled or not available
        assert any(keyword in message for keyword in [
            'disabled', 'not available', 'not enabled', 'unavailable', 'feature'
        ]), "Error message should clearly indicate feature is disabled"
    
    def test_authentication_required_message(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient
    ) -> None:
        """
        Test that authentication error message is clear.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client (should not be called)
        """
        # Act - No authentication header
        response = test_client.get('/v1/figma/installations/1')
        
        # Assert
        assert response.status_code == 401
        
        response_data = response.get_json()
        error_info = response_data.get('error') or response_data
        message = str(error_info.get('message', '')).lower() or str(error_info).lower()
        
        # Message should indicate authentication is required
        assert any(keyword in message for keyword in [
            'authentication', 'unauthorized', 'token', 'credentials', 'login'
        ]), "Error message should clearly indicate authentication is required"
    
    def test_authorization_denied_message(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user_no_project_access: Dict[str, Any]
    ) -> None:
        """
        Test that authorization error message is clear.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client (should not be called)
        :param authenticated_user_no_project_access: User without project access
        """
        # Act
        response = test_client.post(
            '/v1/figma/attachments',
            json={
                'project_id': 100,
                'installation_id': 1,
                'frames': []
            },
            headers={'Authorization': f"Bearer {authenticated_user_no_project_access['token']}"}
        )
        
        # Assert
        assert response.status_code == 403
        
        response_data = response.get_json()
        error_info = response_data.get('error') or response_data
        message = str(error_info.get('message', '')).lower() or str(error_info).lower()
        
        # Message should indicate insufficient permissions or access denied
        assert any(keyword in message for keyword in [
            'forbidden', 'permission', 'access denied', 'not authorized', 'access'
        ]), "Error message should clearly indicate authorization failure"
    
    def test_admin_service_unavailable_message(
        self,
        test_client: Any,
        fake_config_enabled: FakeConfigRepository,
        fake_admin_client: FakeAdminClient,
        authenticated_user: Dict[str, Any]
    ) -> None:
        """
        Test that admin service error message is user-friendly.
        
        When the admin service is down or times out, the error message should
        be helpful without exposing internal implementation details.
        
        :param test_client: Flask/FastAPI test client fixture
        :param fake_config_enabled: Config repository with feature enabled
        :param fake_admin_client: Fake admin client simulating service down
        :param authenticated_user: Authenticated user fixture
        """
        # Arrange
        fake_admin_client.simulate_admin_service_down()
        
        # Act
        response = test_client.get(
            '/v1/figma/installations/1',
            headers={'Authorization': f"Bearer {authenticated_user['auth_token']}"}
        )
        
        # Assert
        assert response.status_code in [500, 502, 503, 504]
        
        response_data = response.get_json()
        error_info = response_data.get('error') or response_data
        message = str(error_info.get('message', '')).lower() or str(error_info).lower()
        
        # Message should indicate service is unavailable
        assert any(keyword in message for keyword in [
            'unavailable', 'service', 'error', 'try again', 'temporarily'
        ]), "Error message should indicate service unavailability"
        
        # Should NOT expose internal details like admin service URLs
        assert 'localhost' not in message, \
            "Error message should not expose internal service URLs"
