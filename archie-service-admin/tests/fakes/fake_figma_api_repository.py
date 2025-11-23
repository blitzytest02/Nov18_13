"""
Fake Figma API Repository for Testing.

This module provides an in-memory fake implementation of IFigmaAPIRepository that
simulates Figma API operations without making actual HTTP calls. The fake supports
configurable responses, error simulation, and call tracking to enable comprehensive
testing of Figma integration business logic.

The fake repository enables deterministic testing by allowing tests to:
    - Pre-configure which PATs should be considered valid or invalid
    - Define specific responses for frame URL validation
    - Simulate API errors and edge cases
    - Track method invocations for assertion verification
    - Reset state between test cases

Usage Pattern for Testing:
    1. Create instance with initial configuration
    2. Configure test-specific responses using helper methods
    3. Inject into FigmaService during test setup
    4. Execute service methods that call Figma API
    5. Verify call tracking and assert on results
    6. Reset state for next test case

Example Test Setup:
    >>> fake_api = FakeFigmaAPIRepository()
    >>> fake_api.set_pat_valid("figd_valid_token", valid=True)
    >>> fake_api.set_pat_valid("figd_expired_token", valid=False)
    >>> fake_api.set_frame_response(
    ...     "https://www.figma.com/file/ABC/design?node-id=1:2",
    ...     valid=True,
    ...     title="Login Screen",
    ...     message=""
    ... )
    >>> service = FigmaService(figma_api_repo=fake_api)
    >>> result = service.validate_frame("https://...", installation_id=1)
    >>> assert result["valid"] is True
    >>> assert fake_api.get_call_counts()["validate_frame_access"] == 1

Design Rationale:
    The fake uses in-memory dictionaries and sets to store configuration and track
    calls, providing fast test execution without external dependencies. The design
    follows the Test Fake pattern from archie-service-backend/docs/TEST.md, where
    fakes maintain internal state across method calls to simulate stateful external
    systems realistically.

Thread Safety:
    This fake is NOT thread-safe and should only be used in single-threaded test
    environments. Each test should create its own instance or use reset() between
    test cases to ensure isolation.
"""

from copy import deepcopy
from typing import Any, Dict, List, Optional, Set, Tuple

from src.repositories.interfaces.i_figma_api_repository import IFigmaAPIRepository


class FakeFigmaAPIRepository(IFigmaAPIRepository):
    """
    In-memory fake implementation of IFigmaAPIRepository for testing.

    Provides configurable mock responses for Figma API operations including PAT
    validation, frame access validation, and metadata retrieval. Supports error
    simulation and call tracking to enable comprehensive unit testing of services
    that depend on Figma API interactions.

    The fake maintains internal state for:
        - Valid/invalid PAT sets (explicit configuration)
        - Frame-specific responses (URL -> response mapping)
        - Frame metadata (URL -> metadata mapping)
        - Default behavior configuration (all valid vs all invalid)
        - Call history for assertion verification
        - Error simulation flags for exception testing

    State Management:
        All state is stored in instance variables and can be modified through
        configuration helper methods. The reset() method clears all state to
        prepare for the next test case.

    Configuration Precedence:
        1. Explicitly configured responses (set_frame_response, set_pat_valid)
        2. Default behavior (configure_default_behavior)
        3. Fallback defaults (PATs valid, frames accessible)

    :ivar valid_pats: Set of PAT strings explicitly marked as valid
    :vartype valid_pats: Set[str]
    :ivar invalid_pats: Set of PAT strings explicitly marked as invalid
    :vartype invalid_pats: Set[str]
    :ivar frame_responses: Mapping from frame_url to validation response dict
    :vartype frame_responses: Dict[str, Dict[str, Any]]
    :ivar frame_metadata: Mapping from frame_url to metadata dict
    :vartype frame_metadata: Dict[str, Dict[str, Any]]
    :ivar default_all_valid: Default behavior for unlisted PATs
    :vartype default_all_valid: bool
    :ivar raise_on_validate_pat: If True, validate_pat raises exception
    :vartype raise_on_validate_pat: bool
    :ivar raise_on_validate_frame: If True, validate_frame_access raises exception
    :vartype raise_on_validate_frame: bool
    :ivar raise_on_get_metadata: If True, get_frame_metadata raises exception
    :vartype raise_on_get_metadata: bool
    :ivar validate_pat_calls: History of validate_pat invocations
    :vartype validate_pat_calls: List[Tuple[str]]
    :ivar validate_frame_calls: History of validate_frame_access invocations
    :vartype validate_frame_calls: List[Tuple[str, str]]
    :ivar get_frame_metadata_calls: History of get_frame_metadata invocations
    :vartype get_frame_metadata_calls: List[Tuple[str, str]]
    """

    def __init__(self):
        """
        Initialize fake repository with default configuration.

        Default State:
            - No PATs explicitly marked valid or invalid
            - No frame responses pre-configured
            - No frame metadata pre-configured
            - Default behavior: all PATs considered valid
            - No error simulation enabled
            - Empty call history

        The default configuration allows tests to pass without explicit setup,
        simulating a "happy path" scenario where all API calls succeed. Tests
        that need to verify error handling should use configuration helpers to
        enable specific failure modes.
        """
        # PAT configuration
        self.valid_pats: Set[str] = set()
        self.invalid_pats: Set[str] = set()
        self.default_all_valid: bool = True

        # Frame response configuration
        self.frame_responses: Dict[str, Dict[str, Any]] = {}
        self.frame_metadata: Dict[str, Dict[str, Any]] = {}

        # Error simulation flags
        self.raise_on_validate_pat: bool = False
        self.raise_on_validate_frame: bool = False
        self.raise_on_get_metadata: bool = False

        # Call tracking
        self.validate_pat_calls: List[Tuple[str]] = []
        self.validate_frame_calls: List[Tuple[str, str]] = []
        self.get_frame_metadata_calls: List[Tuple[str, str]] = []

    def validate_pat(self, pat: str) -> bool:
        """
        Validate Personal Access Token using configured response.

        Determines PAT validity based on configuration precedence:
            1. If PAT in invalid_pats set: return False
            2. If PAT in valid_pats set: return True
            3. Otherwise: return default_all_valid

        This method tracks all invocations in validate_pat_calls for test
        assertions and can be configured to raise exceptions for error testing.

        :param pat: Figma Personal Access Token to validate
        :type pat: str
        :return: True if PAT configured as valid, False if configured as invalid
        :rtype: bool
        :raises RuntimeError: If raise_on_validate_pat flag is True

        Example Usage in Tests:
            >>> fake = FakeFigmaAPIRepository()
            >>> fake.set_pat_valid("figd_abc123", valid=True)
            >>> fake.set_pat_valid("figd_expired", valid=False)
            >>> assert fake.validate_pat("figd_abc123") is True
            >>> assert fake.validate_pat("figd_expired") is False
            >>> assert fake.validate_pat("figd_unknown") is True  # default_all_valid
            >>> assert len(fake.validate_pat_calls) == 3

        Error Simulation:
            >>> fake = FakeFigmaAPIRepository()
            >>> fake.raise_on_validate_pat = True
            >>> try:
            ...     fake.validate_pat("any_pat")
            ... except RuntimeError as e:
            ...     assert "Simulated Figma API error" in str(e)
        """
        # Track call for assertion verification
        self.validate_pat_calls.append((pat,))

        # Simulate error if configured
        if self.raise_on_validate_pat:
            raise RuntimeError("Simulated Figma API error during PAT validation")

        # Check explicit invalid configuration first
        if pat in self.invalid_pats:
            return False

        # Check explicit valid configuration
        if pat in self.valid_pats:
            return True

        # Fall back to default behavior
        return self.default_all_valid

    def validate_frame_access(self, pat: str, frame_url: str) -> Dict[str, Any]:
        """
        Validate PAT access to frame and return configured response.

        Returns a pre-configured response for the given frame_url if one exists,
        otherwise returns a default successful response. The response always
        includes the three required keys: valid, title, and message.

        This method tracks all invocations for test verification and supports
        error simulation for testing exception handling in service layer.

        :param pat: Figma Personal Access Token for authentication
        :type pat: str
        :param frame_url: Full Figma frame URL to validate
        :type frame_url: str
        :return: Dictionary with keys 'valid' (bool), 'title' (str), 'message' (str)
        :rtype: Dict[str, Any]
        :raises RuntimeError: If raise_on_validate_frame flag is True

        Response Structure:
            Success response:
                {
                    "valid": True,
                    "title": "Frame Title from Figma",
                    "message": ""
                }

            Failure response:
                {
                    "valid": False,
                    "title": "",
                    "message": "Error description"
                }

        Example Usage in Tests:
            >>> fake = FakeFigmaAPIRepository()
            >>> frame_url = "https://www.figma.com/file/ABC/design?node-id=1:2"
            >>> fake.set_frame_response(
            ...     frame_url,
            ...     valid=False,
            ...     title="",
            ...     message="Access denied"
            ... )
            >>> result = fake.validate_frame_access("figd_pat", frame_url)
            >>> assert result["valid"] is False
            >>> assert result["message"] == "Access denied"
            >>> assert fake.validate_frame_calls[0] == ("figd_pat", frame_url)

        Default Behavior:
            If no response configured for frame_url, returns successful validation
            with mock frame title:
                {
                    "valid": True,
                    "title": "Mock Frame Title",
                    "message": ""
                }

        Error Simulation:
            >>> fake = FakeFigmaAPIRepository()
            >>> fake.raise_on_validate_frame = True
            >>> try:
            ...     fake.validate_frame_access("pat", "url")
            ... except RuntimeError as e:
            ...     assert "Simulated Figma API error" in str(e)
        """
        # Track call for assertion verification
        self.validate_frame_calls.append((pat, frame_url))

        # Simulate error if configured
        if self.raise_on_validate_frame:
            raise RuntimeError(
                "Simulated Figma API error during frame validation"
            )

        # Return configured response if available
        if frame_url in self.frame_responses:
            # Use deepcopy to prevent test code from modifying internal state
            return deepcopy(self.frame_responses[frame_url])

        # Default response: successful validation with mock title
        return {
            "valid": True,
            "title": "Mock Frame Title",
            "message": ""
        }

    def get_frame_metadata(
        self,
        pat: str,
        frame_url: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve frame metadata using configured response.

        Returns pre-configured metadata for the given frame_url if available,
        otherwise returns a default mock metadata structure. Returns None if
        configured to simulate an inaccessible frame or API error.

        This method is typically used for retrieving detailed frame information
        beyond basic validation, such as frame dimensions, type, and hierarchy.

        :param pat: Figma Personal Access Token for authentication
        :type pat: str
        :param frame_url: Full Figma frame URL to retrieve metadata for
        :type frame_url: str
        :return: Dictionary with frame metadata, or None if inaccessible
        :rtype: Optional[Dict[str, Any]]
        :raises RuntimeError: If raise_on_get_metadata flag is True

        Default Metadata Structure:
            {
                "name": "Mock Frame Title",
                "type": "FRAME",
                "node_id": "mock-node-id",
                "absoluteBoundingBox": {
                    "x": 0,
                    "y": 0,
                    "width": 375,
                    "height": 812
                }
            }

        Example Usage in Tests:
            >>> fake = FakeFigmaAPIRepository()
            >>> frame_url = "https://www.figma.com/file/ABC/design?node-id=1:2"
            >>> fake.frame_metadata[frame_url] = {
            ...     "name": "Login Screen",
            ...     "type": "COMPONENT",
            ...     "absoluteBoundingBox": {"x": 0, "y": 0, "width": 400, "height": 600}
            ... }
            >>> metadata = fake.get_frame_metadata("figd_pat", frame_url)
            >>> assert metadata["name"] == "Login Screen"
            >>> assert metadata["type"] == "COMPONENT"

        Simulating Inaccessible Frame:
            >>> fake = FakeFigmaAPIRepository()
            >>> frame_url = "https://www.figma.com/file/XYZ/design?node-id=99:99"
            >>> fake.frame_metadata[frame_url] = None
            >>> result = fake.get_frame_metadata("figd_pat", frame_url)
            >>> assert result is None

        Error Simulation:
            >>> fake = FakeFigmaAPIRepository()
            >>> fake.raise_on_get_metadata = True
            >>> try:
            ...     fake.get_frame_metadata("pat", "url")
            ... except RuntimeError as e:
            ...     assert "Simulated Figma API error" in str(e)
        """
        # Track call for assertion verification
        self.get_frame_metadata_calls.append((pat, frame_url))

        # Simulate error if configured
        if self.raise_on_get_metadata:
            raise RuntimeError(
                "Simulated Figma API error during metadata retrieval"
            )

        # Return configured metadata if available (including explicit None)
        if frame_url in self.frame_metadata:
            metadata = self.frame_metadata[frame_url]
            # Use deepcopy for dict values to prevent modification
            return deepcopy(metadata) if metadata is not None else None

        # Default metadata: successful retrieval with mock structure
        return {
            "name": "Mock Frame Title",
            "type": "FRAME",
            "node_id": "mock-node-id",
            "absoluteBoundingBox": {
                "x": 0,
                "y": 0,
                "width": 375,
                "height": 812
            }
        }

    def set_pat_valid(self, pat: str, valid: bool = True) -> None:
        """
        Configure PAT validity for testing.

        Explicitly marks a PAT as valid or invalid, overriding default behavior.
        This is the primary method for configuring PAT validation responses in
        tests that need to verify different authentication scenarios.

        :param pat: Personal Access Token to configure
        :type pat: str
        :param valid: True to mark PAT as valid, False to mark as invalid
        :type valid: bool

        Implementation Details:
            - Adds PAT to valid_pats set if valid=True
            - Adds PAT to invalid_pats set if valid=False
            - Removes PAT from opposite set to prevent conflicts
            - Idempotent: calling multiple times with same values has no effect

        Example Usage:
            >>> fake = FakeFigmaAPIRepository()
            >>> fake.set_pat_valid("figd_active_token", valid=True)
            >>> fake.set_pat_valid("figd_expired_token", valid=False)
            >>> assert fake.validate_pat("figd_active_token") is True
            >>> assert fake.validate_pat("figd_expired_token") is False

        Test Setup Pattern:
            >>> def test_pat_validation():
            ...     fake = FakeFigmaAPIRepository()
            ...     fake.set_pat_valid("test_valid", True)
            ...     fake.set_pat_valid("test_invalid", False)
            ...     service = FigmaService(figma_api_repo=fake)
            ...     # Service methods using these PATs will get configured responses
        """
        if valid:
            self.valid_pats.add(pat)
            self.invalid_pats.discard(pat)  # Remove from invalid if present
        else:
            self.invalid_pats.add(pat)
            self.valid_pats.discard(pat)  # Remove from valid if present

    def set_frame_response(
        self,
        frame_url: str,
        valid: bool,
        title: str = "",
        message: str = ""
    ) -> None:
        """
        Configure frame validation response for testing.

        Pre-configures the response that validate_frame_access will return for
        a specific frame URL. This allows tests to simulate various frame access
        scenarios including successful access, permission denial, and not found
        errors.

        :param frame_url: Figma frame URL to configure response for
        :type frame_url: str
        :param valid: True for successful access, False for denied/error
        :type valid: bool
        :param title: Frame title to return (typically empty for invalid responses)
        :type title: str
        :param message: Error message to return (typically empty for valid responses)
        :type message: str

        Response Construction:
            The method constructs a response dict with the standard structure:
                {
                    "valid": <valid parameter>,
                    "title": <title parameter>,
                    "message": <message parameter>
                }

        Example Usage Patterns:
            Successful frame access:
                >>> fake = FakeFigmaAPIRepository()
                >>> fake.set_frame_response(
                ...     "https://www.figma.com/file/ABC/design?node-id=1:2",
                ...     valid=True,
                ...     title="Dashboard Component",
                ...     message=""
                ... )

            Access denied scenario:
                >>> fake.set_frame_response(
                ...     "https://www.figma.com/file/XYZ/private?node-id=5:6",
                ...     valid=False,
                ...     title="",
                ...     message="Access denied to this file"
                ... )

            Frame not found:
                >>> fake.set_frame_response(
                ...     "https://www.figma.com/file/404/missing?node-id=9:9",
                ...     valid=False,
                ...     title="",
                ...     message="Frame not found"
                ... )

        Test Integration:
            >>> def test_frame_attachment_with_denied_access():
            ...     fake = FakeFigmaAPIRepository()
            ...     fake.set_frame_response(
            ...         "https://www.figma.com/file/XYZ/design?node-id=1:2",
            ...         valid=False,
            ...         message="Access denied"
            ...     )
            ...     service = FigmaService(figma_api_repo=fake)
            ...     result = service.validate_frame("https://...", inst_id=1)
            ...     assert result["valid"] is False
            ...     assert "Access denied" in result["message"]
        """
        self.frame_responses[frame_url] = {
            "valid": valid,
            "title": title,
            "message": message
        }

    def configure_default_behavior(self, all_valid: bool = True) -> None:
        """
        Configure default behavior for unconfigured PATs.

        Sets the default return value for validate_pat when a PAT is not
        explicitly configured in valid_pats or invalid_pats sets. This allows
        tests to easily set up "all succeed" or "all fail" baseline scenarios.

        :param all_valid: True to treat unlisted PATs as valid, False as invalid
        :type all_valid: bool

        Usage Scenarios:
            Optimistic testing (default):
                >>> fake = FakeFigmaAPIRepository()
                >>> fake.configure_default_behavior(all_valid=True)
                >>> assert fake.validate_pat("any_random_pat") is True

            Pessimistic testing:
                >>> fake = FakeFigmaAPIRepository()
                >>> fake.configure_default_behavior(all_valid=False)
                >>> assert fake.validate_pat("any_random_pat") is False
                >>> # Explicitly mark specific PATs as valid for test
                >>> fake.set_pat_valid("figd_only_valid_one", True)
                >>> assert fake.validate_pat("figd_only_valid_one") is True

        Test Pattern:
            >>> def test_all_pats_invalid_except_one():
            ...     fake = FakeFigmaAPIRepository()
            ...     fake.configure_default_behavior(all_valid=False)
            ...     fake.set_pat_valid("figd_special_token", True)
            ...     service = FigmaService(figma_api_repo=fake)
            ...     # Only figd_special_token will validate successfully
        """
        self.default_all_valid = all_valid

    def reset(self) -> None:
        """
        Reset all fake state to initial configuration.

        Clears all configuration, call tracking, and error simulation flags,
        returning the fake to its initial state as if newly constructed. This
        method should be called between test cases to ensure test isolation.

        Cleared State:
            - valid_pats and invalid_pats sets emptied
            - frame_responses and frame_metadata dicts cleared
            - All call tracking lists emptied
            - Error simulation flags reset to False
            - default_all_valid reset to True

        Usage Pattern:
            In test setup/teardown:
                >>> fake = FakeFigmaAPIRepository()  # Module or class level
                >>> def setup_test():
                ...     fake.reset()  # Ensure clean state
                ...     # Configure test-specific responses
                >>> def teardown_test():
                ...     fake.reset()  # Clean up for next test

            With pytest fixtures:
                >>> @pytest.fixture
                ... def figma_api_fake():
                ...     fake = FakeFigmaAPIRepository()
                ...     yield fake
                ...     fake.reset()  # Automatic cleanup after test

            Manual reset in test:
                >>> def test_multiple_scenarios():
                ...     fake = FakeFigmaAPIRepository()
                ...     # Scenario 1
                ...     fake.set_pat_valid("pat1", True)
                ...     assert fake.validate_pat("pat1") is True
                ...     fake.reset()
                ...     # Scenario 2 - clean slate
                ...     assert len(fake.validate_pat_calls) == 0
        """
        # Clear PAT configuration
        self.valid_pats.clear()
        self.invalid_pats.clear()
        self.default_all_valid = True

        # Clear frame configuration
        self.frame_responses.clear()
        self.frame_metadata.clear()

        # Clear error simulation flags
        self.raise_on_validate_pat = False
        self.raise_on_validate_frame = False
        self.raise_on_get_metadata = False

        # Clear call tracking
        self.validate_pat_calls.clear()
        self.validate_frame_calls.clear()
        self.get_frame_metadata_calls.clear()

    def get_call_counts(self) -> Dict[str, int]:
        """
        Get count of method invocations for test assertions.

        Returns a dictionary with counts of how many times each interface method
        was called. Useful for verifying that service layer correctly interacts
        with the Figma API repository during test execution.

        :return: Dictionary mapping method names to invocation counts
        :rtype: Dict[str, int]

        Return Structure:
            {
                "validate_pat": <count of validate_pat calls>,
                "validate_frame_access": <count of validate_frame_access calls>,
                "get_frame_metadata": <count of get_frame_metadata calls>
            }

        Example Assertions:
            >>> fake = FakeFigmaAPIRepository()
            >>> service = FigmaService(figma_api_repo=fake)
            >>> service.create_installation(user_id=1, name="test", pat="figd_abc")
            >>> counts = fake.get_call_counts()
            >>> assert counts["validate_pat"] == 1  # PAT validated during creation
            >>> assert counts["validate_frame_access"] == 0  # No frames validated

        Detailed Call History:
            For assertions about specific arguments, use the call tracking lists:
                >>> assert fake.validate_pat_calls[0] == ("figd_abc123",)
                >>> assert fake.validate_frame_calls[0] == ("figd_pat", "http://...")

        Test Pattern:
            >>> def test_service_calls_figma_api_correctly():
            ...     fake = FakeFigmaAPIRepository()
            ...     service = FigmaService(figma_api_repo=fake)
            ...     service.validate_frame("https://...", installation_id=1)
            ...     counts = fake.get_call_counts()
            ...     assert counts["validate_frame_access"] == 1
            ...     assert counts["validate_pat"] == 0  # Not called in this flow
        """
        return {
            "validate_pat": len(self.validate_pat_calls),
            "validate_frame_access": len(self.validate_frame_calls),
            "get_frame_metadata": len(self.get_frame_metadata_calls)
        }
