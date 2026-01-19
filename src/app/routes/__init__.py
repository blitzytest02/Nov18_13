"""
Routes package for the Flask application.

This module exports the blueprints for API routes.
"""

from src.app.routes.api import health_bp, api_bp, api_v1_bp

__all__ = ["health_bp", "api_bp", "api_v1_bp"]
