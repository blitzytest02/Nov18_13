"""
Unit tests for configuration module.

Tests cover:
- Configuration class defaults
- Environment-specific configurations
- Configuration loading from environment variables
- Configuration validation
"""

import os
import pytest

from src.app.config import (
    Config,
    DevelopmentConfig,
    TestingConfig,
    ProductionConfig,
    config_by_name,
    get_config,
    load_config,
)


@pytest.mark.unit
class TestBaseConfig:
    """Tests for base Config class."""
    
    def test_default_debug_is_false(self):
        """Test that DEBUG defaults to False."""
        assert Config.DEBUG is False
    
    def test_default_testing_is_false(self):
        """Test that TESTING defaults to False."""
        assert Config.TESTING is False
    
    def test_default_env_is_production(self):
        """Test that ENV defaults to production."""
        assert Config.ENV == "production"
    
    def test_default_json_sort_keys(self):
        """Test that JSON_SORT_KEYS defaults to False."""
        assert Config.JSON_SORT_KEYS is False
    
    def test_default_max_content_length(self):
        """Test that MAX_CONTENT_LENGTH is 16 MB."""
        assert Config.MAX_CONTENT_LENGTH == 16 * 1024 * 1024
    
    def test_llm_temperature_default(self):
        """Test LLM temperature default."""
        assert Config.LLM_TEMPERATURE == 0.7
    
    def test_llm_max_tokens_default(self):
        """Test LLM max tokens default."""
        assert Config.LLM_MAX_TOKENS == 4096
    
    def test_request_timeout_default(self):
        """Test request timeout default."""
        assert Config.REQUEST_TIMEOUT == 30
    
    def test_retry_max_attempts_default(self):
        """Test retry max attempts default."""
        assert Config.RETRY_MAX_ATTEMPTS == 3
    
    def test_retry_backoff_factor_default(self):
        """Test retry backoff factor default."""
        assert Config.RETRY_BACKOFF_FACTOR == 2.0


@pytest.mark.unit
class TestDevelopmentConfig:
    """Tests for DevelopmentConfig class."""
    
    def test_debug_is_true(self):
        """Test that DEBUG is True in development."""
        assert DevelopmentConfig.DEBUG is True
    
    def test_env_is_development(self):
        """Test that ENV is development."""
        assert DevelopmentConfig.ENV == "development"
    
    def test_inherits_from_config(self):
        """Test that DevelopmentConfig inherits from Config."""
        assert issubclass(DevelopmentConfig, Config)


@pytest.mark.unit
class TestTestingConfig:
    """Tests for TestingConfig class."""
    
    def test_testing_is_true(self):
        """Test that TESTING is True in testing."""
        assert TestingConfig.TESTING is True
    
    def test_debug_is_true(self):
        """Test that DEBUG is True in testing."""
        assert TestingConfig.DEBUG is True
    
    def test_env_is_testing(self):
        """Test that ENV is testing."""
        assert TestingConfig.ENV == "testing"
    
    def test_secret_key_is_set(self):
        """Test that SECRET_KEY is set for testing."""
        assert TestingConfig.SECRET_KEY == "test-secret-key"
    
    def test_gcs_bucket_name(self):
        """Test GCS bucket name for testing."""
        assert TestingConfig.GCS_BUCKET_NAME == "test-bucket"
    
    def test_pubsub_topic_name(self):
        """Test Pub/Sub topic name for testing."""
        assert TestingConfig.PUBSUB_TOPIC_NAME == "test-topic"
    
    def test_request_timeout_reduced(self):
        """Test that request timeout is reduced for testing."""
        assert TestingConfig.REQUEST_TIMEOUT == 5
    
    def test_retry_max_attempts_reduced(self):
        """Test that retry attempts are reduced for testing."""
        assert TestingConfig.RETRY_MAX_ATTEMPTS == 1


@pytest.mark.unit
class TestProductionConfig:
    """Tests for ProductionConfig class."""
    
    def test_debug_is_false(self):
        """Test that DEBUG is False in production."""
        assert ProductionConfig.DEBUG is False
    
    def test_env_is_production(self):
        """Test that ENV is production."""
        assert ProductionConfig.ENV == "production"


@pytest.mark.unit
class TestConfigByName:
    """Tests for config_by_name mapping."""
    
    def test_development_mapping(self):
        """Test development config mapping."""
        assert config_by_name["development"] == DevelopmentConfig
    
    def test_testing_mapping(self):
        """Test testing config mapping."""
        assert config_by_name["testing"] == TestingConfig
    
    def test_production_mapping(self):
        """Test production config mapping."""
        assert config_by_name["production"] == ProductionConfig
    
    def test_default_mapping(self):
        """Test default config mapping."""
        assert config_by_name["default"] == DevelopmentConfig


@pytest.mark.unit
class TestGetConfig:
    """Tests for get_config function."""
    
    def test_get_config_development(self):
        """Test getting development config."""
        config = get_config("development")
        assert config == DevelopmentConfig
    
    def test_get_config_testing(self):
        """Test getting testing config."""
        config = get_config("testing")
        assert config == TestingConfig
    
    def test_get_config_production(self):
        """Test getting production config."""
        config = get_config("production")
        assert config == ProductionConfig
    
    def test_get_config_unknown_returns_default(self):
        """Test getting unknown config returns default."""
        config = get_config("unknown")
        assert config == DevelopmentConfig
    
    def test_get_config_none_uses_env_variable(self, monkeypatch):
        """Test that None uses FLASK_ENV environment variable."""
        monkeypatch.setenv("FLASK_ENV", "testing")
        
        config = get_config(None)
        
        assert config == TestingConfig
    
    def test_get_config_no_env_defaults_to_development(self, monkeypatch):
        """Test default when FLASK_ENV is not set."""
        monkeypatch.delenv("FLASK_ENV", raising=False)
        
        config = get_config(None)
        
        assert config == DevelopmentConfig


@pytest.mark.unit
class TestConfigFromEnv:
    """Tests for Config.from_env method."""
    
    def test_from_env_loads_string_values(self, monkeypatch):
        """Test loading string values from environment."""
        monkeypatch.setenv("SECRET_KEY", "env-secret")
        
        config = Config.from_env()
        
        assert config["SECRET_KEY"] == "env-secret"
    
    def test_from_env_loads_bool_values(self, monkeypatch):
        """Test loading boolean values from environment."""
        monkeypatch.setenv("DEBUG", "true")
        
        config = Config.from_env()
        
        assert config["DEBUG"] is True
    
    def test_from_env_bool_false(self, monkeypatch):
        """Test loading False boolean from environment."""
        monkeypatch.setenv("DEBUG", "false")
        
        config = Config.from_env()
        
        assert config["DEBUG"] is False
    
    def test_from_env_loads_int_values(self, monkeypatch):
        """Test loading integer values from environment."""
        monkeypatch.setenv("MAX_CONTENT_LENGTH", "1024")
        
        config = Config.from_env()
        
        assert config["MAX_CONTENT_LENGTH"] == 1024
    
    def test_from_env_loads_float_values(self, monkeypatch):
        """Test loading float values from environment."""
        monkeypatch.setenv("LLM_TEMPERATURE", "0.5")
        
        config = Config.from_env()
        
        assert config["LLM_TEMPERATURE"] == 0.5
    
    def test_from_env_uses_defaults_when_not_set(self, monkeypatch):
        """Test that defaults are used when env vars not set."""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        
        config = Config.from_env()
        
        # Should use the class default
        assert "SECRET_KEY" in config
    
    def test_from_env_with_prefix(self, monkeypatch):
        """Test loading values with prefix."""
        monkeypatch.setenv("APP_DEBUG", "true")
        
        config = Config.from_env(prefix="APP_")
        
        assert config["DEBUG"] is True


@pytest.mark.unit
class TestConfigValidate:
    """Tests for Config.validate method."""
    
    def test_validate_success_in_non_production(self, monkeypatch):
        """Test validation passes in non-production."""
        monkeypatch.setattr(Config, "ENV", "development")
        
        assert Config.validate() is True
    
    def test_validate_fails_without_secret_in_production(self, monkeypatch):
        """Test validation fails without secret key in production."""
        monkeypatch.setattr(Config, "ENV", "production")
        monkeypatch.setattr(Config, "SECRET_KEY", "dev-secret-key-change-in-production")
        
        with pytest.raises(ValueError, match="SECRET_KEY must be set"):
            Config.validate()
    
    def test_validate_fails_with_invalid_max_content_length(self, monkeypatch):
        """Test validation fails with non-positive MAX_CONTENT_LENGTH."""
        # Set ENV to development to bypass SECRET_KEY production check
        monkeypatch.setattr(Config, "ENV", "development")
        monkeypatch.setattr(Config, "MAX_CONTENT_LENGTH", 0)
        
        with pytest.raises(ValueError, match="MAX_CONTENT_LENGTH must be positive"):
            Config.validate()
    
    def test_validate_fails_with_negative_max_content_length(self, monkeypatch):
        """Test validation fails with negative MAX_CONTENT_LENGTH."""
        # Set ENV to development to bypass SECRET_KEY production check
        monkeypatch.setattr(Config, "ENV", "development")
        monkeypatch.setattr(Config, "MAX_CONTENT_LENGTH", -1)
        
        with pytest.raises(ValueError, match="MAX_CONTENT_LENGTH must be positive"):
            Config.validate()
    
    def test_validate_fails_with_invalid_temperature_low(self, monkeypatch):
        """Test validation fails with temperature below 0."""
        # Set ENV to development to bypass SECRET_KEY production check
        monkeypatch.setattr(Config, "ENV", "development")
        monkeypatch.setattr(Config, "LLM_TEMPERATURE", -0.1)
        
        with pytest.raises(ValueError, match="LLM_TEMPERATURE must be between"):
            Config.validate()
    
    def test_validate_fails_with_invalid_temperature_high(self, monkeypatch):
        """Test validation fails with temperature above 2."""
        # Set ENV to development to bypass SECRET_KEY production check
        monkeypatch.setattr(Config, "ENV", "development")
        monkeypatch.setattr(Config, "LLM_TEMPERATURE", 2.5)
        
        with pytest.raises(ValueError, match="LLM_TEMPERATURE must be between"):
            Config.validate()
    
    def test_validate_fails_with_invalid_max_tokens(self, monkeypatch):
        """Test validation fails with non-positive max tokens."""
        # Set ENV to development to bypass SECRET_KEY production check
        monkeypatch.setattr(Config, "ENV", "development")
        monkeypatch.setattr(Config, "LLM_MAX_TOKENS", 0)
        
        with pytest.raises(ValueError, match="LLM_MAX_TOKENS must be positive"):
            Config.validate()


@pytest.mark.unit
class TestLoadConfig:
    """Tests for load_config function."""
    
    def test_load_config_applies_to_app(self, app):
        """Test that load_config applies config to app."""
        # App fixture already loads config
        assert app.config["TESTING"] is True
    
    def test_load_config_testing_env(self, app):
        """Test that testing config is applied correctly."""
        # TestingConfig should be applied
        assert app.config.get("TESTING") is True
