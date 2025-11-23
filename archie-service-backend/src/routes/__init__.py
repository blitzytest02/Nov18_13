"""
Routes package for archie-service-backend.

This module exports all route blueprints for registration with the Flask application.
"""

from .figma_routes import figma_bp

__all__ = ['figma_bp']
