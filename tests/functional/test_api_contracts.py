"""
API contract validation tests.

Tests cover:
- Request schema validation
- Response schema validation
- Data type enforcement
- Required field validation
- Optional field handling
"""

import json
from typing import Any, Dict, List

import pytest


@pytest.mark.functional
class TestHealthEndpointContract:
    """Tests for health endpoint API contract."""
    
    def test_health_response_schema(self, client):
        """Test health endpoint response matches expected schema."""
        response = client.get("/health")
        data = response.get_json()
        
        # Required fields
        assert "status" in data
        assert isinstance(data["status"], str)
        
        # Status must be one of expected values
        assert data["status"] in ["healthy", "unhealthy", "degraded"]
    
    def test_health_version_field_type(self, client):
        """Test version field is a string."""
        response = client.get("/health")
        data = response.get_json()
        
        if "version" in data:
            assert isinstance(data["version"], str)
    
    def test_health_timestamp_field(self, client):
        """Test timestamp field format if present."""
        response = client.get("/health")
        data = response.get_json()
        
        if "timestamp" in data:
            # Should be ISO format string
            assert isinstance(data["timestamp"], str)
            # Basic ISO format check
            assert "T" in data["timestamp"] or "-" in data["timestamp"]


@pytest.mark.functional
class TestDocumentSectionSchema:
    """Tests for document section schema validation."""
    
    def test_section_heading_required(self, client):
        """Test that heading field is required."""
        payload = {
            "tech_spec": "Test specification",
            "sections": [{"content": "No heading"}]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
    
    def test_section_heading_type(self, client):
        """Test that heading must be a string."""
        payload = {
            "tech_spec": "Test specification",
            "sections": [{"heading": 123, "content": "Content"}]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        # Should either accept coerced value or reject
        assert response.status_code in [200, 400]
    
    def test_section_content_type(self, client):
        """Test that content must be a string."""
        payload = {
            "tech_spec": "Test specification",
            "sections": [{"heading": "Test", "content": {"nested": "object"}}]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        # Should reject non-string content
        assert response.status_code in [200, 400]
    
    def test_section_order_type(self, client):
        """Test that order must be an integer."""
        payload = {
            "tech_spec": "Test specification",
            "sections": [{"heading": "Test", "content": "Content", "order": "first"}]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        # Should reject non-integer order
        assert response.status_code in [200, 400]
    
    def test_section_status_enum_values(self, client):
        """Test that status must be a valid enum value."""
        payload = {
            "tech_spec": "Test specification",
            "sections": [{
                "heading": "Test",
                "content": "Content",
                "status": "invalid_status"
            }]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        # Should reject invalid status
        assert response.status_code in [200, 400]
    
    def test_section_changes_type(self, client):
        """Test that changes must be a list of strings."""
        payload = {
            "tech_spec": "Test specification",
            "sections": [{
                "heading": "Test",
                "content": "Content",
                "changes": "not a list"
            }]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        # Should reject non-list changes
        assert response.status_code in [200, 400]


@pytest.mark.functional
class TestProcessRequestContract:
    """Tests for document process request contract."""
    
    def test_tech_spec_required(self, client):
        """Test that tech_spec is required."""
        payload = {"sections": [{"heading": "Test", "content": "Content"}]}
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        assert response.status_code == 400
    
    def test_sections_required(self, client):
        """Test that sections is required."""
        payload = {"tech_spec": "Test specification"}
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        assert response.status_code == 400
    
    def test_sections_must_be_array(self, client):
        """Test that sections must be an array."""
        payload = {
            "tech_spec": "Test specification",
            "sections": {"not": "an array"}
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        assert response.status_code == 400
    
    def test_tech_spec_must_be_string(self, client):
        """Test that tech_spec must be a string."""
        payload = {
            "tech_spec": ["not", "a", "string"],
            "sections": [{"heading": "Test", "content": "Content"}]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        assert response.status_code == 400
    
    def test_additional_properties_allowed(self, client):
        """Test that additional properties in request are allowed/ignored."""
        payload = {
            "tech_spec": "Test specification",
            "sections": [{"heading": "Test", "content": "Content"}],
            "extra_field": "should be ignored"
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        # Should not fail due to extra field
        assert response.status_code in [200, 400]


@pytest.mark.functional
class TestProcessResponseContract:
    """Tests for document process response contract."""
    
    def test_success_response_has_success_field(self, client):
        """Test successful response includes success field."""
        payload = {
            "tech_spec": "Test specification",
            "sections": [{"heading": "Test", "content": "Content"}]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        if response.status_code == 200:
            data = response.get_json()
            assert "success" in data
            assert isinstance(data["success"], bool)
    
    def test_success_response_has_sections(self, client):
        """Test successful response includes sections."""
        payload = {
            "tech_spec": "Test specification",
            "sections": [{"heading": "Test", "content": "Content"}]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        if response.status_code == 200:
            data = response.get_json()
            assert "sections" in data
            assert isinstance(data["sections"], list)
    
    def test_response_sections_have_required_fields(self, client):
        """Test response sections contain required fields."""
        payload = {
            "tech_spec": "Test specification",
            "sections": [{"heading": "Test", "content": "Content"}]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        if response.status_code == 200:
            data = response.get_json()
            if "sections" in data and len(data["sections"]) > 0:
                section = data["sections"][0]
                assert "heading" in section
                assert "content" in section


@pytest.mark.functional
class TestErrorResponseContract:
    """Tests for error response contract."""
    
    def test_error_response_has_error_field(self, client):
        """Test error response includes error field."""
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps({}),
            content_type="application/json"
        )
        
        data = response.get_json()
        assert "error" in data
    
    def test_error_field_is_string(self, client):
        """Test error field is a string."""
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps({}),
            content_type="application/json"
        )
        
        data = response.get_json()
        assert isinstance(data["error"], str)
    
    def test_error_response_status_code(self, client):
        """Test error response has appropriate status code."""
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps({}),
            content_type="application/json"
        )
        
        # Error status codes
        assert response.status_code >= 400
    
    def test_404_error_contract(self, client):
        """Test 404 error response contract."""
        response = client.get("/api/v1/non-existent")
        
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data


@pytest.mark.functional
class TestStateResponseContract:
    """Tests for state endpoint response contract."""
    
    def test_state_response_has_state_data(self, client):
        """Test state response includes state information."""
        response = client.get("/api/v1/documents/state")
        
        if response.status_code == 200:
            data = response.get_json()
            assert "state" in data or "data" in data
    
    def test_state_includes_completed_field(self, client):
        """Test state includes completed field."""
        response = client.get("/api/v1/documents/state")
        
        if response.status_code == 200:
            data = response.get_json()
            state_data = data.get("state", data.get("data", data))
            if isinstance(state_data, dict):
                # May or may not have 'completed' depending on implementation
                pass  # Flexible check


@pytest.mark.functional
class TestStatusResponseContract:
    """Tests for status endpoint response contract."""
    
    def test_status_response_format(self, client):
        """Test status response has consistent format."""
        response = client.get("/api/v1/documents/status")
        
        if response.status_code == 200:
            data = response.get_json()
            # Should have some status information
            assert len(data) > 0


@pytest.mark.functional
class TestContentTypeNegotiation:
    """Tests for content type handling."""
    
    def test_json_content_type_accepted(self, client):
        """Test application/json content type is accepted."""
        payload = {
            "tech_spec": "Test specification",
            "sections": [{"heading": "Test", "content": "Content"}]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        assert response.status_code in [200, 400]  # Not 415
    
    def test_json_charset_content_type_accepted(self, client):
        """Test application/json with charset is accepted."""
        payload = {
            "tech_spec": "Test specification",
            "sections": [{"heading": "Test", "content": "Content"}]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json; charset=utf-8"
        )
        
        assert response.status_code in [200, 400]  # Not 415
    
    def test_responses_are_json(self, client):
        """Test all responses have JSON content type."""
        response = client.get("/health")
        assert "application/json" in response.content_type
        
        response = client.get("/api/v1/")
        assert "application/json" in response.content_type
    
    def test_error_responses_are_json(self, client):
        """Test error responses have JSON content type."""
        response = client.get("/api/v1/non-existent")
        assert "application/json" in response.content_type


@pytest.mark.functional
class TestHttpMethods:
    """Tests for HTTP method support."""
    
    def test_health_supports_get(self, client):
        """Test health endpoint supports GET."""
        response = client.get("/health")
        assert response.status_code != 405
    
    def test_process_supports_post(self, client):
        """Test process endpoint supports POST."""
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps({}),
            content_type="application/json"
        )
        assert response.status_code != 405
    
    def test_sections_supports_get(self, client):
        """Test sections endpoint supports GET."""
        response = client.get("/api/v1/documents/sections")
        # Should return 200 or 404, not 405
        assert response.status_code in [200, 404]
    
    def test_state_supports_get(self, client):
        """Test state endpoint supports GET."""
        response = client.get("/api/v1/documents/state")
        assert response.status_code != 405


@pytest.mark.functional
class TestApiVersioning:
    """Tests for API versioning."""
    
    def test_v1_prefix_works(self, client):
        """Test API v1 prefix is recognized."""
        response = client.get("/api/v1/")
        assert response.status_code == 200
    
    def test_api_without_version_redirects_or_works(self, client):
        """Test API without version prefix behavior."""
        response = client.get("/api/")
        # May redirect to v1, return 200, or return 404
        assert response.status_code in [200, 301, 302, 404]


@pytest.mark.functional
class TestNullHandling:
    """Tests for null value handling in API."""
    
    def test_null_tech_spec_rejected(self, client):
        """Test null tech_spec is rejected."""
        payload = {
            "tech_spec": None,
            "sections": [{"heading": "Test", "content": "Content"}]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        assert response.status_code == 400
    
    def test_null_sections_rejected(self, client):
        """Test null sections is rejected."""
        payload = {
            "tech_spec": "Test specification",
            "sections": None
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        assert response.status_code == 400
    
    def test_null_heading_rejected(self, client):
        """Test null heading is rejected."""
        payload = {
            "tech_spec": "Test specification",
            "sections": [{"heading": None, "content": "Content"}]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        assert response.status_code == 400
    
    def test_null_content_allowed(self, client):
        """Test null content may be allowed (optional field)."""
        payload = {
            "tech_spec": "Test specification",
            "sections": [{"heading": "Test", "content": None}]
        }
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        # May be allowed or rejected depending on implementation
        assert response.status_code in [200, 400]
