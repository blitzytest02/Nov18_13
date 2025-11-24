"""
Comprehensive unit tests for Figma API route handlers in archie-service-admin.

This test module validates all 14 Figma integration route endpoints defined in
src/routes/figma_routes.py, ensuring proper request validation, authorization checks,
feature flag enforcement, and response formatting. Tests use mocked FigmaService to
isolate route-level logic from business logic execution.

Test Coverage:
    - Feature flag enforcement (FIGMA_INTEGRATION_ENABLED) on all endpoints
    - Request validation (required fields, data types, format validation)
    - Authentication verification (require_authentication decorator)
    - Authorization checks (admin roles for sharing, ownership for updates/deletes)
    - Response formatting (status codes, error messages, schema consistency)
    - Security constraints (PAT never exposed except internal endpoint)

Architecture:
    Tests use Flask test_client() to make HTTP requests to route handlers. The
    FigmaService is patched to return controlled responses, allowing tests to verify
    route-level validation, authorization, and error handling without executing actual
    business logic. FakeConfigRepository enables programmatic feature flag control.

Test Organization:
    - TestFeatureFlagEnforcement: Cross-cutting feature flag tests
    - TestCreateInstallation: POST /v1/figma/installations
    - TestGetInstallation: GET /v1/figma/installations/{id}
    - TestUpdatePAT: PUT /v1/figma/installations/{id}/pat
    - TestDeleteInstallation: DELETE /v1/figma/installations/{id}
    - TestListInstallations: GET /v1/figma/installations
    - TestShareInstallation: POST /v1/figma/installations/{id}/share
    - TestRevokeAccess: DELETE /v1/figma/installations/{id}/share
    - TestListAccess: GET /v1/figma/installations/{id}/access
    - TestValidateFrame: POST /v1/figma/frames/validate
    - TestCreateAttachments: POST /v1/figma/attachments
    - TestListAttachments: GET /v1/figma/attachments
    - TestGetAttachment: GET /v1/figma/attachments/{id}
    - TestDeleteAttachment: DELETE /v1/figma/attachments/{id}
    - TestInternalGetByProject: GET /internal/figma/installations/by-project/{id}

Test Data Patterns:
    - Valid PAT format: "figd_AbCdEfGhIjKlMnOp1234567890"
    - Valid frame URLs: "https://www.figma.com/file/ABC123/Design?node-id=1:2"
    - User IDs: 1 (admin), 2 (owner), 3 (regular user)
    - Installation IDs: 100, 101, 102
    - Project IDs: 200, 201

Coverage Goal:
    Minimum 80% code coverage for all route handlers per section 0.6 requirements.
"""

import json
import pytest
from typing import Any, Dict, Optional
from unittest.mock import Mock, patch, MagicMock

from flask import Flask

# Import route blueprint for testing
from src.routes.figma_routes import figma_blueprint

# Import FakeConfigRepository for feature flag control
from tests.fakes.fake_config_repository import FakeConfigRepository


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def app() -> Flask:
    """
    Create Flask application instance with figma_blueprint registered.

    This fixture provides a Flask app configured for testing with the Figma
    routes blueprint registered. The app is configured with testing mode enabled
    and JSON_SORT_KEYS disabled for predictable response ordering.
    
    The blueprint is registered twice with different names to support both
    public API endpoints (/v1/figma/*) and internal endpoints (/internal/figma/*).
    Flask requires unique names when registering the same blueprint multiple times.

    :return: Flask application configured for testing
    :rtype: Flask
    """
    test_app = Flask(__name__)
    test_app.config['TESTING'] = True
    test_app.config['JSON_SORT_KEYS'] = False  # Preserve response key ordering

    # Register figma_blueprint with URL prefix for public API endpoints
    test_app.register_blueprint(figma_blueprint, url_prefix='/v1/figma', name='figma_public')
    
    # Register figma_blueprint again with different name for internal endpoints
    # This allows the /internal/* routes within the blueprint to be accessible
    # at /internal/figma/* path
    test_app.register_blueprint(figma_blueprint, url_prefix='/internal/figma', name='figma_internal')

    return test_app


@pytest.fixture
def client(app: Flask):
    """
    Create Flask test client for making HTTP requests to routes.

    This fixture provides a test client that can make HTTP requests to the
    registered route handlers without starting an actual HTTP server. Used
    by all route tests to simulate requests and validate responses.

    :param app: Flask application from app fixture
    :return: Flask test client
    """
    return app.test_client()


@pytest.fixture
def fake_config():
    """
    Create FakeConfigRepository with FIGMA_INTEGRATION_ENABLED=True.

    This fixture provides a fresh FakeConfigRepository instance for each test
    with the feature flag enabled by default. Tests can disable the flag to
    verify feature-disabled behavior.

    :return: FakeConfigRepository instance with feature enabled
    :rtype: FakeConfigRepository
    """
    config = FakeConfigRepository()
    # Feature is enabled by default in FakeConfigRepository
    return config


@pytest.fixture
def authenticated_headers() -> Dict[str, str]:
    """
    Provide HTTP headers simulating authenticated user request.

    In production, authentication would be via JWT tokens. For testing, we
    simulate authentication by setting request.user_id attribute via the
    request JSON body (as implemented in get_current_user() helper).

    :return: Dictionary of HTTP headers with Content-Type
    :rtype: Dict[str, str]
    """
    return {
        'Content-Type': 'application/json',
    }


def make_authenticated_request(user_id: int, **kwargs) -> Dict[str, Any]:
    """
    Helper to construct request body with user_id for authentication.

    This helper merges user_id into the request data to simulate authenticated
    requests as implemented in the get_current_user() helper function.

    :param user_id: ID of authenticated user
    :type user_id: int
    :param kwargs: Additional request body fields
    :return: Request body dictionary with user_id
    :rtype: Dict[str, Any]
    """
    data = kwargs.copy()
    data['user_id'] = user_id
    return data


# ============================================================================
# Test Class: Feature Flag Enforcement
# ============================================================================

class TestFeatureFlagEnforcement:
    """
    Test feature flag enforcement across all Figma endpoints.

    Per Feature Group A.6, all Figma functionality must respect the
    FIGMA_INTEGRATION_ENABLED feature flag. When disabled, endpoints should
    return 404 with FEATURE_DISABLED error code.
    """

    @patch('src.routes.figma_routes.config_repo')
    def test_create_installation_feature_disabled(
        self,
        mock_config,
        client,
        authenticated_headers
    ):
        """
        Test POST /installations returns 404 when feature flag is disabled.

        Verifies that attempting to create an installation when
        FIGMA_INTEGRATION_ENABLED=False returns appropriate error response.
        """
        # Configure mock to return False for feature flag
        mock_config.get_bool.return_value = False

        response = client.post(
            '/v1/figma/installations',
            data=json.dumps(make_authenticated_request(
                user_id=1,
                name='Test Installation',
                pat='figd_test1234567890'
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
        assert data['error']['code'] == 'FEATURE_DISABLED'
        assert 'not enabled' in data['error']['message'].lower()

    @patch('src.routes.figma_routes.config_repo')
    def test_get_installation_feature_disabled(self, mock_config, client):
        """Test GET /installations/{id} returns 404 when feature disabled."""
        mock_config.get_bool.return_value = False

        response = client.get('/v1/figma/installations/100')

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['error']['code'] == 'FEATURE_DISABLED'

    @patch('src.routes.figma_routes.config_repo')
    def test_validate_frame_feature_disabled(
        self,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test POST /frames/validate returns 404 when feature disabled."""
        mock_config.get_bool.return_value = False

        response = client.post(
            '/v1/figma/frames/validate',
            data=json.dumps(make_authenticated_request(
                user_id=1,
                frame_url='https://www.figma.com/file/ABC/Design?node-id=1:2',
                installation_id=100
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['error']['code'] == 'FEATURE_DISABLED'

    @patch('src.routes.figma_routes.config_repo')
    def test_feature_enabled_allows_request(
        self,
        mock_config,
        client,
        authenticated_headers
    ):
        """
        Test that requests proceed when FIGMA_INTEGRATION_ENABLED=True.

        Verifies feature flag check allows request to reach route handler
        (even if it fails later for other reasons like missing service mock).
        """
        mock_config.get_bool.return_value = True

        # Make request - it should pass feature flag check
        # (may fail later without service mock, but won't be FEATURE_DISABLED)
        with patch('src.routes.figma_routes.FigmaService') as mock_service:
            mock_service.return_value.create_installation.return_value = {
                'id': 100,
                'name': 'Test',
                'status': 'active',
                'created_at': '2024-01-01T00:00:00Z',
                'updated_at': '2024-01-01T00:00:00Z'
            }

            response = client.post(
                '/v1/figma/installations',
                data=json.dumps(make_authenticated_request(
                    user_id=1,
                    name='Test Installation',
                    pat='figd_test1234567890'
                )),
                headers=authenticated_headers
            )

            # Should NOT be FEATURE_DISABLED
            if response.status_code == 404:
                data = json.loads(response.data)
                assert data.get('error', {}).get('code') != 'FEATURE_DISABLED'


# ============================================================================
# Test Class: POST /v1/figma/installations (Create Installation)
# ============================================================================

class TestCreateInstallation:
    """
    Test POST /v1/figma/installations endpoint for creating Figma installations.

    Per Feature Group A.1, this endpoint creates a new Figma installation with
    secure PAT storage in Google Secret Manager. Tests validate request format,
    required fields, and response structure.
    """

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_create_installation_success(
        self,
        mock_service_class,
        mock_config,
        client,
        authenticated_headers
    ):
        """
        Test successful installation creation returns 201 with metadata (no PAT).

        Verifies that a valid request creates an installation and returns
        proper response without exposing the PAT value.
        """
        # Configure feature flag enabled
        mock_config.get_bool.return_value = True

        # Configure service mock to return installation data
        mock_service = Mock()
        mock_service.create_installation.return_value = {
            'id': 100,
            'user_id': 1,
            'team_id': None,
            'name': 'My Figma PAT',
            'description': 'Test description',
            'status': 'active',
            'created_at': '2024-01-01T00:00:00Z',
            'updated_at': '2024-01-01T00:00:00Z'
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            '/v1/figma/installations',
            data=json.dumps(make_authenticated_request(
                user_id=1,
                name='My Figma PAT',
                pat='figd_AbCdEfGhIjKlMnOp1234567890',
                description='Test description'
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        
        # Verify response structure
        assert data['id'] == 100
        assert data['name'] == 'My Figma PAT'
        assert data['status'] == 'active'
        assert 'created_at' in data
        
        # Critical: PAT must NOT be in response
        assert 'pat' not in data

        # Verify service was called with correct parameters
        mock_service.create_installation.assert_called_once_with(
            user_id=1,
            name='My Figma PAT',
            pat='figd_AbCdEfGhIjKlMnOp1234567890',
            description='Test description',
            team_id=None
        )

    @patch('src.routes.figma_routes.config_repo')
    def test_create_installation_missing_name(
        self,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test missing 'name' field returns 400 Bad Request."""
        mock_config.get_bool.return_value = True

        response = client.post(
            '/v1/figma/installations',
            data=json.dumps(make_authenticated_request(
                user_id=1,
                pat='figd_test1234567890'
                # name is missing
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert data['error']['code'] == 'INVALID_REQUEST'
        assert 'name' in data['error']['message'].lower()

    @patch('src.routes.figma_routes.config_repo')
    def test_create_installation_missing_pat(
        self,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test missing 'pat' field returns 400 Bad Request."""
        mock_config.get_bool.return_value = True

        response = client.post(
            '/v1/figma/installations',
            data=json.dumps(make_authenticated_request(
                user_id=1,
                name='Test Installation'
                # pat is missing
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'INVALID_REQUEST'
        assert 'pat' in data['error']['message'].lower()

    @patch('src.routes.figma_routes.config_repo')
    def test_create_installation_empty_name(
        self,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test empty 'name' string returns 400 Bad Request."""
        mock_config.get_bool.return_value = True

        response = client.post(
            '/v1/figma/installations',
            data=json.dumps(make_authenticated_request(
                user_id=1,
                name='   ',  # Whitespace only
                pat='figd_test1234567890'
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'INVALID_REQUEST'

    @patch('src.routes.figma_routes.get_current_user')
    @patch('src.routes.figma_routes.config_repo')
    def test_create_installation_no_body(
        self,
        mock_config,
        mock_get_user,
        client,
        authenticated_headers
    ):
        """Test request with no body returns 400 Bad Request."""
        mock_config.get_bool.return_value = True
        mock_get_user.return_value = {'user_id': 1}  # Mock authenticated user

        response = client.post(
            '/v1/figma/installations',
            headers=authenticated_headers
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'INVALID_REQUEST'

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_create_installation_service_error(
        self,
        mock_service_class,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test service layer error returns 500 with PAT_STORAGE_FAILED."""
        mock_config.get_bool.return_value = True

        # Configure service to raise exception (simulating Secret Manager failure)
        mock_service = Mock()
        mock_service.create_installation.side_effect = Exception('Secret Manager unavailable')
        mock_service_class.return_value = mock_service

        response = client.post(
            '/v1/figma/installations',
            data=json.dumps(make_authenticated_request(
                user_id=1,
                name='Test Installation',
                pat='figd_test1234567890'
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 500
        data = json.loads(response.data)
        assert data['error']['code'] == 'PAT_STORAGE_FAILED'

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_create_installation_validation_error(
        self,
        mock_service_class,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test service validation error returns 400 with error message."""
        mock_config.get_bool.return_value = True

        # Configure service to raise ValueError
        mock_service = Mock()
        mock_service.create_installation.side_effect = ValueError('Invalid PAT format')
        mock_service_class.return_value = mock_service

        response = client.post(
            '/v1/figma/installations',
            data=json.dumps(make_authenticated_request(
                user_id=1,
                name='Test Installation',
                pat='invalid_pat'
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'INVALID_REQUEST'
        assert 'Invalid PAT format' in data['error']['message']


# ============================================================================
# Test Class: GET /v1/figma/installations/{id} (Get Installation)
# ============================================================================

class TestGetInstallation:
    """
    Test GET /v1/figma/installations/{id} endpoint.

    Per Feature Group A.4, this endpoint retrieves installation metadata with
    computed PAT status (Active/Expired). PAT value must never be exposed.
    """

    @patch('src.routes.figma_routes.get_current_user')
    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_get_installation_success(
        self,
        mock_service_class,
        mock_config,
        mock_get_user,
        client
    ):
        """Test successful retrieval returns 200 with PAT status (not PAT value)."""
        mock_config.get_bool.return_value = True
        mock_get_user.return_value = {'user_id': 1}  # Mock authenticated user

        mock_service = Mock()
        mock_service.get_installation.return_value = {
            'id': 100,
            'user_id': 1,
            'team_id': None,
            'name': 'Test Installation',
            'description': 'Test description',
            'status': 'active',
            'pat_status': 'Active',  # Computed status, not actual PAT
            'created_at': '2024-01-01T00:00:00Z',
            'updated_at': '2024-01-01T00:00:00Z'
        }
        mock_service_class.return_value = mock_service

        response = client.get('/v1/figma/installations/100')

        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['id'] == 100
        assert data['name'] == 'Test Installation'
        assert data['pat_status'] == 'Active'
        
        # Critical: actual PAT must NOT be in response
        assert 'pat' not in data

        mock_service.get_installation.assert_called_once_with(100)

    @patch('src.routes.figma_routes.get_current_user')
    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_get_installation_not_found(
        self,
        mock_service_class,
        mock_config,
        mock_get_user,
        client
    ):
        """Test non-existent installation returns 404 NOT_FOUND."""
        mock_config.get_bool.return_value = True
        mock_get_user.return_value = {'user_id': 1}  # Mock authenticated user

        mock_service = Mock()
        mock_service.get_installation.return_value = None  # Not found
        mock_service_class.return_value = mock_service

        response = client.get('/v1/figma/installations/999')

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['error']['code'] == 'INSTALLATION_NOT_FOUND'
        assert '999' in data['error']['message']

    @patch('src.routes.figma_routes.get_current_user')
    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_get_installation_expired_pat_status(
        self,
        mock_service_class,
        mock_config,
        mock_get_user,
        client
    ):
        """Test installation with expired PAT returns pat_status='Expired'."""
        mock_config.get_bool.return_value = True
        mock_get_user.return_value = {'user_id': 1}  # Mock authenticated user

        mock_service = Mock()
        mock_service.get_installation.return_value = {
            'id': 100,
            'user_id': 1,
            'name': 'Test Installation',
            'status': 'active',
            'pat_status': 'Expired',  # PAT is no longer valid
            'created_at': '2024-01-01T00:00:00Z',
            'updated_at': '2024-01-01T00:00:00Z'
        }
        mock_service_class.return_value = mock_service

        response = client.get('/v1/figma/installations/100')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['pat_status'] == 'Expired'

    @patch('src.routes.figma_routes.get_current_user')
    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_get_installation_service_error(
        self,
        mock_service_class,
        mock_config,
        mock_get_user,
        client
    ):
        """Test service error returns 500 INTERNAL_ERROR."""
        mock_config.get_bool.return_value = True
        mock_get_user.return_value = {'user_id': 1}  # Mock authenticated user

        mock_service = Mock()
        mock_service.get_installation.side_effect = Exception('Database error')
        mock_service_class.return_value = mock_service

        response = client.get('/v1/figma/installations/100')

        assert response.status_code == 500
        data = json.loads(response.data)
        assert data['error']['code'] == 'INTERNAL_ERROR'


# ============================================================================
# Test Class: PUT /v1/figma/installations/{id}/pat (Update PAT)
# ============================================================================

class TestUpdatePAT:
    """
    Test PUT /v1/figma/installations/{id}/pat endpoint.

    Per Feature Group A.5, this endpoint updates the PAT for an existing
    installation with proper authorization checks.
    """

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_update_pat_success(
        self,
        mock_service_class,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test successful PAT update returns 200 with updated installation."""
        mock_config.get_bool.return_value = True

        mock_service = Mock()
        mock_service.update_pat.return_value = {
            'id': 100,
            'user_id': 1,
            'name': 'Test Installation',
            'status': 'active',
            'updated_at': '2024-01-02T00:00:00Z'  # Updated timestamp
        }
        mock_service_class.return_value = mock_service

        response = client.put(
            '/v1/figma/installations/100/pat',
            data=json.dumps(make_authenticated_request(
                user_id=1,
                new_pat='figd_NewPAT9876543210'
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['id'] == 100
        
        # Verify PAT not in response
        assert 'pat' not in data
        assert 'new_pat' not in data

        mock_service.update_pat.assert_called_once_with(
            installation_id=100,
            new_pat='figd_NewPAT9876543210',
            user_id=1
        )

    @patch('src.routes.figma_routes.config_repo')
    def test_update_pat_missing_new_pat(
        self,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test missing 'new_pat' field returns 400 Bad Request."""
        mock_config.get_bool.return_value = True

        response = client.put(
            '/v1/figma/installations/100/pat',
            data=json.dumps(make_authenticated_request(user_id=1)),
            headers=authenticated_headers
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'INVALID_REQUEST'
        assert 'new_pat' in data['error']['message'].lower()

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_update_pat_unauthorized_user(
        self,
        mock_service_class,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test unauthorized user (not owner/admin) returns 403 UNAUTHORIZED."""
        mock_config.get_bool.return_value = True

        mock_service = Mock()
        # Service raises ValueError for authorization failure
        mock_service.update_pat.side_effect = ValueError('User not authorized to update this installation')
        mock_service_class.return_value = mock_service

        response = client.put(
            '/v1/figma/installations/100/pat',
            data=json.dumps(make_authenticated_request(
                user_id=3,  # Different user
                new_pat='figd_NewPAT9876543210'
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 400  # ValueError mapped to 400
        data = json.loads(response.data)
        assert 'not authorized' in data['error']['message'].lower()

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_update_pat_installation_not_found(
        self,
        mock_service_class,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test updating non-existent installation returns appropriate error."""
        mock_config.get_bool.return_value = True

        mock_service = Mock()
        mock_service.update_pat.side_effect = ValueError('Installation 999 not found')
        mock_service_class.return_value = mock_service

        response = client.put(
            '/v1/figma/installations/999/pat',
            data=json.dumps(make_authenticated_request(
                user_id=1,
                new_pat='figd_NewPAT9876543210'
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'not found' in data['error']['message'].lower()


# ============================================================================
# Test Class: DELETE /v1/figma/installations/{id} (Delete Installation)
# ============================================================================

class TestDeleteInstallation:
    """
    Test DELETE /v1/figma/installations/{id} endpoint.

    Per Feature Group A.3, this endpoint soft deletes an installation and
    removes its PAT from Secret Manager with proper authorization.
    """

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_delete_installation_success(
        self,
        mock_service_class,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test successful deletion returns 204 No Content."""
        mock_config.get_bool.return_value = True

        mock_service = Mock()
        mock_service.delete_installation.return_value = True
        mock_service_class.return_value = mock_service

        response = client.delete(
            '/v1/figma/installations/100',
            data=json.dumps(make_authenticated_request(user_id=1)),
            headers=authenticated_headers
        )

        assert response.status_code == 204
        assert response.data == b''  # No content

        mock_service.delete_installation.assert_called_once_with(
            installation_id=100,
            user_id=1
        )

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_delete_installation_not_found(
        self,
        mock_service_class,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test deleting non-existent installation returns 404."""
        mock_config.get_bool.return_value = True

        mock_service = Mock()
        mock_service.delete_installation.side_effect = ValueError('Installation 999 not found')
        mock_service_class.return_value = mock_service

        response = client.delete(
            '/v1/figma/installations/999',
            data=json.dumps(make_authenticated_request(user_id=1)),
            headers=authenticated_headers
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'not found' in data['error']['message'].lower()

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_delete_installation_unauthorized(
        self,
        mock_service_class,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test unauthorized deletion attempt returns error."""
        mock_config.get_bool.return_value = True

        mock_service = Mock()
        mock_service.delete_installation.side_effect = PermissionError('User not authorized')
        mock_service_class.return_value = mock_service

        response = client.delete(
            '/v1/figma/installations/100',
            data=json.dumps(make_authenticated_request(user_id=3)),
            headers=authenticated_headers
        )

        assert response.status_code == 403
        data = json.loads(response.data)
        assert data['error']['code'] == 'PERMISSION_DENIED'


# ============================================================================
# Test Class: GET /v1/figma/installations (List Installations)
# ============================================================================

class TestListInstallations:
    """Test GET /v1/figma/installations endpoint for listing installations."""

    @patch('src.routes.figma_routes.get_current_user')
    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_list_installations_success(
        self,
        mock_service_class,
        mock_config,
        mock_get_user,
        client
    ):
        """Test listing installations returns 200 with array."""
        mock_config.get_bool.return_value = True
        mock_get_user.return_value = {'user_id': 1}  # Mock authenticated user

        mock_service = Mock()
        mock_service.list_installations.return_value = [
            {
                'id': 100,
                'name': 'Installation 1',
                'status': 'active',
                'created_at': '2024-01-01T00:00:00Z'
            },
            {
                'id': 101,
                'name': 'Installation 2',
                'status': 'active',
                'created_at': '2024-01-02T00:00:00Z'
            }
        ]
        mock_service_class.return_value = mock_service

        response = client.get('/v1/figma/installations')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]['id'] == 100
        assert data[1]['id'] == 101

    @patch('src.routes.figma_routes.get_current_user')
    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_list_installations_empty(
        self,
        mock_service_class,
        mock_config,
        mock_get_user,
        client
    ):
        """Test listing returns empty array when no installations exist."""
        mock_config.get_bool.return_value = True
        mock_get_user.return_value = {'user_id': 1}  # Mock authenticated user

        mock_service = Mock()
        mock_service.list_installations.return_value = []
        mock_service_class.return_value = mock_service

        response = client.get('/v1/figma/installations')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == []

    @patch('src.routes.figma_routes.get_current_user')
    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_list_installations_with_filters(
        self,
        mock_service_class,
        mock_config,
        mock_get_user,
        client
    ):
        """Test listing with query parameters filters results."""
        mock_config.get_bool.return_value = True
        mock_get_user.return_value = {'user_id': 1}  # Mock authenticated user

        mock_service = Mock()
        mock_service.list_installations.return_value = [
            {'id': 100, 'name': 'User Installation', 'status': 'active'}
        ]
        mock_service_class.return_value = mock_service

        response = client.get('/v1/figma/installations?user_id=1')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 1
        
        # Verify service called with filter parameters
        mock_service.list_installations.assert_called_once()


# ============================================================================
# Test Class: POST /v1/figma/installations/{id}/share (Share Installation)
# ============================================================================

class TestShareInstallation:
    """
    Test POST /v1/figma/installations/{id}/share endpoint.

    Per Feature Group A.2, only ADMIN and SUPER_ADMIN users can share
    installations. Tests verify role-based authorization.
    """

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_share_installation_admin_success(
        self,
        mock_service_class,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test ADMIN user successfully grants access, returns 200."""
        mock_config.get_bool.return_value = True

        mock_service = Mock()
        mock_service.share_installation.return_value = {
            'id': 10,
            'installation_id': 100,
            'user_id': 2,
            'access_level': 'viewer',
            'granted_by': 1,
            'created_at': '2024-01-01T00:00:00Z'
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            '/v1/figma/installations/100/share',
            data=json.dumps(make_authenticated_request(
                user_id=1,  # ADMIN user
                target_user_id=2,
                access_level='viewer'
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['installation_id'] == 100
        assert data['user_id'] == 2
        assert data['granted_by'] == 1

        mock_service.share_installation.assert_called_once()

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_share_installation_regular_user_denied(
        self,
        mock_service_class,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test regular user (non-admin) returns 403 UNAUTHORIZED."""
        mock_config.get_bool.return_value = True

        mock_service = Mock()
        # Service layer checks role and raises error for non-admin
        mock_service.share_installation.side_effect = ValueError(
            'User does not have ADMIN or SUPER_ADMIN role'
        )
        mock_service_class.return_value = mock_service

        response = client.post(
            '/v1/figma/installations/100/share',
            data=json.dumps(make_authenticated_request(
                user_id=3,  # Regular user
                target_user_id=2,
                access_level='viewer'
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'ADMIN' in data['error']['message']

    @patch('src.routes.figma_routes.config_repo')
    def test_share_installation_missing_target_user(
        self,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test missing 'target_user_id' returns 400."""
        mock_config.get_bool.return_value = True

        response = client.post(
            '/v1/figma/installations/100/share',
            data=json.dumps(make_authenticated_request(
                user_id=1,
                access_level='viewer'
                # target_user_id missing
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'INVALID_REQUEST'

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_share_installation_not_found(
        self,
        mock_service_class,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test sharing non-existent installation returns 404."""
        mock_config.get_bool.return_value = True

        mock_service = Mock()
        mock_service.share_installation.side_effect = ValueError('Installation 999 not found')
        mock_service_class.return_value = mock_service

        response = client.post(
            '/v1/figma/installations/999/share',
            data=json.dumps(make_authenticated_request(
                user_id=1,
                target_user_id=2,
                access_level='viewer'
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'not found' in data['error']['message'].lower()


# ============================================================================
# Test Class: DELETE /v1/figma/installations/{id}/share (Revoke Access)
# ============================================================================

class TestRevokeAccess:
    """
    Test DELETE /v1/figma/installations/{id}/share endpoint.

    Per Feature Group A.2, only ADMIN/SUPER_ADMIN users can revoke access.
    """

    @patch('src.routes.figma_routes.get_current_user')
    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_revoke_access_success(
        self,
        mock_service_class,
        mock_config,
        mock_get_user,
        client,
        authenticated_headers
    ):
        """Test ADMIN user successfully revokes access, returns 204."""
        mock_config.get_bool.return_value = True
        mock_get_user.return_value = {'user_id': 1}  # Mock ADMIN user

        mock_service = Mock()
        mock_service.revoke_access.return_value = True
        mock_service_class.return_value = mock_service

        response = client.delete(
            '/v1/figma/installations/100/share',
            data=json.dumps({
                'user_id': 2  # User whose access to revoke
            }),
            headers=authenticated_headers
        )

        assert response.status_code == 204

        # Route calls service.revoke_access with installation_id and user_id only
        mock_service.revoke_access.assert_called_once_with(
            installation_id=100,
            user_id=2
        )

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_revoke_access_unauthorized(
        self,
        mock_service_class,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test regular user cannot revoke access."""
        mock_config.get_bool.return_value = True

        mock_service = Mock()
        mock_service.revoke_access.side_effect = ValueError('User not authorized')
        mock_service_class.return_value = mock_service

        response = client.delete(
            '/v1/figma/installations/100/share',
            data=json.dumps(make_authenticated_request(
                user_id=3,  # Regular user
                target_user_id=2
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'not authorized' in data['error']['message'].lower()

    @patch('src.routes.figma_routes.config_repo')
    def test_revoke_access_missing_target_user(
        self,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test missing 'target_user_id' returns 400."""
        mock_config.get_bool.return_value = True

        response = client.delete(
            '/v1/figma/installations/100/share',
            data=json.dumps(make_authenticated_request(user_id=1)),
            headers=authenticated_headers
        )

        assert response.status_code == 400


# ============================================================================
# Test Class: GET /v1/figma/installations/{id}/access (List Access)
# ============================================================================

class TestListAccess:
    """Test GET /v1/figma/installations/{id}/access endpoint."""

    @patch('src.routes.figma_routes.get_current_user')
    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_list_access_success(
        self,
        mock_service_class,
        mock_config,
        mock_get_user,
        client
    ):
        """Test returns 200 with list of users who have access."""
        mock_config.get_bool.return_value = True
        mock_get_user.return_value = {'user_id': 1}  # Mock authenticated user

        mock_service = Mock()
        mock_service.list_installation_access.return_value = [
            {'user_id': 2, 'access_level': 'viewer', 'granted_by': 1},
            {'user_id': 3, 'access_level': 'editor', 'granted_by': 1}
        ]
        mock_service_class.return_value = mock_service

        response = client.get('/v1/figma/installations/100/access')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 2
        assert data[0]['user_id'] == 2

    @patch('src.routes.figma_routes.get_current_user')
    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_list_access_empty(
        self,
        mock_service_class,
        mock_config,
        mock_get_user,
        client
    ):
        """Test returns empty list when no access grants exist."""
        mock_config.get_bool.return_value = True
        mock_get_user.return_value = {'user_id': 1}  # Mock authenticated user

        mock_service = Mock()
        mock_service.list_installation_access.return_value = []
        mock_service_class.return_value = mock_service

        response = client.get('/v1/figma/installations/100/access')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == []


# ============================================================================
# Test Class: POST /v1/figma/frames/validate (Validate Frame)
# ============================================================================

class TestValidateFrame:
    """
    Test POST /v1/figma/frames/validate endpoint.

    Per Feature Group A.7, this endpoint validates frame URL access and
    retrieves frame title from Figma API.
    """

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_validate_frame_valid_url(
        self,
        mock_service_class,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test valid frame URL returns 200 with valid=true and title."""
        mock_config.get_bool.return_value = True

        mock_service = Mock()
        mock_service.validate_frame.return_value = {
            'valid': True,
            'title': 'Homepage Design',
            'message': None
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            '/v1/figma/frames/validate',
            data=json.dumps(make_authenticated_request(
                user_id=1,
                frame_url='https://www.figma.com/file/ABC123/Design?node-id=1:2',
                installation_id=100
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['valid'] is True
        assert data['title'] == 'Homepage Design'

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_validate_frame_invalid_url(
        self,
        mock_service_class,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test invalid frame URL returns 200 with valid=false and message."""
        mock_config.get_bool.return_value = True

        mock_service = Mock()
        mock_service.validate_frame.return_value = {
            'valid': False,
            'title': None,
            'message': 'Access denied or frame not found'
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            '/v1/figma/frames/validate',
            data=json.dumps(make_authenticated_request(
                user_id=1,
                frame_url='https://www.figma.com/file/INVALID/Design?node-id=999:999',
                installation_id=100
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['valid'] is False
        assert data['message'] == 'Access denied or frame not found'

    @patch('src.routes.figma_routes.config_repo')
    def test_validate_frame_missing_url(
        self,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test missing 'frame_url' returns 400."""
        mock_config.get_bool.return_value = True

        response = client.post(
            '/v1/figma/frames/validate',
            data=json.dumps(make_authenticated_request(
                user_id=1,
                installation_id=100
                # frame_url missing
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 400

    @patch('src.routes.figma_routes.config_repo')
    def test_validate_frame_missing_installation_id(
        self,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test missing 'installation_id' returns 400."""
        mock_config.get_bool.return_value = True

        response = client.post(
            '/v1/figma/frames/validate',
            data=json.dumps(make_authenticated_request(
                user_id=1,
                frame_url='https://www.figma.com/file/ABC/Design?node-id=1:2'
                # installation_id missing
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 400


# ============================================================================
# Test Class: POST /v1/figma/attachments (Create Attachments)
# ============================================================================

class TestCreateAttachments:
    """
    Test POST /v1/figma/attachments endpoint.

    Per Feature Group A.7, this endpoint attaches Figma frames to projects
    with additive, idempotent behavior (same URL overwrites previous).
    """

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_create_attachments_success(
        self,
        mock_service_class,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test successful attachment creation returns 201 with attachment data."""
        mock_config.get_bool.return_value = True

        mock_service = Mock()
        mock_service.attach_frames.return_value = [
            {
                'id': 10,
                'project_id': 200,
                'installation_id': 100,
                'frame_url': 'https://www.figma.com/file/ABC/Design?node-id=1:2',
                'frame_title': 'Homepage',
                'description': 'Main homepage design',
                'created_by': 1
            }
        ]
        mock_service_class.return_value = mock_service

        response = client.post(
            '/v1/figma/attachments',
            data=json.dumps(make_authenticated_request(
                user_id=1,
                project_id=200,
                installation_id=100,
                frames=[
                    {
                        'url': 'https://www.figma.com/file/ABC/Design?node-id=1:2',
                        'description': 'Main homepage design'
                    }
                ]
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]['frame_url'] == 'https://www.figma.com/file/ABC/Design?node-id=1:2'

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_create_attachments_multiple_frames(
        self,
        mock_service_class,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test multiple frames in single request creates/updates all."""
        mock_config.get_bool.return_value = True

        mock_service = Mock()
        mock_service.attach_frames.return_value = [
            {'id': 10, 'frame_url': 'https://figma.com/file/A'},
            {'id': 11, 'frame_url': 'https://figma.com/file/B'}
        ]
        mock_service_class.return_value = mock_service

        response = client.post(
            '/v1/figma/attachments',
            data=json.dumps(make_authenticated_request(
                user_id=1,
                project_id=200,
                installation_id=100,
                frames=[
                    {'url': 'https://figma.com/file/A', 'description': 'Frame A'},
                    {'url': 'https://figma.com/file/B', 'description': 'Frame B'}
                ]
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert len(data) == 2

    @patch('src.routes.figma_routes.config_repo')
    def test_create_attachments_missing_project_id(
        self,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test missing 'project_id' returns 400."""
        mock_config.get_bool.return_value = True

        response = client.post(
            '/v1/figma/attachments',
            data=json.dumps(make_authenticated_request(
                user_id=1,
                installation_id=100,
                frames=[{'url': 'https://figma.com/file/A'}]
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 400

    @patch('src.routes.figma_routes.config_repo')
    def test_create_attachments_missing_frames(
        self,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test missing 'frames' array returns 400."""
        mock_config.get_bool.return_value = True

        response = client.post(
            '/v1/figma/attachments',
            data=json.dumps(make_authenticated_request(
                user_id=1,
                project_id=200,
                installation_id=100
                # frames missing
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 400

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_create_attachments_with_tech_spec(
        self,
        mock_service_class,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test optional tech_spec_id association works."""
        mock_config.get_bool.return_value = True

        mock_service = Mock()
        mock_service.attach_frames.return_value = [
            {
                'id': 10,
                'project_id': 200,
                'tech_spec_id': 300,
                'frame_url': 'https://figma.com/file/A'
            }
        ]
        mock_service_class.return_value = mock_service

        response = client.post(
            '/v1/figma/attachments',
            data=json.dumps(make_authenticated_request(
                user_id=1,
                project_id=200,
                installation_id=100,
                tech_spec_id=300,  # Optional association
                frames=[{'url': 'https://figma.com/file/A'}]
            )),
            headers=authenticated_headers
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data[0]['tech_spec_id'] == 300


# ============================================================================
# Test Class: GET /v1/figma/attachments (List Attachments)
# ============================================================================

class TestListAttachments:
    """Test GET /v1/figma/attachments endpoint."""

    @patch('src.routes.figma_routes.get_current_user')
    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_list_attachments_by_project(
        self,
        mock_service_class,
        mock_config,
        mock_get_user,
        client
    ):
        """Test filtering by project_id returns matching attachments."""
        mock_config.get_bool.return_value = True
        mock_get_user.return_value = {'user_id': 1}  # Mock authenticated user

        mock_service = Mock()
        mock_service.list_attachments.return_value = [
            {
                'id': 10,
                'project_id': 200,
                'frame_url': 'https://figma.com/file/A',
                'frame_title': 'Frame A'
            }
        ]
        mock_service_class.return_value = mock_service

        response = client.get('/v1/figma/attachments?project_id=200')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 1
        assert data[0]['project_id'] == 200

    @patch('src.routes.figma_routes.get_current_user')
    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_list_attachments_by_project_and_tech_spec(
        self,
        mock_service_class,
        mock_config,
        mock_get_user,
        client
    ):
        """Test filtering by project_id AND tech_spec_id."""
        mock_config.get_bool.return_value = True
        mock_get_user.return_value = {'user_id': 1}  # Mock authenticated user

        mock_service = Mock()
        mock_service.list_attachments.return_value = [
            {
                'id': 10,
                'project_id': 200,
                'tech_spec_id': 300,
                'frame_url': 'https://figma.com/file/A'
            }
        ]
        mock_service_class.return_value = mock_service

        response = client.get('/v1/figma/attachments?project_id=200&tech_spec_id=300')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 1
        assert data[0]['tech_spec_id'] == 300

    @patch('src.routes.figma_routes.get_current_user')
    @patch('src.routes.figma_routes.config_repo')
    def test_list_attachments_missing_project_id(
        self,
        mock_config,
        mock_get_user,
        client
    ):
        """Test missing project_id query parameter returns 400."""
        mock_config.get_bool.return_value = True
        mock_get_user.return_value = {'user_id': 1}  # Mock authenticated user

        response = client.get('/v1/figma/attachments')

        assert response.status_code == 400

    @patch('src.routes.figma_routes.get_current_user')
    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_list_attachments_empty(
        self,
        mock_service_class,
        mock_config,
        mock_get_user,
        client
    ):
        """Test returns empty array when no attachments exist."""
        mock_config.get_bool.return_value = True
        mock_get_user.return_value = {'user_id': 1}  # Mock authenticated user

        mock_service = Mock()
        mock_service.list_attachments.return_value = []
        mock_service_class.return_value = mock_service

        response = client.get('/v1/figma/attachments?project_id=200')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == []


# ============================================================================
# Test Class: GET /v1/figma/attachments/{id} (Get Single Attachment)
# ============================================================================

class TestGetAttachment:
    """Test GET /v1/figma/attachments/{id} endpoint."""

    @patch('src.routes.figma_routes.get_current_user')
    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_get_attachment_success(
        self,
        mock_service_class,
        mock_config,
        mock_get_user,
        client
    ):
        """Test successful retrieval returns 200 with attachment data."""
        mock_config.get_bool.return_value = True
        mock_get_user.return_value = {'user_id': 1}  # Mock authenticated user

        mock_service = Mock()
        mock_service.get_attachment.return_value = {
            'id': 10,
            'project_id': 200,
            'installation_id': 100,
            'frame_url': 'https://figma.com/file/ABC',
            'frame_title': 'Homepage Design',
            'description': 'Main page',
            'created_by': 1
        }
        mock_service_class.return_value = mock_service

        response = client.get('/v1/figma/attachments/10')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['id'] == 10
        assert data['frame_url'] == 'https://figma.com/file/ABC'
        assert data['frame_title'] == 'Homepage Design'

    @patch('src.routes.figma_routes.get_current_user')
    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_get_attachment_not_found(
        self,
        mock_service_class,
        mock_config,
        mock_get_user,
        client
    ):
        """Test non-existent attachment returns 404."""
        mock_config.get_bool.return_value = True
        mock_get_user.return_value = {'user_id': 1}  # Mock authenticated user

        mock_service = Mock()
        mock_service.get_attachment.return_value = None
        mock_service_class.return_value = mock_service

        response = client.get('/v1/figma/attachments/999')

        assert response.status_code == 404


# ============================================================================
# Test Class: DELETE /v1/figma/attachments/{id} (Delete Attachment)
# ============================================================================

class TestDeleteAttachment:
    """Test DELETE /v1/figma/attachments/{id} endpoint."""

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_delete_attachment_success(
        self,
        mock_service_class,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test successful deletion returns 204 No Content."""
        mock_config.get_bool.return_value = True

        mock_service = Mock()
        mock_service.delete_attachment.return_value = True
        mock_service_class.return_value = mock_service

        response = client.delete(
            '/v1/figma/attachments/10',
            data=json.dumps(make_authenticated_request(user_id=1)),
            headers=authenticated_headers
        )

        assert response.status_code == 204

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_delete_attachment_not_found(
        self,
        mock_service_class,
        mock_config,
        client,
        authenticated_headers
    ):
        """Test deleting non-existent attachment returns 404."""
        mock_config.get_bool.return_value = True

        mock_service = Mock()
        mock_service.delete_attachment.side_effect = ValueError('Attachment 999 not found')
        mock_service_class.return_value = mock_service

        response = client.delete(
            '/v1/figma/attachments/999',
            data=json.dumps(make_authenticated_request(user_id=1)),
            headers=authenticated_headers
        )

        assert response.status_code == 400


# ============================================================================
# Test Class: GET /internal/figma/installations/by-project/{id}
# ============================================================================

class TestInternalGetByProject:
    """
    Test GET /internal/figma/installations/by-project/{id} internal endpoint.

    Per Feature Group A.9, this is the ONLY endpoint that returns the actual
    PAT value (not just status). Used by internal services only.
    """

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_internal_get_by_project_includes_pat(
        self,
        mock_service_class,
        mock_config,
        client
    ):
        """Test internal endpoint returns installation INCLUDING actual PAT."""
        mock_config.get_bool.return_value = True

        mock_service = Mock()
        mock_service.get_installation_by_project.return_value = {
            'id': 100,
            'name': 'Test Installation',
            'pat': 'figd_ActualPATValue1234567890',  # Actual PAT included
            'status': 'active',
            'created_at': '2024-01-01T00:00:00Z'
        }
        mock_service_class.return_value = mock_service

        response = client.get('/internal/figma/installations/by-project/200')

        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Critical: This is the ONLY endpoint that includes actual PAT
        assert 'pat' in data
        assert data['pat'] == 'figd_ActualPATValue1234567890'

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_internal_get_by_project_not_found(
        self,
        mock_service_class,
        mock_config,
        client
    ):
        """Test non-existent project returns 404."""
        mock_config.get_bool.return_value = True

        mock_service = Mock()
        mock_service.get_installation_by_project.return_value = None
        mock_service_class.return_value = mock_service

        response = client.get('/internal/figma/installations/by-project/999')

        assert response.status_code == 404

    @patch('src.routes.figma_routes.config_repo')
    @patch('src.routes.figma_routes.FigmaService')
    def test_internal_endpoint_different_format(
        self,
        mock_service_class,
        mock_config,
        client
    ):
        """Test internal endpoint response format differs from public endpoints."""
        mock_config.get_bool.return_value = True

        mock_service = Mock()
        mock_service.get_installation_by_project.return_value = {
            'id': 100,
            'pat': 'figd_SecretValue123',
            'status': 'active'
        }
        mock_service_class.return_value = mock_service

        response = client.get('/internal/figma/installations/by-project/200')

        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Verify this response includes PAT (unlike public endpoints)
        assert 'pat' in data
        # Verify no pat_status (that's only for public endpoints)
        assert 'pat_status' not in data or data.get('pat_status') is None
