"""
Configuration management for the Flask application.

This module provides configuration classes and utilities for managing
application settings across different environments (development, testing,
production).
"""

import os
from typing import Any, Dict, Optional


class Config:
    """
    Base configuration class with default settings.
    
    All configuration values can be overridden via environment variables.
    
    Attributes:
        SECRET_KEY: Secret key for session management and CSRF protection
        DEBUG: Enable/disable debug mode
        TESTING: Enable/disable testing mode
        ENV: Current environment name
        JSON_SORT_KEYS: Whether to sort JSON response keys
        MAX_CONTENT_LENGTH: Maximum allowed request content length in bytes
    """
    
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG: bool = False
    TESTING: bool = False
    ENV: str = "production"
    JSON_SORT_KEYS: bool = False
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024  # 16 MB
    
    # Cloud service configuration
    GCS_BUCKET_NAME: str = os.environ.get("GCS_BUCKET_NAME", "")
    GCS_PROJECT_ID: str = os.environ.get("GCS_PROJECT_ID", "")
    PUBSUB_PROJECT_ID: str = os.environ.get("PUBSUB_PROJECT_ID", "")
    PUBSUB_TOPIC_NAME: str = os.environ.get("PUBSUB_TOPIC_NAME", "")
    PUBSUB_SUBSCRIPTION_NAME: str = os.environ.get("PUBSUB_SUBSCRIPTION_NAME", "")
    
    # LLM configuration
    LLM_MODEL_NAME: str = os.environ.get("LLM_MODEL_NAME", "gpt-4")
    LLM_API_KEY: str = os.environ.get("LLM_API_KEY", "")
    LLM_TEMPERATURE: float = float(os.environ.get("LLM_TEMPERATURE", "0.7"))
    LLM_MAX_TOKENS: int = int(os.environ.get("LLM_MAX_TOKENS", "4096"))
    
    # Request/Response configuration
    REQUEST_TIMEOUT: int = int(os.environ.get("REQUEST_TIMEOUT", "30"))
    RETRY_MAX_ATTEMPTS: int = int(os.environ.get("RETRY_MAX_ATTEMPTS", "3"))
    RETRY_BACKOFF_FACTOR: float = float(os.environ.get("RETRY_BACKOFF_FACTOR", "2.0"))
    
    @classmethod
    def from_env(cls, prefix: str = "") -> Dict[str, Any]:
        """
        Load configuration from environment variables with optional prefix.
        
        Args:
            prefix: Optional prefix for environment variable names
            
        Returns:
            Dictionary of configuration values
        """
        config = {}
        for key in dir(cls):
            if key.isupper() and not key.startswith("_"):
                env_key = f"{prefix}{key}" if prefix else key
                env_value = os.environ.get(env_key)
                if env_value is not None:
                    # Get the default value to determine type
                    default = getattr(cls, key)
                    if isinstance(default, bool):
                        config[key] = env_value.lower() in ("true", "1", "yes")
                    elif isinstance(default, int):
                        config[key] = int(env_value)
                    elif isinstance(default, float):
                        config[key] = float(env_value)
                    else:
                        config[key] = env_value
                else:
                    config[key] = getattr(cls, key)
        return config

    @classmethod
    def validate(cls) -> bool:
        """
        Validate the configuration.
        
        Returns:
            True if configuration is valid, raises ValueError otherwise
        """
        if not cls.SECRET_KEY or cls.SECRET_KEY == "dev-secret-key-change-in-production":
            if cls.ENV == "production":
                raise ValueError("SECRET_KEY must be set in production")
        
        if cls.MAX_CONTENT_LENGTH <= 0:
            raise ValueError("MAX_CONTENT_LENGTH must be positive")
        
        if cls.LLM_TEMPERATURE < 0 or cls.LLM_TEMPERATURE > 2:
            raise ValueError("LLM_TEMPERATURE must be between 0 and 2")
        
        if cls.LLM_MAX_TOKENS <= 0:
            raise ValueError("LLM_MAX_TOKENS must be positive")
        
        return True


class DevelopmentConfig(Config):
    """Development environment configuration."""
    
    DEBUG: bool = True
    ENV: str = "development"
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-key")


class TestingConfig(Config):
    """Testing environment configuration."""
    
    TESTING: bool = True
    DEBUG: bool = True
    ENV: str = "testing"
    SECRET_KEY: str = "test-secret-key"
    
    # Use mock values for cloud services in testing
    GCS_BUCKET_NAME: str = "test-bucket"
    GCS_PROJECT_ID: str = "test-project"
    PUBSUB_PROJECT_ID: str = "test-project"
    PUBSUB_TOPIC_NAME: str = "test-topic"
    PUBSUB_SUBSCRIPTION_NAME: str = "test-subscription"
    
    # Faster timeouts for testing
    REQUEST_TIMEOUT: int = 5
    RETRY_MAX_ATTEMPTS: int = 1


class ProductionConfig(Config):
    """Production environment configuration."""
    
    DEBUG: bool = False
    ENV: str = "production"


# Configuration mapping by environment name
config_by_name: Dict[str, type] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig
}


def get_config(env_name: Optional[str] = None) -> type:
    """
    Get the configuration class for the specified environment.
    
    Args:
        env_name: Environment name (development, testing, production)
                 If None, uses FLASK_ENV environment variable
                 
    Returns:
        Configuration class for the environment
    """
    if env_name is None:
        env_name = os.environ.get("FLASK_ENV", "development")
    
    return config_by_name.get(env_name, config_by_name["default"])


def load_config(app: Any, env_name: Optional[str] = None) -> None:
    """
    Load configuration into a Flask application.
    
    Args:
        app: Flask application instance
        env_name: Optional environment name
    """
    config_class = get_config(env_name)
    app.config.from_object(config_class)
