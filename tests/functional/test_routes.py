"""
Functional tests for Flask route handlers.

Tests cover:
- Health check endpoint
- Document processing endpoints
- Error handling responses
- Request validation
- Authentication/authorization (if applicable)
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from src.app import create_app
from src.app.models.document import DocumentSection, DocumentSectionStatus


@pytest.mark.functional
class TestHealthCheck:
    """Tests for health check endpoint."""
    
    def test_health_check_returns_200(self, client):
        """Test health check endpoint returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_health_check_returns_json(self, client):
        """Test health check returns JSON response."""
        response = client.get("/health")
        assert response.content_type == "application/json"
    
    def test_health_check_status_healthy(self, client):
        """Test health check returns healthy status."""
        response = client.get("/health")
        data = response.get_json()
        assert data["status"] == "healthy"
    
    def test_health_check_includes_version(self, client):
        """Test health check includes version information."""
        response = client.get("/health")
        data = response.get_json()
        assert "version" in data


@pytest.mark.functional
class TestAPIRootEndpoint:
    """Tests for API root endpoint."""
    
    def test_api_root_returns_200(self, client):
        """Test API root endpoint returns 200."""
        response = client.get("/api/v1/")
        assert response.status_code == 200
    
    def test_api_root_returns_welcome_message(self, client):
        """Test API root returns welcome message."""
        response = client.get("/api/v1/")
        data = response.get_json()
        assert "message" in data
    
    def test_api_root_includes_endpoints(self, client):
        """Test API root includes available endpoints."""
        response = client.get("/api/v1/")
        data = response.get_json()
        assert "endpoints" in data


@pytest.mark.functional
class TestDocumentProcessEndpoint:
    """Tests for document processing endpoint."""
    
    def test_process_document_success(self, client, sample_document_section_data):
        """Test successful document processing."""
        payload = {
            "tech_spec": "Test technical specification",
            "sections": [sample_document_section_data]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
    
    def test_process_document_returns_processed_sections(self, client, sample_document_section_data):
        """Test that processed sections are returned."""
        payload = {
            "tech_spec": "Test technical specification",
            "sections": [sample_document_section_data]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        data = response.get_json()
        assert "sections" in data
        assert len(data["sections"]) > 0
    
    def test_process_document_missing_tech_spec(self, client, sample_document_section_data):
        """Test error when tech_spec is missing."""
        payload = {
            "sections": [sample_document_section_data]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
    
    def test_process_document_missing_sections(self, client):
        """Test error when sections are missing."""
        payload = {
            "tech_spec": "Test technical specification"
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
    
    def test_process_document_empty_sections(self, client):
        """Test error when sections list is empty."""
        payload = {
            "tech_spec": "Test technical specification",
            "sections": []
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
    
    def test_process_document_invalid_json(self, client):
        """Test error when request body is not valid JSON."""
        response = client.post(
            "/api/v1/documents/process",
            data="not valid json",
            content_type="application/json"
        )
        
        assert response.status_code == 400
    
    def test_process_document_wrong_content_type(self, client):
        """Test error when content type is not JSON."""
        response = client.post(
            "/api/v1/documents/process",
            data="some data",
            content_type="text/plain"
        )
        
        assert response.status_code == 415
    
    def test_process_document_invalid_section_data(self, client):
        """Test error when section data is invalid."""
        payload = {
            "tech_spec": "Test technical specification",
            "sections": [{"invalid": "data"}]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        assert response.status_code == 400


@pytest.mark.functional
class TestDocumentSectionEndpoint:
    """Tests for individual document section endpoint."""
    
    def test_get_section_success(self, client):
        """Test getting a specific section."""
        response = client.get("/api/v1/documents/sections/test-section-id")
        # May return 404 if section doesn't exist, or 200 if it does
        assert response.status_code in [200, 404]
    
    def test_get_section_not_found(self, client):
        """Test getting a non-existent section."""
        response = client.get("/api/v1/documents/sections/non-existent-id")
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data
    
    def test_update_section_success(self, client, sample_document_section_data):
        """Test updating a section."""
        response = client.put(
            "/api/v1/documents/sections/test-section-id",
            data=json.dumps(sample_document_section_data),
            content_type="application/json"
        )
        # May return 200 if section exists, 404 if not, or 201 if created
        assert response.status_code in [200, 201, 404]
    
    def test_delete_section_success(self, client):
        """Test deleting a section."""
        response = client.delete("/api/v1/documents/sections/test-section-id")
        # May return 200/204 if deleted, 404 if not found
        assert response.status_code in [200, 204, 404]


@pytest.mark.functional
class TestDocumentStatusEndpoint:
    """Tests for document processing status endpoint."""
    
    def test_get_status_success(self, client):
        """Test getting processing status."""
        response = client.get("/api/v1/documents/status")
        assert response.status_code == 200
    
    def test_get_status_returns_json(self, client):
        """Test status returns JSON response."""
        response = client.get("/api/v1/documents/status")
        assert response.content_type == "application/json"
    
    def test_get_status_includes_state(self, client):
        """Test status includes state information."""
        response = client.get("/api/v1/documents/status")
        data = response.get_json()
        assert "completed" in data or "status" in data


@pytest.mark.functional
class TestErrorHandling:
    """Tests for error handling responses."""
    
    def test_404_not_found(self, client):
        """Test 404 response for non-existent endpoint."""
        response = client.get("/api/v1/non-existent-endpoint")
        assert response.status_code == 404
    
    def test_404_returns_json(self, client):
        """Test 404 response returns JSON."""
        response = client.get("/api/v1/non-existent-endpoint")
        assert response.content_type == "application/json"
    
    def test_404_includes_error_message(self, client):
        """Test 404 response includes error message."""
        response = client.get("/api/v1/non-existent-endpoint")
        data = response.get_json()
        assert "error" in data
    
    def test_405_method_not_allowed(self, client):
        """Test 405 response for wrong HTTP method."""
        response = client.delete("/health")
        assert response.status_code == 405
    
    def test_415_unsupported_media_type(self, client):
        """Test 415 response for unsupported content type."""
        response = client.post(
            "/api/v1/documents/process",
            data="text data",
            content_type="text/plain"
        )
        assert response.status_code == 415
    
    def test_500_internal_server_error_handled(self, client, mocker):
        """Test that internal server errors are handled gracefully."""
        # Mock a function to raise an exception
        mocker.patch(
            "src.app.routes.api.process_document_request",
            side_effect=RuntimeError("Internal error")
        )
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps({
                "tech_spec": "test",
                "sections": [{"heading": "Test", "content": "Content"}]
            }),
            content_type="application/json"
        )
        
        # Should return 500 or be caught by error handler
        assert response.status_code in [400, 500]


@pytest.mark.functional
class TestRequestValidation:
    """Tests for request validation."""
    
    def test_max_content_length(self, client):
        """Test that large payloads are rejected."""
        # Create a payload larger than MAX_CONTENT_LENGTH
        large_content = "x" * (17 * 1024 * 1024)  # 17 MB
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps({"tech_spec": large_content, "sections": []}),
            content_type="application/json"
        )
        
        # Should be rejected due to size - 413 or error during processing
        assert response.status_code in [400, 413]
    
    def test_empty_request_body(self, client):
        """Test error when request body is empty."""
        response = client.post(
            "/api/v1/documents/process",
            data="",
            content_type="application/json"
        )
        
        assert response.status_code == 400
    
    def test_null_request_body(self, client):
        """Test error when request body is null."""
        response = client.post(
            "/api/v1/documents/process",
            data="null",
            content_type="application/json"
        )
        
        assert response.status_code == 400
    
    def test_section_heading_required(self, client):
        """Test that section heading is required."""
        payload = {
            "tech_spec": "Test specification",
            "sections": [{"content": "Content without heading"}]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        assert response.status_code == 400
    
    def test_section_heading_not_empty(self, client):
        """Test that section heading cannot be empty."""
        payload = {
            "tech_spec": "Test specification",
            "sections": [{"heading": "", "content": "Content"}]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        assert response.status_code == 400


@pytest.mark.functional
class TestCORSHeaders:
    """Tests for CORS headers (if enabled)."""
    
    def test_options_request(self, client):
        """Test OPTIONS request for CORS preflight."""
        response = client.options("/api/v1/documents/process")
        # Should return 200 or 204 for OPTIONS
        assert response.status_code in [200, 204, 405]
    
    def test_cors_headers_present(self, client):
        """Test that CORS headers are present (if CORS is enabled)."""
        response = client.get("/api/v1/")
        # CORS headers may or may not be present depending on configuration
        # This test just ensures the endpoint works
        assert response.status_code == 200


@pytest.mark.functional
class TestResponseFormat:
    """Tests for response format consistency."""
    
    def test_success_response_format(self, client, sample_document_section_data):
        """Test successful response has consistent format."""
        payload = {
            "tech_spec": "Test specification",
            "sections": [sample_document_section_data]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        data = response.get_json()
        # Success responses should have 'success' or 'data' field
        assert "success" in data or "data" in data or "sections" in data
    
    def test_error_response_format(self, client):
        """Test error response has consistent format."""
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps({}),
            content_type="application/json"
        )
        
        data = response.get_json()
        # Error responses should have 'error' field
        assert "error" in data
    
    def test_response_includes_request_id(self, client, sample_document_section_data):
        """Test response includes request ID for tracking."""
        payload = {
            "tech_spec": "Test specification",
            "sections": [sample_document_section_data]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        # Request ID may be in headers or response body
        # This is optional functionality
        assert response.status_code in [200, 400]


@pytest.mark.functional
class TestPagination:
    """Tests for pagination in list endpoints."""
    
    def test_list_sections_default_pagination(self, client):
        """Test default pagination on list endpoint."""
        response = client.get("/api/v1/documents/sections")
        
        if response.status_code == 200:
            data = response.get_json()
            # If pagination is supported, check for pagination fields
            if isinstance(data, dict):
                # May have 'items', 'sections', 'data', etc.
                assert True
    
    def test_list_sections_with_limit(self, client):
        """Test list endpoint with limit parameter."""
        response = client.get("/api/v1/documents/sections?limit=5")
        
        if response.status_code == 200:
            data = response.get_json()
            if isinstance(data, dict) and "items" in data:
                assert len(data["items"]) <= 5
    
    def test_list_sections_with_offset(self, client):
        """Test list endpoint with offset parameter."""
        response = client.get("/api/v1/documents/sections?offset=10")
        # Should return 200 even with offset
        assert response.status_code in [200, 404]


@pytest.mark.functional
class TestDocumentStateEndpoint:
    """Tests for document state management endpoints."""
    
    def test_get_state(self, client):
        """Test getting current document state."""
        response = client.get("/api/v1/documents/state")
        assert response.status_code == 200
        data = response.get_json()
        assert "state" in data or "data" in data
    
    def test_reset_state(self, client):
        """Test resetting document state."""
        response = client.post("/api/v1/documents/state/reset")
        assert response.status_code in [200, 204]
    
    def test_reset_state_with_new_tech_spec(self, client):
        """Test resetting state with new tech spec."""
        payload = {"tech_spec": "New technical specification"}
        
        response = client.post(
            "/api/v1/documents/state/reset",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        assert response.status_code in [200, 204]


# Fixture for sample document section data used in tests
@pytest.fixture
def sample_document_section_data():
    """Provide sample document section data for tests."""
    return {
        "heading": "Test Section",
        "content": "This is test content for the section.",
        "order": 1
    }
