"""
Concrete implementation of IConfigRepository for application configuration access.

This module provides the ConfigRepository class that implements configuration access
from environment variables, with support for type coercion and sensible defaults.
This implementation replaces direct usage of consts.py for the Figma integration
feature, enabling dependency injection and testability.

Configuration Sources (in order of precedence):
    1. Environment variables (os.environ)
    2. Default values provided in method calls
    3. Hardcoded fallback defaults for critical settings

Design Rationale:
    Environment variables are the primary configuration source because:
    - They follow twelve-factor app methodology
    - They enable easy configuration changes without code modifications
    - They work seamlessly in containerized environments (Docker, Kubernetes)
    - They integrate with secrets management systems (Kubernetes secrets, etc.)
    - They support different configurations per environment (dev, staging, prod)

Common Configuration Keys:
    - FIGMA_INTEGRATION_ENABLED: Feature flag for Figma integration (boolean)
    - GCP_PROJECT_ID: Google Cloud project ID for Secret Manager (string, required)
    - SECRET_MANAGER_RETRY_COUNT: Number of retries for Secret Manager operations (int)
    - DEBUG_MODE: Enable debug logging and verbose output (boolean)
    - DATABASE_URL: Database connection string (string)
    - API_TIMEOUT_SECONDS: Timeout for external API calls (int)

Example Usage:
    >>> import os
    >>> os.environ['FIGMA_INTEGRATION_ENABLED'] = 'true'
    >>> os.environ['GCP_PROJECT_ID'] = 'my-production-project'
    >>> 
    >>> config_repo = ConfigRepository()
    >>> if config_repo.get_bool('FIGMA_INTEGRATION_ENABLED'):
    ...     project_id = config_repo.get_project_id()
    ...     print(f"Using GCP project: {project_id}")
    Using GCP project: my-production-project
"""

import os
import logging
from typing import Any

from .interfaces.i_config_repository import IConfigRepository


# Module-level logger
logger = logging.getLogger(__name__)


class ConfigRepository(IConfigRepository):
    """
    Concrete implementation of IConfigRepository using environment variables.
    
    This class provides configuration access from environment variables with
    type coercion for boolean and integer values. It follows the principle of
    "configuration as environment" from twelve-factor app methodology.
    
    Thread Safety:
        This class is thread-safe. Reading from os.environ is inherently thread-safe
        in Python, and the class maintains no mutable state.
    
    Initialization:
        No explicit initialization required. Configuration is read on-demand from
        environment variables when methods are called.
    
    Example Usage:
        >>> # Set environment variables (typically done outside Python code)
        >>> os.environ['FIGMA_INTEGRATION_ENABLED'] = 'true'
        >>> os.environ['GCP_PROJECT_ID'] = 'my-project-id'
        >>> 
        >>> # Use in application code
        >>> config_repo = ConfigRepository()
        >>> enabled = config_repo.get_bool('FIGMA_INTEGRATION_ENABLED')
        >>> project_id = config_repo.get_project_id()
        >>> 
        >>> # Inject into services
        >>> secret_repo = SecretRepository(config_repo=config_repo)
        >>> figma_service = FigmaService(config_repo=config_repo)
    
    Design Note:
        This implementation does not cache values. Each method call reads directly
        from os.environ. This allows for runtime configuration changes in development
        environments. If caching is needed for performance, implement it at a higher
        layer (e.g., application initialization caching specific values).
    """
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve configuration value from environment variable.
        
        Reads the value directly from os.environ without type conversion. For
        boolean values, prefer get_bool() to handle various truthy/falsy
        representations. For integers, prefer get_int() to handle string-to-int
        conversion.
        
        :param key: Environment variable name (e.g., 'FIGMA_INTEGRATION_ENABLED',
                   'GCP_PROJECT_ID', 'DATABASE_URL')
        :type key: str
        :param default: Value to return if environment variable is not set.
                       Defaults to None.
        :type default: Any
        :return: Environment variable value (always a string from os.environ) or
                default if not set.
        :rtype: Any
        
        Example:
            >>> os.environ['DATABASE_URL'] = 'postgresql://localhost/mydb'
            >>> config = ConfigRepository()
            >>> config.get('DATABASE_URL')
            'postgresql://localhost/mydb'
            >>> config.get('NONEXISTENT_KEY', 'fallback')
            'fallback'
            >>> del os.environ['DATABASE_URL']
            >>> config.get('DATABASE_URL', 'default_url')
            'default_url'
        
        Note:
            Environment variables are always strings in os.environ. Use get_bool()
            or get_int() for automatic type coercion.
        """
        value = os.environ.get(key)
        
        if value is None:
            return default
        
        return value
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """
        Retrieve boolean configuration value with type coercion.
        
        Handles various string representations of boolean values commonly found
        in environment variables:
        - Truthy: 'true', 'True', 'TRUE', 't', 'T', '1', 'yes', 'Yes', 'YES', 'y', 'Y'
        - Falsy: 'false', 'False', 'FALSE', 'f', 'F', '0', 'no', 'No', 'NO', 'n', 'N'
        - Empty string or unset: Returns default value
        
        This method is essential for feature flags like FIGMA_INTEGRATION_ENABLED
        per Feature Group A.6 requirements from the Agent Action Plan.
        
        :param key: Environment variable name (e.g., 'FIGMA_INTEGRATION_ENABLED',
                   'DEBUG_MODE', 'ENABLE_LOGGING')
        :type key: str
        :param default: Boolean value to return if environment variable is not set
                       or cannot be interpreted. Defaults to False.
        :type default: bool
        :return: Boolean value after type coercion
        :rtype: bool
        
        Example:
            >>> os.environ['FIGMA_INTEGRATION_ENABLED'] = 'true'
            >>> config = ConfigRepository()
            >>> config.get_bool('FIGMA_INTEGRATION_ENABLED')
            True
            >>> os.environ['FIGMA_INTEGRATION_ENABLED'] = '1'
            >>> config.get_bool('FIGMA_INTEGRATION_ENABLED')
            True
            >>> os.environ['FIGMA_INTEGRATION_ENABLED'] = 'yes'
            >>> config.get_bool('FIGMA_INTEGRATION_ENABLED')
            True
            >>> os.environ['FIGMA_INTEGRATION_ENABLED'] = 'false'
            >>> config.get_bool('FIGMA_INTEGRATION_ENABLED')
            False
            >>> os.environ['FIGMA_INTEGRATION_ENABLED'] = '0'
            >>> config.get_bool('FIGMA_INTEGRATION_ENABLED')
            False
            >>> config.get_bool('NONEXISTENT_FLAG', True)
            True
        
        Note:
            This is the primary method used by route handlers to check the
            FIGMA_INTEGRATION_ENABLED feature flag before processing requests.
            Per section A.6 of the Agent Action Plan, all Figma endpoints must
            respect this flag.
        """
        value = os.environ.get(key)
        
        if value is None:
            return default
        
        # Handle empty string as default
        if value == '':
            return default
        
        # Normalize to lowercase for comparison
        lower_value = value.lower().strip()
        
        # Define truthy values
        truthy_values = ('true', 't', '1', 'yes', 'y', 'on', 'enabled')
        
        # Define falsy values
        falsy_values = ('false', 'f', '0', 'no', 'n', 'off', 'disabled')
        
        if lower_value in truthy_values:
            return True
        elif lower_value in falsy_values:
            return False
        else:
            # If value doesn't match known patterns, log warning and return default
            logger.warning(
                f"Configuration key '{key}' has unrecognized boolean value '{value}'. "
                f"Using default: {default}"
            )
            return default
    
    def get_int(self, key: str, default: int = 0) -> int:
        """
        Retrieve integer configuration value with type coercion.
        
        Attempts to convert the environment variable value to an integer. If
        conversion fails (value is not a valid integer string), logs a warning
        and returns the default value.
        
        This method is useful for configurable limits, timeouts, and retry counts
        throughout the Figma integration feature.
        
        :param key: Environment variable name (e.g., 'SECRET_MANAGER_RETRY_COUNT',
                   'MAX_ATTACHMENT_SIZE', 'API_TIMEOUT_SECONDS')
        :type key: str
        :param default: Integer value to return if environment variable is not set
                       or cannot be converted to integer. Defaults to 0.
        :type default: int
        :return: Integer value after type coercion
        :rtype: int
        
        Example:
            >>> os.environ['SECRET_MANAGER_RETRY_COUNT'] = '5'
            >>> config = ConfigRepository()
            >>> config.get_int('SECRET_MANAGER_RETRY_COUNT')
            5
            >>> os.environ['SECRET_MANAGER_RETRY_COUNT'] = '3'
            >>> config.get_int('SECRET_MANAGER_RETRY_COUNT')
            3
            >>> config.get_int('UNDEFINED_SETTING', 10)
            10
            >>> os.environ['INVALID_INT'] = 'not_a_number'
            >>> config.get_int('INVALID_INT', 42)
            42
        
        Note:
            Used for SECRET_MANAGER_RETRY_COUNT in SecretRepository to determine
            how many times to retry transient failures when accessing Google
            Secret Manager per section 0.4 of the Agent Action Plan.
        """
        value = os.environ.get(key)
        
        if value is None:
            return default
        
        # Handle empty string as default
        if value == '':
            return default
        
        # Attempt integer conversion
        try:
            return int(value)
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Configuration key '{key}' has non-integer value '{value}'. "
                f"Using default: {default}. Error: {e}"
            )
            return default
    
    def get_project_id(self) -> str:
        """
        Retrieve GCP project ID from environment variable.
        
        This is a convenience method for accessing the GCP project ID required
        for Google Secret Manager operations. The project ID must be set in the
        GCP_PROJECT_ID environment variable.
        
        Critical Warning from Agent Action Plan section 0.4:
            "A common error is using the project NAME and not the project ID".
            Ensure the GCP_PROJECT_ID environment variable contains the project
            ID (unique identifier), not the project display name.
        
        Configuration:
            Set the environment variable:
            export GCP_PROJECT_ID=my-project-id-12345
            
            NOT:
            export GCP_PROJECT_ID="My Project Name"
        
        :return: GCP project ID string from environment variable
        :rtype: str
        :raises ValueError: If GCP_PROJECT_ID is not set or is empty
        
        Example:
            >>> os.environ['GCP_PROJECT_ID'] = 'blitzy-production-project'
            >>> config = ConfigRepository()
            >>> config.get_project_id()
            'blitzy-production-project'
            >>> del os.environ['GCP_PROJECT_ID']
            >>> config.get_project_id()
            Traceback (most recent call last):
                ...
            ValueError: GCP_PROJECT_ID environment variable is not set or is empty
        
        Note:
            This project ID is used by SecretRepository for all Google Secret Manager
            operations including creating, retrieving, updating, and deleting Figma
            Personal Access Token secrets with the naming pattern 'figma-secret-<id>'.
            
            Per section A.1.5 of the Agent Action Plan, secrets are stored with the
            pattern: projects/{project_id}/secrets/figma-secret-{installation_id}
        """
        project_id = os.environ.get('GCP_PROJECT_ID', '').strip()
        
        if not project_id:
            error_msg = (
                "GCP_PROJECT_ID environment variable is not set or is empty. "
                "This is required for Google Cloud Secret Manager operations. "
                "Set it with: export GCP_PROJECT_ID=your-project-id"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Log the project ID being used (useful for debugging environment issues)
        logger.debug(f"Using GCP project ID: {project_id}")
        
        return project_id
