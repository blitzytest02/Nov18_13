"""
API routes for the reverse document generator.

This module defines the REST API endpoints for the Flask application,
including document processing, health checks, and status endpoints.
"""

from flask import Blueprint, jsonify, request, current_app
from typing import Any, Dict, List, Optional, Tuple
import uuid

from src.app.models.document import DocumentSection, DocumentSectionStatus
from src.app.services.document_helper import ReverseDocumentHelper
from src.app.services.state_manager import get_state, update_state, validate_state

# Create blueprints
health_bp = Blueprint("health", __name__)
api_bp = Blueprint("api", __name__, url_prefix="/api")
api_v1_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")

# In-memory storage for sections (in production, this would be a database)
_sections_store: Dict[str, Dict[str, Any]] = {}
_current_state: Dict[str, Any] = {
    "tech_spec": "",
    "document_sections": [],
    "current_section_index": 0,
    "completed": False,
    "error": None,
    "metadata": {}
}


def process_document_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a document request and return results.
    
    This function is separated for easier mocking in tests.
    
    Args:
        data: Request data containing tech_spec and sections
        
    Returns:
        Processing result dictionary
    """
    tech_spec = data.get("tech_spec")
    sections_data = data.get("sections", [])
    
    helper = ReverseDocumentHelper(tech_spec=tech_spec)
    
    for section_data in sections_data:
        helper.process_document_section(section_data)
    
    return {
        "success": True,
        "sections": helper.get_document_sections(),
        "state": helper.to_dict(),
        "section_count": helper.get_section_count()
    }


def get_document_status() -> Dict[str, Any]:
    """
    Get the current document processing status.
    
    This function is separated for easier mocking in tests.
    
    Returns:
        Status dictionary
    """
    global _current_state
    return {
        "completed": _current_state.get("completed", False),
        "section_count": len(_current_state.get("document_sections", [])),
        "current_index": _current_state.get("current_section_index", 0),
        "has_error": _current_state.get("error") is not None
    }


# Health endpoints (at root level)
@health_bp.route("/health", methods=["GET"])
def health_check() -> Tuple[Dict[str, Any], int]:
    """
    Health check endpoint.
    
    Returns:
        JSON response with health status
    """
    return jsonify({
        "status": "healthy",
        "version": "1.0.0",
        "service": "reverse-document-generator"
    }), 200


# API Root endpoint
@api_bp.route("/", methods=["GET"])
def api_root() -> Tuple[Dict[str, Any], int]:
    """
    API root endpoint.
    
    Returns:
        JSON response with API information
    """
    return jsonify({
        "message": "Reverse Document Generator API",
        "version": "1.0",
        "endpoints": {
            "v1": "/api/v1/"
        }
    }), 200


# API v1 Root endpoint
@api_v1_bp.route("/", methods=["GET"])
def api_v1_root() -> Tuple[Dict[str, Any], int]:
    """
    API v1 root endpoint.
    
    Returns:
        JSON response with API v1 information
    """
    return jsonify({
        "message": "Reverse Document Generator API v1",
        "version": "1.0.0",
        "endpoints": [
            "/api/v1/documents/process",
            "/api/v1/documents/status",
            "/api/v1/documents/state",
            "/api/v1/documents/sections"
        ]
    }), 200


# Document processing endpoints
@api_v1_bp.route("/documents/process", methods=["POST", "OPTIONS"])
def process_document() -> Tuple[Dict[str, Any], int]:
    """
    Process a document with the provided tech spec.
    
    Expected JSON payload:
    {
        "tech_spec": "string",
        "sections": [list of sections]
    }
    
    Returns:
        JSON response with processing result
    """
    # Handle OPTIONS for CORS preflight
    if request.method == "OPTIONS":
        return jsonify({}), 204
    
    # Validate content type
    content_type = request.content_type or ""
    if not content_type.startswith("application/json"):
        return jsonify({
            "error": "Unsupported Media Type",
            "message": "Content-Type must be application/json"
        }), 415
    
    # Get JSON data
    try:
        data = request.get_json(force=False, silent=False)
    except Exception as e:
        return jsonify({
            "error": "Bad Request",
            "message": f"Invalid JSON: {str(e)}"
        }), 400
    
    # Check for empty or null body
    if data is None:
        return jsonify({
            "error": "Bad Request",
            "message": "Request body cannot be empty or null"
        }), 400
    
    if not isinstance(data, dict):
        return jsonify({
            "error": "Bad Request",
            "message": "Request body must be a JSON object"
        }), 400
    
    # Validate tech_spec
    tech_spec = data.get("tech_spec")
    if tech_spec is None:
        return jsonify({
            "error": "Bad Request",
            "message": "tech_spec is required"
        }), 400
    
    if not isinstance(tech_spec, str):
        return jsonify({
            "error": "Bad Request",
            "message": "tech_spec must be a string"
        }), 400
    
    # Validate sections
    sections = data.get("sections")
    if sections is None:
        return jsonify({
            "error": "Bad Request",
            "message": "sections is required"
        }), 400
    
    if not isinstance(sections, list):
        return jsonify({
            "error": "Bad Request",
            "message": "sections must be an array"
        }), 400
    
    if len(sections) == 0:
        return jsonify({
            "error": "Bad Request",
            "message": "sections cannot be empty"
        }), 400
    
    # Validate each section
    for i, section in enumerate(sections):
        if not isinstance(section, dict):
            return jsonify({
                "error": "Bad Request",
                "message": f"Section {i} must be an object"
            }), 400
        
        heading = section.get("heading")
        if heading is None:
            return jsonify({
                "error": "Bad Request",
                "message": f"Section {i} is missing required field: heading"
            }), 400
        
        if not isinstance(heading, str) or not heading.strip():
            return jsonify({
                "error": "Bad Request",
                "message": f"Section {i}: heading must be a non-empty string"
            }), 400
    
    try:
        result = process_document_request(data)
        return jsonify(result), 200
        
    except ValueError as e:
        return jsonify({
            "error": "Bad Request",
            "message": str(e)
        }), 400
    except Exception as e:
        return jsonify({
            "error": "Internal Server Error",
            "message": f"Processing failed: {str(e)}"
        }), 500


@api_v1_bp.route("/documents/status", methods=["GET"])
def get_status() -> Tuple[Dict[str, Any], int]:
    """
    Get document processing status.
    
    Returns:
        JSON response with status information
    """
    try:
        status = get_document_status()
        return jsonify(status), 200
    except Exception as e:
        return jsonify({
            "error": "Internal Server Error",
            "message": str(e)
        }), 500


@api_v1_bp.route("/documents/state", methods=["GET"])
def get_document_state() -> Tuple[Dict[str, Any], int]:
    """
    Get the current document processing state.
    
    Returns:
        JSON response with current state
    """
    global _current_state
    return jsonify({
        "state": _current_state,
        "data": _current_state
    }), 200


@api_v1_bp.route("/documents/state/reset", methods=["POST"])
def reset_state() -> Tuple[Dict[str, Any], int]:
    """
    Reset the document processing state.
    
    Optional JSON payload:
    {
        "tech_spec": "new technical specification"
    }
    
    Returns:
        JSON response confirming reset
    """
    global _current_state
    
    # Get optional new tech spec from request
    new_tech_spec = ""
    if request.is_json:
        data = request.get_json(silent=True) or {}
        new_tech_spec = data.get("tech_spec", "")
    
    # Reset state
    _current_state = {
        "tech_spec": new_tech_spec,
        "document_sections": [],
        "current_section_index": 0,
        "completed": False,
        "error": None,
        "metadata": {}
    }
    
    return jsonify({
        "success": True,
        "message": "State reset successfully"
    }), 200


# Document sections endpoints
@api_v1_bp.route("/documents/sections", methods=["GET"])
def list_sections() -> Tuple[Dict[str, Any], int]:
    """
    List all document sections.
    
    Query parameters:
    - status: Filter by status
    - limit: Maximum number of results
    - offset: Pagination offset
    
    Returns:
        JSON response with list of sections
    """
    global _sections_store
    
    status_filter = request.args.get("status")
    limit = request.args.get("limit", type=int)
    offset = request.args.get("offset", 0, type=int)
    
    sections = list(_sections_store.values())
    
    # Apply status filter
    if status_filter:
        try:
            DocumentSectionStatus(status_filter)
            sections = [s for s in sections if s.get("status") == status_filter]
        except ValueError:
            return jsonify({
                "error": "Bad Request",
                "message": f"Invalid status filter: {status_filter}"
            }), 400
    
    # Apply pagination
    total = len(sections)
    if offset:
        sections = sections[offset:]
    if limit:
        sections = sections[:limit]
    
    return jsonify({
        "items": sections,
        "sections": sections,
        "total": total,
        "offset": offset,
        "limit": limit
    }), 200


@api_v1_bp.route("/documents/sections/<section_id>", methods=["GET", "PUT", "DELETE"])
def section_detail(section_id: str) -> Tuple[Dict[str, Any], int]:
    """
    Get, update, or delete a specific document section.
    
    Args:
        section_id: The section identifier
        
    Returns:
        JSON response with section data or status
    """
    global _sections_store
    
    if request.method == "GET":
        section = _sections_store.get(section_id)
        if not section:
            return jsonify({
                "error": "Not Found",
                "message": f"Section {section_id} not found"
            }), 404
        return jsonify(section), 200
    
    elif request.method == "PUT":
        if not request.is_json:
            return jsonify({
                "error": "Unsupported Media Type",
                "message": "Content-Type must be application/json"
            }), 415
        
        data = request.get_json()
        if not data:
            return jsonify({
                "error": "Bad Request",
                "message": "Request body cannot be empty"
            }), 400
        
        # Create or update section
        section_exists = section_id in _sections_store
        _sections_store[section_id] = {
            "id": section_id,
            **data
        }
        
        status_code = 200 if section_exists else 201
        return jsonify({
            "success": True,
            "section": _sections_store[section_id]
        }), status_code
    
    elif request.method == "DELETE":
        if section_id in _sections_store:
            del _sections_store[section_id]
            return jsonify({
                "success": True,
                "message": f"Section {section_id} deleted"
            }), 200
        else:
            return jsonify({
                "error": "Not Found",
                "message": f"Section {section_id} not found"
            }), 404


# Error handlers
@api_v1_bp.errorhandler(404)
def api_v1_not_found(error) -> Tuple[Dict[str, Any], int]:
    """Handle 404 errors for API v1."""
    return jsonify({
        "error": "Not Found",
        "message": "Resource not found"
    }), 404


@api_v1_bp.errorhandler(405)
def api_v1_method_not_allowed(error) -> Tuple[Dict[str, Any], int]:
    """Handle 405 errors for API v1."""
    return jsonify({
        "error": "Method Not Allowed",
        "message": "The method is not allowed for this endpoint"
    }), 405


@api_v1_bp.errorhandler(500)
def api_v1_internal_error(error) -> Tuple[Dict[str, Any], int]:
    """Handle 500 errors for API v1."""
    return jsonify({
        "error": "Internal Server Error",
        "message": "An unexpected error occurred"
    }), 500
