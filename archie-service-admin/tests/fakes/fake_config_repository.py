"""
Fake Configuration Repository for Testing.

This module provides an in-memory implementation of IConfigRepository for use in
unit tests, enabling testing of configuration-dependent behavior without requiring
environment variables, configuration files, or external configuration services.

The FakeConfigRepository allows tests to:
- Programmatically set configuration values for specific test scenarios
- Test feature flag behavior (e.g., FIGMA_INTEGRATION_ENABLED) in both states
- Verify correct handling of missing configuration keys with defaults
- Test type coercion logic for boolean and integer configuration values
- Isolate tests from actual system configuration

This fake follows the testing patterns outlined in archie-service-backend/docs/TEST.md
and supports the testing requirements from section 0.6 of the Agent Action Plan.

Example Usage in Tests:
    >>> # Setup test configuration
    >>> fake_config = FakeConfigRepository()
    >>> fake_config.set('FIGMA_INTEGRATION_ENABLED', True)
    >>> fake_config.set('GCP_PROJECT_ID', 'test-project')
    >>>
    >>> # Inject into service under test
    >>> service = FigmaService(config_repo=fake_config)
    >>>
    >>> # Test feature flag disabled scenario
    >>> fake_config.set_feature_flag('FIGMA_INTEGRATION_ENABLED', False)
    >>> # Service should now reject requests
    >>>
    >>> # Reset to defaults for next test
    >>> fake_config.reset()
"""

from typing import Any, Dict
from src.repositories.interfaces.i_config_repository import IConfigRepository


class FakeConfigRepository(IConfigRepository):
    """
    In-memory fake implementation of IConfigRepository for unit testing.

    This fake provides a dictionary-based configuration store that can be
    programmatically manipulated within tests to verify behavior under different
    configuration scenarios. It implements all IConfigRepository methods plus
    additional test helper methods for convenience.

    The fake initializes with sensible defaults for common configuration keys
    used throughout the Figma integration feature, ensuring tests work out of
    the box while still allowing override for specific test scenarios.

    Default Test Configuration:
        - FIGMA_INTEGRATION_ENABLED: True (feature enabled by default)
        - GCP_PROJECT_ID: 'test-project-id' (valid test project ID)
        - SECRET_MANAGER_RETRY_COUNT: 3 (standard retry count)
        - DEBUG_MODE: False (production-like testing by default)

    State Management:
        The fake maintains state across method calls within a test, simulating
        persistent configuration. Use reset() between tests to ensure isolation,
        or create a new instance for each test.

    Type Conversion:
        Follows the same conversion rules as production implementations:
        - get_bool: Truthy strings ('true', 'True', '1', 'yes') → True
        - get_int: Converts strings to integers, returns default on error
        - get: Returns value as-is without conversion

    Example:
        >>> fake = FakeConfigRepository()
        >>>
        >>> # Test with feature enabled (default)
        >>> assert fake.is_feature_enabled('FIGMA_INTEGRATION_ENABLED') is True
        >>>
        >>> # Test with feature disabled
        >>> fake.set_feature_flag('FIGMA_INTEGRATION_ENABLED', False)
        >>> assert fake.is_feature_enabled('FIGMA_INTEGRATION_ENABLED') is False
        >>>
        >>> # Test with custom configuration
        >>> fake.update({
        ...     'SECRET_MANAGER_RETRY_COUNT': 5,
        ...     'CUSTOM_SETTING': 'custom_value'
        ... })
        >>> assert fake.get_int('SECRET_MANAGER_RETRY_COUNT') == 5
        >>>
        >>> # Reset for next test
        >>> fake.reset()
        >>> assert fake.get_int('SECRET_MANAGER_RETRY_COUNT') == 3
    """

    def __init__(self):
        """
        Initialize fake repository with default test configuration.

        Sets up an in-memory dictionary with sensible defaults for Figma
        integration testing. Tests can override these defaults using set(),
        update(), or set_feature_flag() methods.
        """
        self._config: Dict[str, Any] = self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """
        Build default test configuration dictionary.

        This internal method defines the baseline configuration that is used
        when the fake is initialized or reset. Tests should not call this
        directly; use reset() to restore defaults.

        :return: Dictionary containing default test configuration keys and values.
        :rtype: Dict[str, Any]
        """
        return {
            'FIGMA_INTEGRATION_ENABLED': True,
            'GCP_PROJECT_ID': 'test-project-id',
            'SECRET_MANAGER_RETRY_COUNT': 3,
            'DEBUG_MODE': False,
            'MAX_ATTACHMENT_SIZE': 1048576,  # 1 MB in bytes
            'API_TIMEOUT_SECONDS': 30,
            'ENABLE_LOGGING': True,
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve configuration value by key with optional default.

        Returns the raw value from the internal configuration dictionary without
        type conversion. For boolean values, prefer get_bool() to handle various
        truthy/falsy representations. For integers, prefer get_int() to handle
        string-to-int conversion.

        :param key: Configuration key to retrieve
        :type key: str
        :param default: Value to return if key is not found. Defaults to None.
        :type default: Any
        :return: Configuration value for the key, or default if key doesn't exist
        :rtype: Any

        Example:
            >>> fake = FakeConfigRepository()
            >>> fake.get('GCP_PROJECT_ID')
            'test-project-id'
            >>> fake.get('NONEXISTENT_KEY', 'fallback')
            'fallback'
            >>> fake.set('CUSTOM_KEY', [1, 2, 3])
            >>> fake.get('CUSTOM_KEY')
            [1, 2, 3]
        """
        return self._config.get(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        """
        Retrieve boolean configuration value with type coercion.

        Handles various representations of boolean values commonly found in
        configuration sources:
        - Truthy values: True, 'true', 'True', 'TRUE', '1', 1, 'yes', 'Yes', 'YES'
        - Falsy values: False, 'false', 'False', 'FALSE', '0', 0, 'no', 'No', 'NO'
        - Any other value is treated as falsy

        This method is essential for testing feature flag behavior, particularly
        FIGMA_INTEGRATION_ENABLED flag per Feature Group A.6 requirements.

        :param key: Configuration key to retrieve
        :type key: str
        :param default: Boolean value to return if key is not found. Defaults to False.
        :type default: bool
        :return: Boolean configuration value after type coercion
        :rtype: bool

        Example:
            >>> fake = FakeConfigRepository()
            >>> fake.get_bool('FIGMA_INTEGRATION_ENABLED')
            True
            >>> fake.set('STRING_TRUE', 'true')
            >>> fake.get_bool('STRING_TRUE')
            True
            >>> fake.set('STRING_FALSE', 'false')
            >>> fake.get_bool('STRING_FALSE')
            False
            >>> fake.set('NUMERIC_TRUE', 1)
            >>> fake.get_bool('NUMERIC_TRUE')
            True
            >>> fake.get_bool('MISSING_KEY', True)
            True

        Note:
            This is the primary method used by route handlers to check the
            FIGMA_INTEGRATION_ENABLED feature flag before processing requests.
        """
        value = self._config.get(key)

        if value is None:
            return default

        # Handle boolean type directly
        if isinstance(value, bool):
            return value

        # Handle integer type (1 = True, 0 = False, other = False)
        if isinstance(value, int):
            return value == 1

        # Handle string representations
        if isinstance(value, str):
            lower_value = value.lower()
            if lower_value in ('true', '1', 'yes'):
                return True
            elif lower_value in ('false', '0', 'no'):
                return False

        # Any other value is falsy
        return False

    def get_int(self, key: str, default: int = 0) -> int:
        """
        Retrieve integer configuration value with type coercion.

        Attempts to convert the configuration value to an integer. If the value
        is already an integer, returns it directly. If it's a string, attempts
        integer conversion. If conversion fails or key doesn't exist, returns
        the default value.

        :param key: Configuration key to retrieve
        :type key: str
        :param default: Integer value to return if key is not found or conversion fails.
                       Defaults to 0.
        :type default: int
        :return: Integer configuration value after type coercion
        :rtype: int

        Example:
            >>> fake = FakeConfigRepository()
            >>> fake.get_int('SECRET_MANAGER_RETRY_COUNT')
            3
            >>> fake.set('MAX_RETRIES', '10')
            >>> fake.get_int('MAX_RETRIES')
            10
            >>> fake.set('INVALID_INT', 'not_a_number')
            >>> fake.get_int('INVALID_INT', 5)
            5
            >>> fake.get_int('MISSING_KEY', 42)
            42

        Note:
            Useful for testing retry logic, timeout configurations, and limits
            throughout the Figma integration feature implementation.
        """
        value = self._config.get(key)

        if value is None:
            return default

        # Handle integer type directly
        if isinstance(value, int):
            return value

        # Attempt string-to-int conversion
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return default

        # If value is any other type, return default
        return default

    def get_project_id(self) -> str:
        """
        Retrieve the GCP project ID for Google Cloud operations.

        Returns the test GCP project ID from configuration, which is used by
        SecretRepository for constructing resource paths when accessing Google
        Secret Manager. The default test project ID is 'test-project-id'.

        :return: GCP project ID string for testing. Never empty.
        :rtype: str

        Example:
            >>> fake = FakeConfigRepository()
            >>> fake.get_project_id()
            'test-project-id'
            >>> fake.set('GCP_PROJECT_ID', 'custom-test-project')
            >>> fake.get_project_id()
            'custom-test-project'

        Warning:
            Per Agent Action Plan section 0.4 research findings, this returns
            the project ID (unique identifier), not a project display name.
            Tests should verify that services use this correctly when constructing
            Secret Manager resource paths like 'projects/{project_id}/secrets/...'.

        Note:
            This project ID is used by FakeSecretRepository (or real SecretRepository
            in integration tests) for all Google Secret Manager operations including
            creating, retrieving, updating, and deleting Figma PAT secrets with the
            naming pattern 'figma-secret-<installation_id>'.
        """
        return self._config.get('GCP_PROJECT_ID', 'test-project-id')

    # Test Helper Methods

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value for test scenarios.

        This test helper method allows programmatic configuration changes within
        tests to verify behavior under different configuration states. Changes
        persist within the fake instance until reset() is called.

        :param key: Configuration key to set
        :type key: str
        :param value: Configuration value to store (any type)
        :type value: Any

        Example:
            >>> fake = FakeConfigRepository()
            >>> fake.set('CUSTOM_SETTING', 'custom_value')
            >>> fake.get('CUSTOM_SETTING')
            'custom_value'
            >>> fake.set('FIGMA_INTEGRATION_ENABLED', False)
            >>> fake.get_bool('FIGMA_INTEGRATION_ENABLED')
            False

        Note:
            For feature flags (boolean values), consider using set_feature_flag()
            for better readability in test code.
        """
        self._config[key] = value

    def set_feature_flag(self, flag_name: str, enabled: bool) -> None:
        """
        Set a feature flag value for test scenarios.

        Convenience method for setting boolean feature flags with clearer intent
        than generic set() method. Primarily used for testing FIGMA_INTEGRATION_ENABLED
        flag behavior per Feature Group A.6 requirements.

        :param flag_name: Name of the feature flag (e.g., 'FIGMA_INTEGRATION_ENABLED')
        :type flag_name: str
        :param enabled: Whether the feature should be enabled (True) or disabled (False)
        :type enabled: bool

        Example:
            >>> fake = FakeConfigRepository()
            >>>
            >>> # Test with feature enabled
            >>> fake.set_feature_flag('FIGMA_INTEGRATION_ENABLED', True)
            >>> assert fake.is_feature_enabled('FIGMA_INTEGRATION_ENABLED') is True
            >>>
            >>> # Test with feature disabled
            >>> fake.set_feature_flag('FIGMA_INTEGRATION_ENABLED', False)
            >>> assert fake.is_feature_enabled('FIGMA_INTEGRATION_ENABLED') is False

        Note:
            This is the recommended way to control feature flags in tests for better
            code readability and explicit test intent.
        """
        self._config[flag_name] = enabled

    def update(self, config_dict: Dict[str, Any]) -> None:
        """
        Bulk update configuration from a dictionary.

        This test helper method allows setting multiple configuration values at
        once, useful for complex test scenarios requiring multiple configuration
        changes. Existing keys are overwritten; new keys are added.

        :param config_dict: Dictionary of configuration key-value pairs to set
        :type config_dict: Dict[str, Any]

        Example:
            >>> fake = FakeConfigRepository()
            >>> fake.update({
            ...     'SECRET_MANAGER_RETRY_COUNT': 5,
            ...     'API_TIMEOUT_SECONDS': 60,
            ...     'CUSTOM_FEATURE_FLAG': True
            ... })
            >>> fake.get_int('SECRET_MANAGER_RETRY_COUNT')
            5
            >>> fake.get_int('API_TIMEOUT_SECONDS')
            60
            >>> fake.get_bool('CUSTOM_FEATURE_FLAG')
            True

        Note:
            This method performs a shallow update (does not merge nested dictionaries).
            Each key-value pair in config_dict replaces the existing value.
        """
        self._config.update(config_dict)

    def reset(self) -> None:
        """
        Reset configuration to default test values.

        This test helper method restores the configuration dictionary to its
        initial state with default test values. Use this between tests to ensure
        test isolation, or within a test to restore known configuration state.

        Example:
            >>> fake = FakeConfigRepository()
            >>> fake.set('CUSTOM_KEY', 'custom_value')
            >>> fake.get('CUSTOM_KEY')
            'custom_value'
            >>> fake.reset()
            >>> fake.get('CUSTOM_KEY')  # Returns None since CUSTOM_KEY not in defaults
            None
            >>> fake.get_bool('FIGMA_INTEGRATION_ENABLED')  # Default restored
            True

        Note:
            Prefer using pytest fixtures with function or method scope that create
            fresh FakeConfigRepository instances for each test, rather than resetting
            a shared instance. This provides better test isolation.
        """
        self._config = self._get_default_config()

    def get_all(self) -> Dict[str, Any]:
        """
        Retrieve all configuration key-value pairs for debugging.

        This test helper method returns a shallow copy of the entire configuration
        dictionary, useful for debugging test failures or verifying configuration
        state in test assertions.

        :return: Dictionary containing all configuration keys and values
        :rtype: Dict[str, Any]

        Example:
            >>> fake = FakeConfigRepository()
            >>> config = fake.get_all()
            >>> 'FIGMA_INTEGRATION_ENABLED' in config
            True
            >>> config['GCP_PROJECT_ID']
            'test-project-id'

        Warning:
            The returned dictionary is a shallow copy. Modifying nested mutable
            objects (lists, dicts) in the returned dictionary may affect the
            internal state. Use set(), update(), or reset() for intentional changes.
        """
        return self._config.copy()

    def is_feature_enabled(self, feature_name: str) -> bool:
        """
        Check if a feature flag is enabled.

        Convenience method for testing feature flag state with clearer intent
        than calling get_bool() directly. Returns False if the feature flag
        is not configured (conservative default).

        This method is particularly useful for testing route handlers that check
        FIGMA_INTEGRATION_ENABLED before processing requests per Feature Group A.6.

        :param feature_name: Name of the feature flag to check
        :type feature_name: str
        :return: True if feature is enabled, False otherwise
        :rtype: bool

        Example:
            >>> fake = FakeConfigRepository()
            >>> fake.is_feature_enabled('FIGMA_INTEGRATION_ENABLED')
            True
            >>> fake.set_feature_flag('FIGMA_INTEGRATION_ENABLED', False)
            >>> fake.is_feature_enabled('FIGMA_INTEGRATION_ENABLED')
            False
            >>> fake.is_feature_enabled('UNDEFINED_FEATURE')
            False

        Note:
            This is functionally equivalent to get_bool(feature_name, False) but
            provides better code readability in feature flag testing scenarios.
        """
        return self.get_bool(feature_name, default=False)

    def copy(self) -> 'FakeConfigRepository':
        """
        Create a snapshot copy of the current configuration state.

        This test helper method creates a new FakeConfigRepository instance with
        the same configuration values as the current instance. Useful for creating
        configuration variants in tests without affecting the original fake.

        :return: New FakeConfigRepository instance with copied configuration
        :rtype: FakeConfigRepository

        Example:
            >>> fake1 = FakeConfigRepository()
            >>> fake1.set('CUSTOM_KEY', 'custom_value')
            >>>
            >>> fake2 = fake1.copy()
            >>> fake2.get('CUSTOM_KEY')
            'custom_value'
            >>>
            >>> # Modifications to fake2 don't affect fake1
            >>> fake2.set('CUSTOM_KEY', 'different_value')
            >>> fake1.get('CUSTOM_KEY')
            'custom_value'
            >>> fake2.get('CUSTOM_KEY')
            'different_value'

        Note:
            This performs a shallow copy of the configuration dictionary. Nested
            mutable objects (lists, dicts) are not deep-copied, so modifications
            to nested structures may affect both instances. For Figma integration
            testing, configuration values are typically primitives (str, int, bool),
            so this limitation is not a concern.
        """
        new_fake = FakeConfigRepository()
        new_fake._config = self._config.copy()
        return new_fake
