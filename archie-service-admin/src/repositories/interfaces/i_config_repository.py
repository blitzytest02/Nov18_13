"""
Configuration Repository Interface.

This module defines the abstract interface for application configuration access,
enabling dependency injection and testability by replacing direct usage of
consts.py throughout the Figma integration feature.

The interface pattern allows:
- Testing with fake implementations using different configuration values
- Runtime configuration changes without modifying constants
- Isolation of configuration sources (environment variables, config files, etc.)
- Consistent configuration access patterns across services

Example Usage:
    >>> config_repo = ConfigRepository()  # Concrete implementation
    >>> if config_repo.get_bool('FIGMA_INTEGRATION_ENABLED', False):
    ...     # Figma feature is enabled
    ...     project_id = config_repo.get_project_id()
    ...     # Proceed with Figma operations
"""

from abc import ABC, abstractmethod
from typing import Any


class IConfigRepository(ABC):
    """
    Abstract repository interface for application configuration access.
    
    Provides a consistent interface for retrieving configuration values with
    type-specific accessors. Concrete implementations can source configuration
    from environment variables, configuration files, remote configuration
    services, or in-memory test data.
    
    This interface replaces direct usage of consts.py to enable:
    - Dependency injection in service layer
    - Testing with faked configuration values
    - Environment-specific configuration without code changes
    - Feature flag runtime toggling (e.g., FIGMA_INTEGRATION_ENABLED)
    
    Concrete implementations must provide all four abstract methods to ensure
    complete configuration access capabilities.
    
    Example:
        >>> class FakeConfigRepository(IConfigRepository):
        ...     def get(self, key, default=None):
        ...         return self._config.get(key, default)
        ...     # ... implement other methods
        >>> 
        >>> service = FigmaService(config_repo=FakeConfigRepository())
    """
    
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a configuration value by key with optional default.
        
        This is the generic configuration accessor that returns values of any
        type. Use the typed accessors (get_bool, get_int) when you know the
        expected type for better type safety.
        
        :param key: Configuration key to retrieve (e.g., 'FIGMA_INTEGRATION_ENABLED',
                   'GCP_PROJECT_ID', 'SECRET_MANAGER_RETRY_COUNT')
        :type key: str
        :param default: Default value to return if key is not found. Defaults to None.
        :type default: Any
        :return: Configuration value associated with the key, or default if not found.
                Can be string, boolean, integer, list, dict, or any other type
                depending on the configuration source.
        :rtype: Any
        
        Example:
            >>> config_repo.get('DATABASE_URL', 'postgresql://localhost/db')
            'postgresql://production-host/production-db'
            >>> config_repo.get('NONEXISTENT_KEY', 'fallback')
            'fallback'
        
        Note:
            For boolean and integer values, prefer get_bool() and get_int()
            respectively, as they handle type coercion and validation.
        """
        pass
    
    @abstractmethod
    def get_bool(self, key: str, default: bool = False) -> bool:
        """
        Retrieve a boolean configuration value with type coercion.
        
        This method handles various representations of boolean values commonly
        found in configuration sources:
        - String values: 'true', 'True', 'TRUE', '1', 'yes', 'Yes', 'YES' → True
        - String values: 'false', 'False', 'FALSE', '0', 'no', 'No', 'NO' → False
        - Boolean values: True, False (passed through)
        - Integer values: 1 → True, 0 → False
        
        :param key: Configuration key to retrieve (e.g., 'FIGMA_INTEGRATION_ENABLED',
                   'DEBUG_MODE', 'ENABLE_LOGGING')
        :type key: str
        :param default: Default boolean value if key is not found. Defaults to False.
        :type default: bool
        :return: Boolean configuration value, coerced from various representations.
        :rtype: bool
        
        Example:
            >>> config_repo.get_bool('FIGMA_INTEGRATION_ENABLED', False)
            True
            >>> config_repo.get_bool('FEATURE_NOT_CONFIGURED', True)
            True  # Returns default since key doesn't exist
        
        Note:
            This is the primary method for checking feature flags like
            FIGMA_INTEGRATION_ENABLED throughout the Figma integration feature.
            All route handlers should use this to respect the feature flag.
        """
        pass
    
    @abstractmethod
    def get_int(self, key: str, default: int = 0) -> int:
        """
        Retrieve an integer configuration value with type coercion.
        
        This method handles conversion from string representations to integers,
        which is common when reading from environment variables or text-based
        configuration files.
        
        :param key: Configuration key to retrieve (e.g., 'SECRET_MANAGER_RETRY_COUNT',
                   'MAX_ATTACHMENT_SIZE', 'API_TIMEOUT_SECONDS')
        :type key: str
        :param default: Default integer value if key is not found. Defaults to 0.
        :type default: int
        :return: Integer configuration value, coerced from string if necessary.
        :rtype: int
        :raises ValueError: If the configuration value cannot be converted to integer
                           (implementation-specific behavior)
        
        Example:
            >>> config_repo.get_int('SECRET_MANAGER_RETRY_COUNT', 3)
            5
            >>> config_repo.get_int('UNDEFINED_SETTING', 10)
            10  # Returns default since key doesn't exist
        
        Note:
            Useful for configurable limits, timeouts, and retry counts throughout
            the Figma integration implementation.
        """
        pass
    
    @abstractmethod
    def get_project_id(self) -> str:
        """
        Retrieve the GCP project ID for Google Cloud operations.
        
        This is a convenience method specifically for accessing the GCP project ID,
        which is required for Google Secret Manager operations throughout the
        Figma integration feature. The project ID is used to construct resource
        paths for secrets (e.g., 'projects/{project_id}/secrets/figma-secret-123').
        
        The implementation should retrieve the project ID from the appropriate
        configuration source (environment variable, metadata service, config file).
        
        :return: GCP project ID string. Must not be empty.
        :rtype: str
        :raises ValueError: If project ID is not configured or is empty
                           (implementation-specific behavior)
        
        Example:
            >>> config_repo.get_project_id()
            'blitzy-production-project'
        
        Warning:
            Per section 0.4 research findings: "A common error is using the project
            NAME and not the project ID". Implementations must ensure they return
            the project ID (unique identifier), not the project display name.
        
        Note:
            This project ID is used by SecretRepository for all Google Secret Manager
            operations including creating, retrieving, updating, and deleting Figma
            Personal Access Token secrets with the naming pattern 'figma-secret-<id>'.
        """
        pass
