"""
Fake implementation of IConfigRepository for testing.

This module provides an in-memory fake configuration repository that enables
testing of feature flag behavior and configuration access without requiring
actual configuration files or environment variables.
"""

from typing import Any, Dict, List
from copy import deepcopy


class FakeConfigRepository:
    """
    In-memory fake implementation of IConfigRepository for testing.

    This fake provides a dictionary-based configuration store that allows tests
    to control feature flags (particularly FIGMA_INTEGRATION_ENABLED) and
    other configuration values without external dependencies. State is
    maintained across method calls within a test, and can be reset or
    reconfigured as needed.

    The fake supports type conversion, default values, and provides convenience
    methods for common testing scenarios like enabling/disabling the Figma
    integration feature flag.

    Example usage in tests:

        .. code-block:: python

            def test_feature_flag_disabled():
                '''Test endpoints reject requests when feature disabled.'''
                config = FakeConfigRepository.with_figma_disabled()
                service = FigmaService(config_repo=config)

                assert config.get_bool('FIGMA_INTEGRATION_ENABLED') is False
                # ... test that service respects the flag

            def test_custom_configuration():
                '''Test with custom configuration values.'''
                config = FakeConfigRepository.with_custom_config({
                    'FIGMA_INTEGRATION_ENABLED': True,
                    'MAX_FRAME_ATTACHMENTS': 50,
                    'API_TIMEOUT': 30
                })

                assert config.get_int('MAX_FRAME_ATTACHMENTS') == 50

    :ivar _config: Internal dictionary storing configuration key-value pairs
    """

    def __init__(self) -> None:
        """
        Initialize fake config repository with default test values.

        Default configuration includes:
        - FIGMA_INTEGRATION_ENABLED: True (feature enabled by default)
        - GCP_PROJECT_ID: 'test-project-id' (for Secret Manager testing)
        - ADMIN_SERVICE_URL: 'http://localhost:8000' (for service routing)
        """
        self._config: Dict[str, Any] = {
            'FIGMA_INTEGRATION_ENABLED': True,
            'GCP_PROJECT_ID': 'test-project-id',
            'ADMIN_SERVICE_URL': 'http://localhost:8000',
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve configuration value by key.

        Returns the value associated with the key if present, otherwise returns
        the provided default value. This is the generic accessor for any
        configuration value regardless of type.

        :param key: Configuration key (e.g., 'FIGMA_INTEGRATION_ENABLED')
        :param default: Default value to return if key not found
        :return: Configuration value or default if key not present

        Example:

            .. code-block:: python

                config = FakeConfigRepository()
                url = config.get('ADMIN_SERVICE_URL', 'http://fallback:8000')
                # Returns 'http://localhost:8000'
        """
        return self._config.get(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        """
        Retrieve boolean configuration value.

        Handles type conversion from various representations to boolean:
        - Actual bool values returned as-is
        - String 'true' (case-insensitive) converted to True
        - String 'false' (case-insensitive) converted to False
        - String '1' converted to True, '0' converted to False
        - None returns the default value
        - Other types raise ValueError

        :param key: Configuration key to retrieve
        :param default: Default boolean value if key not found
        :return: Boolean configuration value
        :raises ValueError: If value cannot be converted to boolean

        Example:

            .. code-block:: python

                config = FakeConfigRepository()
                enabled = config.get_bool('FIGMA_INTEGRATION_ENABLED')
                # Returns True

                config.set('FEATURE_X', 'true')
                feature_x = config.get_bool('FEATURE_X')
                # Returns True (string converted)
        """
        value = self._config.get(key)

        if value is None:
            return default

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            lower_value = value.lower()
            if lower_value in ('true', '1', 'yes', 'on'):
                return True
            elif lower_value in ('false', '0', 'no', 'off'):
                return False
            else:
                raise ValueError(
                    f"Cannot convert string value '{value}' to boolean "
                    f"for key '{key}'"
                )

        if isinstance(value, int):
            return bool(value)

        raise ValueError(
            f"Cannot convert value of type {type(value).__name__} "
            f"to boolean for key '{key}'"
        )

    def get_int(self, key: str, default: int = 0) -> int:
        """
        Retrieve integer configuration value.

        Handles type conversion from various representations to integer:
        - Actual int values returned as-is
        - Numeric strings converted to integers
        - None returns the default value
        - Non-numeric values raise ValueError

        :param key: Configuration key to retrieve
        :param default: Default integer value if key not found
        :return: Integer configuration value
        :raises ValueError: If value cannot be converted to integer

        Example:

            .. code-block:: python

                config = FakeConfigRepository()
                config.set('MAX_RETRIES', '3')
                retries = config.get_int('MAX_RETRIES')
                # Returns 3 (string converted to int)
        """
        value = self._config.get(key)

        if value is None:
            return default

        if isinstance(value, int):
            return value

        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                raise ValueError(
                    f"Cannot convert string value '{value}' to integer "
                    f"for key '{key}'"
                )

        if isinstance(value, float):
            return int(value)

        raise ValueError(
            f"Cannot convert value of type {type(value).__name__} "
            f"to integer for key '{key}'"
        )

    def get_project_id(self) -> str:
        """
        Retrieve GCP project ID for Secret Manager operations.

        This is a convenience method for retrieving the Google Cloud
        Platform project ID used in Secret Manager operations during
        testing. Returns a test project ID by default.

        :return: GCP project ID string

        Example:

            .. code-block:: python

                config = FakeConfigRepository()
                project_id = config.get_project_id()
                # Returns 'test-project-id'
        """
        result = self.get('GCP_PROJECT_ID', 'test-project-id')
        return str(result)

    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value for a key.

        Allows tests to dynamically modify configuration values to test
        different scenarios. This is useful for testing behavior under
        various configuration states without creating multiple repository
        instances.

        :param key: Configuration key to set
        :param value: Value to associate with the key (any type)

        Example:

            .. code-block:: python

                config = FakeConfigRepository()
                config.set('FIGMA_INTEGRATION_ENABLED', False)
                config.set('MAX_ATTACHMENTS', 100)
        """
        self._config[key] = value

    def set_bool(self, key: str, value: bool) -> None:
        """
        Set boolean configuration value.

        Type-safe convenience method for setting boolean configuration values.
        Ensures the value is actually a boolean before storing.

        :param key: Configuration key to set
        :param value: Boolean value to store
        :raises TypeError: If value is not a boolean

        Example:

            .. code-block:: python

                config = FakeConfigRepository()
                config.set_bool('FEATURE_ENABLED', True)
        """
        if not isinstance(value, bool):
            raise TypeError(f"Expected bool value, got {type(value).__name__}")
        self._config[key] = value

    def enable_figma_integration(self) -> None:
        """
        Enable Figma integration feature flag.

        Convenience method to set FIGMA_INTEGRATION_ENABLED to True. This
        is commonly used in tests that need to verify feature behavior when
        enabled.

        Example:

            .. code-block:: python

                config = FakeConfigRepository()
                config.disable_figma_integration()
                # ... test disabled behavior
                config.enable_figma_integration()
                # ... test enabled behavior
        """
        self._config['FIGMA_INTEGRATION_ENABLED'] = True

    def disable_figma_integration(self) -> None:
        """
        Disable Figma integration feature flag.

        Convenience method to set FIGMA_INTEGRATION_ENABLED to False. This is
        commonly used in tests that need to verify proper rejection of requests
        when the feature is disabled.

        Example:

            .. code-block:: python

                config = FakeConfigRepository.with_figma_enabled()
                config.disable_figma_integration()
                # Test that routes return appropriate error
        """
        self._config['FIGMA_INTEGRATION_ENABLED'] = False

    def reset(self) -> None:
        """
        Reset configuration to default test values.

        Restores the configuration dictionary to its initial state with default
        test values. Useful for ensuring clean state between test methods when
        reusing a repository instance.

        Example:

            .. code-block:: python

                config = FakeConfigRepository()
                config.set('CUSTOM_KEY', 'custom_value')
                config.reset()
                # CUSTOM_KEY no longer exists, defaults restored
        """
        self._config = {
            'FIGMA_INTEGRATION_ENABLED': True,
            'GCP_PROJECT_ID': 'test-project-id',
            'ADMIN_SERVICE_URL': 'http://localhost:8000',
        }

    def load_from_dict(self, config_dict: Dict[str, Any]) -> None:
        """
        Load configuration from dictionary.

        Bulk load multiple configuration values from a dictionary. This
        replaces the existing configuration entirely with the provided
        values.

        :param config_dict: Dictionary of configuration key-value pairs to load

        Example:

            .. code-block:: python

                config = FakeConfigRepository()
                config.load_from_dict({
                    'FIGMA_INTEGRATION_ENABLED': False,
                    'GCP_PROJECT_ID': 'prod-project',
                    'TIMEOUT_SECONDS': 60
                })
        """
        self._config = dict(config_dict)

    @classmethod
    def with_figma_enabled(cls) -> 'FakeConfigRepository':
        """
        Create instance with Figma integration enabled.

        Factory method that returns a new FakeConfigRepository instance with
        FIGMA_INTEGRATION_ENABLED set to True. This is the default state, but
        this factory method makes test intent explicit.

        :return: New FakeConfigRepository instance with Figma enabled

        Example:

            .. code-block:: python

                def test_create_installation():
                    config = FakeConfigRepository.with_figma_enabled()
                    service = FigmaService(config_repo=config)
                    # Test installation creation succeeds
        """
        instance = cls()
        instance.enable_figma_integration()
        return instance

    @classmethod
    def with_figma_disabled(cls) -> 'FakeConfigRepository':
        """
        Create instance with Figma integration disabled.

        Factory method that returns a new FakeConfigRepository instance with
        FIGMA_INTEGRATION_ENABLED set to False. Useful for testing that routes
        properly reject requests when the feature flag is disabled.

        :return: New FakeConfigRepository instance with Figma disabled

        Example:

            .. code-block:: python

                def test_feature_flag_enforcement():
                    config = FakeConfigRepository.with_figma_disabled()
                    # Test all Figma endpoints return feature disabled error
        """
        instance = cls()
        instance.disable_figma_integration()
        return instance

    @classmethod
    def with_custom_config(
        cls, config_dict: Dict[str, Any]
    ) -> 'FakeConfigRepository':
        """
        Create instance with custom configuration.

        Factory method that returns a new FakeConfigRepository instance
        initialized with the provided configuration dictionary. This is
        useful for tests that need specific configuration combinations.

        :param config_dict: Dictionary of configuration key-value pairs
        :return: New FakeConfigRepository instance with custom configuration

        Example:

            .. code-block:: python

                def test_with_custom_limits():
                    config = FakeConfigRepository.with_custom_config({
                        'FIGMA_INTEGRATION_ENABLED': True,
                        'MAX_FRAME_ATTACHMENTS': 100,
                        'SECRET_MANAGER_RETRIES': 5,
                        'GCP_PROJECT_ID': 'custom-project-123'
                    })
                    # Test with these specific configuration values
        """
        instance = cls()
        instance.load_from_dict(config_dict)
        return instance

    def get_all(self) -> Dict[str, Any]:
        """
        Get copy of all configuration values.

        Returns a deep copy of the entire configuration dictionary. The copy
        prevents external code from modifying the fake's internal state, which
        is important for maintaining test isolation and predictability.

        :return: Deep copy of configuration dictionary

        Example:

            .. code-block:: python

                config = FakeConfigRepository()
                all_config = config.get_all()
                # Inspect all values for debugging
                assert 'FIGMA_INTEGRATION_ENABLED' in all_config
        """
        return deepcopy(self._config)

    def has_key(self, key: str) -> bool:
        """
        Check if configuration key exists.

        Determines whether a specific key has been set in the configuration
        dictionary, regardless of its value. Useful for test assertions about
        configuration presence.

        :param key: Configuration key to check
        :return: True if key exists, False otherwise

        Example:

            .. code-block:: python

                config = FakeConfigRepository()
                assert config.has_key('FIGMA_INTEGRATION_ENABLED')
                assert not config.has_key('NONEXISTENT_KEY')
        """
        return key in self._config

    def keys(self) -> List[str]:
        """
        Get list of all configuration keys.

        Returns a list of all keys currently present in the configuration
        dictionary. Useful for debugging tests and verifying configuration
        state.

        :return: List of configuration key names

        Example:

            .. code-block:: python

                config = FakeConfigRepository()
                config.set('CUSTOM_KEY', 'value')
                all_keys = config.keys()
                # Returns ['FIGMA_INTEGRATION_ENABLED', 'GCP_PROJECT_ID',
                #          'ADMIN_SERVICE_URL', 'CUSTOM_KEY']
        """
        return list(self._config.keys())
