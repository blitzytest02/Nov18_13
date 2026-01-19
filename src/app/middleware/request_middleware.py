"""
Request middleware for the Flask application.

This module provides middleware components for processing requests and
responses, including logging, timing, and validation.
"""

import logging
import time
import uuid
from functools import wraps
from typing import Any, Callable, Optional

from flask import Flask, Request, Response, g, request

# Module-level logger
logger = logging.getLogger(__name__)


class RequestMiddleware:
    """
    Middleware class for request/response processing.
    
    This middleware handles:
    - Request ID generation and propagation
    - Request timing and logging
    - Response header injection
    
    Attributes:
        app: The Flask application instance
        logger: Optional logger for request logging
    """

    def __init__(self, app: Optional[Flask] = None, logger: Optional[Any] = None):
        """
        Initialize the middleware.
        
        Args:
            app: Optional Flask application to register with
            logger: Optional logger instance
        """
        self.app = app
        self.logger = logger
        
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """
        Register the middleware with a Flask application.
        
        Args:
            app: Flask application instance
        """
        self.app = app
        
        # Register before request handler
        app.before_request(self._before_request)
        
        # Register after request handler
        app.after_request(self._after_request)

    def _before_request(self) -> Optional[Response]:
        """
        Handler executed before each request.
        
        Sets up request context with:
        - Request ID
        - Start time for timing
        
        Returns:
            None to continue processing, or Response to short-circuit
        """
        # Generate or extract request ID
        g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Record start time
        g.start_time = time.time()
        
        # Log request if logger available
        if self.logger:
            self.logger.info(
                f"Request started: {request.method} {request.path}",
                extra={"request_id": g.request_id}
            )
        
        return None

    def _after_request(self, response: Response) -> Response:
        """
        Handler executed after each request.
        
        Adds headers for:
        - Request ID
        - Request duration
        
        Args:
            response: The response object
            
        Returns:
            Modified response object
        """
        # Add request ID header
        if hasattr(g, "request_id"):
            response.headers["X-Request-ID"] = g.request_id
        
        # Calculate and add duration header
        if hasattr(g, "start_time"):
            duration = time.time() - g.start_time
            response.headers["X-Request-Duration"] = f"{duration:.3f}s"
            
            # Log completion if logger available
            if self.logger:
                self.logger.info(
                    f"Request completed: {request.method} {request.path} "
                    f"- {response.status_code} ({duration:.3f}s)",
                    extra={"request_id": g.request_id}
                )
        
        return response


def before_request_handler() -> Optional[Response]:
    """
    Standalone before request handler function.
    
    Can be registered directly with app.before_request().
    
    Returns:
        None to continue processing, or Response to short-circuit
    """
    # Generate or extract request ID
    g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    
    # Record start time
    g.start_time = time.time()
    
    return None


def after_request_handler(response: Response) -> Response:
    """
    Standalone after request handler function.
    
    Can be registered directly with app.after_request().
    
    Args:
        response: The response object
        
    Returns:
        Modified response object
    """
    # Add request ID header
    if hasattr(g, "request_id"):
        response.headers["X-Request-ID"] = g.request_id
    
    # Calculate and add duration header
    if hasattr(g, "start_time"):
        duration = time.time() - g.start_time
        response.headers["X-Request-Duration"] = f"{duration:.3f}s"
    
    return response


def register_middleware(app: Flask, logger: Optional[Any] = None) -> RequestMiddleware:
    """
    Convenience function to register middleware with an app.
    
    Args:
        app: Flask application instance
        logger: Optional logger instance
        
    Returns:
        The configured RequestMiddleware instance
    """
    middleware = RequestMiddleware(app=app, logger=logger)
    return middleware


def require_json(func: Callable) -> Callable:
    """
    Decorator that requires JSON content type for requests.
    
    Args:
        func: The route handler function
        
    Returns:
        Wrapped function that validates content type
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not request.is_json:
            return {"error": "Content-Type must be application/json"}, 400
        return func(*args, **kwargs)
    return wrapper


def validate_request_size(max_size: int) -> Callable:
    """
    Decorator factory that validates request content length.
    
    Args:
        max_size: Maximum allowed content length in bytes
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            content_length = request.content_length or 0
            if content_length > max_size:
                return {
                    "error": f"Request too large. Maximum size is {max_size} bytes"
                }, 413
            return func(*args, **kwargs)
        return wrapper
    return decorator


def rate_limit(requests_per_minute: int) -> Callable:
    """
    Decorator factory for rate limiting.
    
    Note: This is a placeholder implementation. In production,
    use a proper rate limiting solution with Redis or similar.
    
    Args:
        requests_per_minute: Maximum requests allowed per minute
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Placeholder - in production, implement with Redis
            # For now, just pass through
            return func(*args, **kwargs)
        return wrapper
    return decorator
