"""
Flask application factory for the reverse document generator.

This module provides the application factory function and initialization
logic for the Flask web application.
"""

from typing import Any, Dict, Optional

from flask import Flask

from src.app.config import load_config, get_config
from src.app.routes.api import health_bp, api_bp, api_v1_bp
from src.app.middleware import register_middleware


def create_app(config: Optional[Dict[str, Any]] = None) -> Flask:
    """
    Create and configure the Flask application.
    
    This factory function creates a new Flask application instance with:
    - Configuration loading from environment-specific settings
    - Blueprint registration for API routes
    - Middleware registration for request/response processing
    - Error handlers setup
    
    Args:
        config: Optional dictionary of configuration overrides
        
    Returns:
        Configured Flask application instance
        
    Example:
        >>> app = create_app({"TESTING": True})
        >>> app.config["TESTING"]
        True
    """
    app = Flask(__name__)
    
    # Load default configuration
    load_config(app)
    
    # Apply configuration overrides if provided
    if config:
        app.config.update(config)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register middleware
    register_middleware(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    return app


def register_blueprints(app: Flask) -> None:
    """
    Register all blueprints with the application.
    
    Args:
        app: Flask application instance
    """
    # Register health endpoint at root level
    app.register_blueprint(health_bp)
    
    # Register API blueprints
    app.register_blueprint(api_bp)
    app.register_blueprint(api_v1_bp)


def register_error_handlers(app: Flask) -> None:
    """
    Register global error handlers with the application.
    
    Args:
        app: Flask application instance
    """
    
    @app.errorhandler(400)
    def bad_request(error: Exception) -> tuple:
        """Handle 400 Bad Request errors."""
        return {"error": "Bad Request", "message": str(error)}, 400
    
    @app.errorhandler(404)
    def not_found(error: Exception) -> tuple:
        """Handle 404 Not Found errors."""
        return {"error": "Not Found", "message": "Resource not found"}, 404
    
    @app.errorhandler(405)
    def method_not_allowed(error: Exception) -> tuple:
        """Handle 405 Method Not Allowed errors."""
        return {"error": "Method Not Allowed", "message": str(error)}, 405
    
    @app.errorhandler(500)
    def internal_server_error(error: Exception) -> tuple:
        """Handle 500 Internal Server errors."""
        return {"error": "Internal Server Error", "message": "An unexpected error occurred"}, 500


# Create a default application instance for CLI commands
app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
