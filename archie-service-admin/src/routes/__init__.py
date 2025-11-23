"""
Routes package for archie-service-admin.

This module exports all route blueprints for registration with the
Flask application. Each blueprint contains related endpoint handlers
following the thin controller pattern where business logic resides
in service layers.

Blueprints:
    figma_blueprint: All Figma integration endpoints (public and internal)

Usage:
    To register the Figma blueprint with your Flask application:
    
    from flask import Flask
    from src.routes import figma_blueprint
    
    app = Flask(__name__)
    
    # Register with URL prefix for public endpoints
    # Note: The blueprint contains both /v1/figma/* and /internal/figma/* routes
    # Individual routes define their full paths in decorators
    app.register_blueprint(figma_blueprint)
    
    # Alternatively, specify url_prefix if routes use relative paths:
    # app.register_blueprint(figma_blueprint, url_prefix='/v1/figma')

Architecture Notes:
    - Route handlers contain NO business logic
    - All business logic resides in service layer (src/services/)
    - Services use dependency injection with repository interfaces
    - Repositories abstract all external dependencies (DB, Secret Manager, APIs)
"""

from .figma_routes import figma_blueprint

__all__ = ['figma_blueprint']
