"""
Unit tests for the request middleware module.

Tests cover:
- RequestMiddleware class
- before_request_handler function
- after_request_handler function
- register_middleware function
- Decorators (require_json, validate_request_size, rate_limit)
"""

import pytest
import time
from unittest.mock import MagicMock, patch
from flask import Flask, g


class TestRequestMiddlewareClass:
    """Tests for RequestMiddleware class."""
    
    def test_init_without_app(self):
        """Test RequestMiddleware can be created without app."""
        from src.app.middleware.request_middleware import RequestMiddleware
        
        middleware = RequestMiddleware()
        
        assert middleware.app is None
        assert middleware.logger is None
    
    def test_init_with_app(self):
        """Test RequestMiddleware initializes with app."""
        from src.app.middleware.request_middleware import RequestMiddleware
        
        app = Flask(__name__)
        middleware = RequestMiddleware(app=app)
        
        assert middleware.app is app
        # Verify hooks were registered
        assert len(app.before_request_funcs.get(None, [])) > 0
        assert len(app.after_request_funcs.get(None, [])) > 0
    
    def test_init_with_logger(self):
        """Test RequestMiddleware accepts custom logger."""
        from src.app.middleware.request_middleware import RequestMiddleware
        
        mock_logger = MagicMock()
        middleware = RequestMiddleware(logger=mock_logger)
        
        assert middleware.logger is mock_logger
    
    def test_init_app(self):
        """Test init_app registers middleware."""
        from src.app.middleware.request_middleware import RequestMiddleware
        
        app = Flask(__name__)
        middleware = RequestMiddleware()
        
        before_count = len(app.before_request_funcs.get(None, []))
        after_count = len(app.after_request_funcs.get(None, []))
        
        middleware.init_app(app)
        
        assert len(app.before_request_funcs.get(None, [])) > before_count
        assert len(app.after_request_funcs.get(None, [])) > after_count
    
    def test_before_request_generates_request_id(self):
        """Test _before_request generates request ID."""
        from src.app.middleware.request_middleware import RequestMiddleware
        
        app = Flask(__name__)
        middleware = RequestMiddleware(app=app)
        
        with app.test_request_context('/test'):
            result = middleware._before_request()
            
            assert result is None
            assert hasattr(g, 'request_id')
            assert g.request_id is not None
    
    def test_before_request_uses_provided_id(self):
        """Test _before_request uses provided X-Request-ID."""
        from src.app.middleware.request_middleware import RequestMiddleware
        
        app = Flask(__name__)
        middleware = RequestMiddleware(app=app)
        
        with app.test_request_context(
            '/test',
            headers={'X-Request-ID': 'custom-id-123'}
        ):
            middleware._before_request()
            
            assert g.request_id == 'custom-id-123'
    
    def test_before_request_records_start_time(self):
        """Test _before_request records start time."""
        from src.app.middleware.request_middleware import RequestMiddleware
        
        app = Flask(__name__)
        middleware = RequestMiddleware(app=app)
        
        before = time.time()
        with app.test_request_context('/test'):
            middleware._before_request()
            
            assert hasattr(g, 'start_time')
            assert g.start_time >= before
    
    def test_before_request_logs_with_logger(self):
        """Test _before_request logs when logger provided."""
        from src.app.middleware.request_middleware import RequestMiddleware
        
        app = Flask(__name__)
        mock_logger = MagicMock()
        middleware = RequestMiddleware(app=app, logger=mock_logger)
        
        with app.test_request_context('/test', method='GET'):
            middleware._before_request()
            
            mock_logger.info.assert_called()
    
    def test_after_request_adds_request_id_header(self):
        """Test _after_request adds X-Request-ID header."""
        from src.app.middleware.request_middleware import RequestMiddleware
        
        app = Flask(__name__)
        middleware = RequestMiddleware(app=app)
        
        with app.test_request_context('/test'):
            g.request_id = 'test-request-id'
            
            response = MagicMock()
            response.headers = {}
            
            result = middleware._after_request(response)
            
            assert result.headers['X-Request-ID'] == 'test-request-id'
    
    def test_after_request_adds_duration_header(self):
        """Test _after_request adds X-Request-Duration header."""
        from src.app.middleware.request_middleware import RequestMiddleware
        
        app = Flask(__name__)
        middleware = RequestMiddleware(app=app)
        
        with app.test_request_context('/test'):
            g.request_id = 'test-id'
            g.start_time = time.time() - 0.1  # 100ms ago
            
            response = MagicMock()
            response.headers = {}
            response.status_code = 200
            
            result = middleware._after_request(response)
            
            assert 'X-Request-Duration' in result.headers
            assert 's' in result.headers['X-Request-Duration']
    
    def test_after_request_logs_with_logger(self):
        """Test _after_request logs completion when logger provided."""
        from src.app.middleware.request_middleware import RequestMiddleware
        
        app = Flask(__name__)
        mock_logger = MagicMock()
        middleware = RequestMiddleware(app=app, logger=mock_logger)
        
        with app.test_request_context('/test', method='GET'):
            g.request_id = 'test-id'
            g.start_time = time.time()
            
            response = MagicMock()
            response.headers = {}
            response.status_code = 200
            
            middleware._after_request(response)
            
            # Should log at least completion message
            assert mock_logger.info.call_count >= 1


class TestBeforeRequestHandler:
    """Tests for before_request_handler function."""
    
    def test_generates_request_id(self):
        """Test before_request_handler generates request ID."""
        from src.app.middleware.request_middleware import before_request_handler
        
        app = Flask(__name__)
        
        with app.test_request_context('/test'):
            result = before_request_handler()
            
            assert result is None
            assert hasattr(g, 'request_id')
    
    def test_uses_provided_request_id(self):
        """Test before_request_handler uses provided ID."""
        from src.app.middleware.request_middleware import before_request_handler
        
        app = Flask(__name__)
        
        with app.test_request_context(
            '/test',
            headers={'X-Request-ID': 'my-custom-id'}
        ):
            before_request_handler()
            
            assert g.request_id == 'my-custom-id'
    
    def test_records_start_time(self):
        """Test before_request_handler records start time."""
        from src.app.middleware.request_middleware import before_request_handler
        
        app = Flask(__name__)
        
        before = time.time()
        with app.test_request_context('/test'):
            before_request_handler()
            after = time.time()
            
            assert hasattr(g, 'start_time')
            assert g.start_time >= before
            assert g.start_time <= after


class TestAfterRequestHandler:
    """Tests for after_request_handler function."""
    
    def test_adds_request_id_header(self):
        """Test after_request_handler adds X-Request-ID."""
        from src.app.middleware.request_middleware import after_request_handler
        
        app = Flask(__name__)
        
        with app.test_request_context('/test'):
            g.request_id = 'handler-test-id'
            
            response = MagicMock()
            response.headers = {}
            
            result = after_request_handler(response)
            
            assert result.headers['X-Request-ID'] == 'handler-test-id'
    
    def test_adds_duration_header(self):
        """Test after_request_handler adds duration header."""
        from src.app.middleware.request_middleware import after_request_handler
        
        app = Flask(__name__)
        
        with app.test_request_context('/test'):
            g.start_time = time.time() - 0.05
            
            response = MagicMock()
            response.headers = {}
            
            result = after_request_handler(response)
            
            assert 'X-Request-Duration' in result.headers
    
    def test_handles_missing_request_id(self):
        """Test after_request_handler handles missing request_id."""
        from src.app.middleware.request_middleware import after_request_handler
        
        app = Flask(__name__)
        
        with app.test_request_context('/test'):
            # Don't set g.request_id
            
            response = MagicMock()
            response.headers = {}
            
            # Should not raise
            result = after_request_handler(response)
            
            assert 'X-Request-ID' not in result.headers
    
    def test_handles_missing_start_time(self):
        """Test after_request_handler handles missing start_time."""
        from src.app.middleware.request_middleware import after_request_handler
        
        app = Flask(__name__)
        
        with app.test_request_context('/test'):
            g.request_id = 'test-id'
            # Don't set g.start_time
            
            response = MagicMock()
            response.headers = {}
            
            # Should not raise
            result = after_request_handler(response)
            
            assert 'X-Request-Duration' not in result.headers


class TestRegisterMiddleware:
    """Tests for register_middleware function."""
    
    def test_registers_middleware(self):
        """Test register_middleware creates and registers middleware."""
        from src.app.middleware.request_middleware import register_middleware
        
        app = Flask(__name__)
        
        middleware = register_middleware(app)
        
        assert middleware is not None
        assert middleware.app is app
    
    def test_accepts_logger(self):
        """Test register_middleware accepts logger argument."""
        from src.app.middleware.request_middleware import register_middleware
        
        app = Flask(__name__)
        mock_logger = MagicMock()
        
        middleware = register_middleware(app, logger=mock_logger)
        
        assert middleware.logger is mock_logger


class TestRequireJsonDecorator:
    """Tests for require_json decorator."""
    
    def test_allows_json_request(self):
        """Test decorator allows JSON content type."""
        from src.app.middleware.request_middleware import require_json
        
        app = Flask(__name__)
        
        @require_json
        def handler():
            return {'success': True}
        
        with app.test_request_context(
            '/test',
            method='POST',
            content_type='application/json',
            json={'key': 'value'}
        ):
            result = handler()
            assert result == {'success': True}
    
    def test_rejects_non_json_request(self):
        """Test decorator rejects non-JSON content type."""
        from src.app.middleware.request_middleware import require_json
        
        app = Flask(__name__)
        
        @require_json
        def handler():
            return {'success': True}
        
        with app.test_request_context(
            '/test',
            method='POST',
            content_type='text/plain',
            data='some text'
        ):
            result, status = handler()
            assert status == 400
            assert 'error' in result


class TestValidateRequestSizeDecorator:
    """Tests for validate_request_size decorator."""
    
    def test_allows_small_request(self):
        """Test decorator allows request under size limit."""
        from src.app.middleware.request_middleware import validate_request_size
        
        app = Flask(__name__)
        
        @validate_request_size(1000)
        def handler():
            return {'success': True}
        
        with app.test_request_context(
            '/test',
            method='POST',
            content_length=100
        ):
            result = handler()
            assert result == {'success': True}
    
    def test_rejects_large_request(self):
        """Test decorator rejects request over size limit."""
        from src.app.middleware.request_middleware import validate_request_size
        
        app = Flask(__name__)
        
        @validate_request_size(100)
        def handler():
            return {'success': True}
        
        with app.test_request_context(
            '/test',
            method='POST',
            content_length=500
        ):
            result, status = handler()
            assert status == 413
            assert 'error' in result
    
    def test_allows_empty_request(self):
        """Test decorator allows request with no content length."""
        from src.app.middleware.request_middleware import validate_request_size
        
        app = Flask(__name__)
        
        @validate_request_size(100)
        def handler():
            return {'success': True}
        
        with app.test_request_context('/test', method='POST'):
            result = handler()
            assert result == {'success': True}


class TestRateLimitDecorator:
    """Tests for rate_limit decorator."""
    
    def test_passes_through(self):
        """Test rate_limit decorator passes through (placeholder)."""
        from src.app.middleware.request_middleware import rate_limit
        
        app = Flask(__name__)
        
        @rate_limit(60)
        def handler():
            return {'success': True}
        
        with app.test_request_context('/test'):
            result = handler()
            assert result == {'success': True}


class TestMiddlewareIntegration:
    """Integration tests for middleware."""
    
    def test_full_request_cycle(self):
        """Test complete request cycle with middleware."""
        from src.app.middleware.request_middleware import register_middleware
        
        app = Flask(__name__)
        
        @app.route('/test')
        def test_route():
            return {'message': 'success'}
        
        register_middleware(app)
        
        with app.test_client() as client:
            response = client.get('/test')
            
            assert response.status_code == 200
            assert 'X-Request-ID' in response.headers
    
    def test_request_id_propagation(self):
        """Test request ID is propagated to response."""
        from src.app.middleware.request_middleware import register_middleware
        
        app = Flask(__name__)
        
        @app.route('/test')
        def test_route():
            return {'request_id': g.request_id}
        
        register_middleware(app)
        
        with app.test_client() as client:
            response = client.get(
                '/test',
                headers={'X-Request-ID': 'custom-propagated-id'}
            )
            
            assert response.status_code == 200
            assert response.headers.get('X-Request-ID') == 'custom-propagated-id'
    
    def test_duration_header_present(self):
        """Test X-Request-Duration header is present."""
        from src.app.middleware.request_middleware import register_middleware
        
        app = Flask(__name__)
        
        @app.route('/test')
        def test_route():
            return {'message': 'success'}
        
        register_middleware(app)
        
        with app.test_client() as client:
            response = client.get('/test')
            
            assert 'X-Request-Duration' in response.headers
