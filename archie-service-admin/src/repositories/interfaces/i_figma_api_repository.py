"""
Figma API Repository Interface.

This module defines the abstract interface for Figma API operations, including
Personal Access Token validation, frame URL accessibility verification, and
frame metadata retrieval. The interface abstracts external Figma API HTTP calls
to enable testing with faked responses and isolate HTTP client dependencies.

The interface supports the repository pattern implementation per requirement B.1,
allowing the service layer to interact with Figma's REST API without direct
dependency on HTTP client libraries or external API implementation details.

Authentication Pattern:
    All Figma API requests use Bearer token authentication with Personal Access
    Tokens (PATs) in the Authorization header:
        Authorization: Bearer <PAT>

Common Error Scenarios:
    - 401 Unauthorized: Invalid or expired PAT
    - 403 Forbidden: Valid PAT but lacks permission to access resource
    - 404 Not Found: Frame or file does not exist
    - 429 Too Many Requests: Rate limit exceeded
    - 500 Internal Server Error: Figma API service error
    - Network errors: Connection timeout, DNS resolution failure

Usage:
    This interface should be implemented by FigmaAPIRepository (production) and
    FakeFigmaAPIRepository (testing). Services receive the interface through
    dependency injection, enabling seamless switching between real and fake
    implementations without code changes.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class IFigmaAPIRepository(ABC):
    """
    Repository interface for Figma API operations.

    Abstracts external Figma API calls to enable testing and isolate HTTP
    client dependencies. Concrete implementations handle actual HTTP requests
    to Figma's REST API, authentication, error handling, and response parsing.

    This interface supports three primary operations:
        1. PAT validation - Verify token validity and determine Active/Expired status
        2. Frame access validation - Check if PAT can access a specific frame URL
        3. Frame metadata retrieval - Get comprehensive frame information

    Implementations must handle:
        - Bearer token authentication with PATs
        - HTTP error responses (4xx, 5xx)
        - Rate limiting and retry logic
        - Network timeouts and connection errors
        - Response parsing and validation
    """

    @abstractmethod
    def validate_pat(self, pat: str) -> bool:
        """
        Validate Personal Access Token by making a test API call to Figma.

        Makes a lightweight API request to Figma (typically GET /v1/me) to verify
        the PAT is valid and active. This method is used to compute the PAT status
        (Active/Expired) for installation records per requirement A.4.

        The validation should use a minimal API call to check token validity without
        retrieving large amounts of data. A successful response indicates the token
        is valid and has at least basic API access.

        :param pat: Figma Personal Access Token to validate
        :type pat: str
        :return: True if PAT is valid and active, False if invalid or expired
        :rtype: bool

        Example Usage:
            >>> api_repo = FigmaAPIRepository()
            >>> is_valid = api_repo.validate_pat("figd_AbC123...")
            >>> if is_valid:
            ...     print("PAT is active")
            ... else:
            ...     print("PAT is expired or invalid")

        Error Handling:
            - Returns False for 401 Unauthorized (invalid/expired token)
            - Returns False for 403 Forbidden (revoked token)
            - Returns False for network errors or timeouts
            - Returns False for any unexpected API errors
            - Should NOT raise exceptions - always returns bool

        Implementation Notes:
            - Use Figma API endpoint: GET https://api.figma.com/v1/me
            - Include header: Authorization: Bearer {pat}
            - Consider caching results with short TTL to avoid excessive API calls
            - Implement timeout (recommended: 10 seconds)
        """
        pass

    @abstractmethod
    def validate_frame_access(self, pat: str, frame_url: str) -> Dict[str, Any]:
        """
        Validate PAT has access to frame and retrieve frame metadata.

        Checks if the provided PAT can successfully access the Figma frame specified
        by frame_url. This method is essential for the frame attachment validation
        flow per requirement A.7.1.1, where frame URLs must be validated before
        being stored in the database.

        The method extracts the file key and node ID from the frame_url, makes a
        request to Figma's API to retrieve the frame/node, and returns validation
        status along with the frame title if successful.

        :param pat: Figma Personal Access Token for authentication
        :type pat: str
        :param frame_url: Full Figma frame URL to validate
                         Format: https://www.figma.com/file/{file_key}/{file_name}?node-id={node_id}
                         or: https://www.figma.com/design/{file_key}/{file_name}?node-id={node_id}
        :type frame_url: str
        :return: Dictionary with validation results containing:
                 - valid (bool): True if PAT can access frame, False otherwise
                 - title (str): Frame name/title from Figma API if valid, empty string if invalid
                 - message (str): Error message if validation failed, empty string if successful
        :rtype: Dict[str, Any]

        Example Response Structures:
            Success case:
                {
                    "valid": True,
                    "title": "Login Screen - Mobile",
                    "message": ""
                }

            Invalid PAT case:
                {
                    "valid": False,
                    "title": "",
                    "message": "Invalid or expired Personal Access Token"
                }

            Frame not found case:
                {
                    "valid": False,
                    "title": "",
                    "message": "Frame not found or you don't have access"
                }

            Malformed URL case:
                {
                    "valid": False,
                    "title": "",
                    "message": "Invalid Figma frame URL format"
                }

        Error Scenarios:
            - 401 Unauthorized: PAT is invalid or expired
                Returns: {"valid": False, "title": "", "message": "Invalid or expired PAT"}
            - 403 Forbidden: PAT valid but lacks permission to file
                Returns: {"valid": False, "title": "", "message": "Access denied to this file"}
            - 404 Not Found: File or node does not exist
                Returns: {"valid": False, "title": "", "message": "Frame not found"}
            - 429 Too Many Requests: Rate limit exceeded
                Returns: {"valid": False, "title": "",
                         "message": "Rate limit exceeded, try again later"}
            - Network errors: Timeout or connection failure
                Returns: {"valid": False, "title": "",
                         "message": "Network error connecting to Figma API"}

        Implementation Notes:
            - Parse frame_url to extract file_key and node_id
            - Use Figma API endpoint:
              GET https://api.figma.com/v1/files/{file_key}/nodes?ids={node_id}
            - Include header: Authorization: Bearer {pat}
            - Extract frame title from response:
              response['nodes'][node_id]['document']['name']
            - Implement timeout (recommended: 15 seconds for frame retrieval)
            - Consider retry logic for transient errors (3 attempts recommended)
            - Validate URL format before making API request
        """
        pass

    @abstractmethod
    def get_frame_metadata(self, pat: str, frame_url: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve comprehensive frame metadata from Figma API.

        Fetches detailed information about a Figma frame including name, type,
        dimensions, parent file information, and other properties. This method
        provides richer metadata than validate_frame_access and is useful for
        displaying frame information in the UI or for advanced integration scenarios.

        Unlike validate_frame_access, this method returns the full metadata structure
        from Figma's API rather than a standardized validation response. Returns None
        if the frame is inaccessible or if any error occurs.

        :param pat: Figma Personal Access Token for authentication
        :type pat: str
        :param frame_url: Full Figma frame URL to retrieve metadata for
                         Format: https://www.figma.com/file/{file_key}/{file_name}?node-id={node_id}
                         or: https://www.figma.com/design/{file_key}/{file_name}?node-id={node_id}
        :type frame_url: str
        :return: Dictionary containing frame metadata from Figma API, or None if inaccessible
                 Typical structure includes:
                 - name (str): Frame/node name
                 - type (str): Node type (e.g., "FRAME", "COMPONENT", "INSTANCE")
                 - absoluteBoundingBox (dict): Frame dimensions and position
                 - children (list): Child nodes if applicable
                 Other fields vary based on Figma API response
        :rtype: Optional[Dict]

        Example Response:
            {
                "name": "Login Screen - Mobile",
                "type": "FRAME",
                "absoluteBoundingBox": {
                    "x": 0,
                    "y": 0,
                    "width": 375,
                    "height": 812
                },
                "backgroundColor": {
                    "r": 1,
                    "g": 1,
                    "b": 1,
                    "a": 1
                },
                "children": [...]
            }

        Returns None for error cases:
            - Invalid or expired PAT (401)
            - Access denied (403)
            - Frame not found (404)
            - Rate limit exceeded (429)
            - Network errors or timeouts
            - Malformed frame URL

        Implementation Notes:
            - Parse frame_url to extract file_key and node_id
            - Use Figma API endpoint:
              GET https://api.figma.com/v1/files/{file_key}/nodes?ids={node_id}
            - Include header: Authorization: Bearer {pat}
            - Extract node data from response: response['nodes'][node_id]['document']
            - Return None for any error condition (don't raise exceptions)
            - Implement timeout (recommended: 15 seconds)
            - Consider caching results if called frequently for same frames

        Usage Example:
            >>> api_repo = FigmaAPIRepository()
            >>> frame_url = "https://www.figma.com/file/abc/design?node-id=1:2"
            >>> metadata = api_repo.get_frame_metadata("figd_AbC123...", frame_url)
            >>> if metadata:
            ...     print(f"Frame name: {metadata['name']}")
            ...     print(f"Frame type: {metadata['type']}")
            ... else:
            ...     print("Could not retrieve frame metadata")
        """
        pass
