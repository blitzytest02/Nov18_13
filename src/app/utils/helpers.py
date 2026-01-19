"""
Helper utility functions for the Flask application.

This module provides common utility functions used throughout the application
for string manipulation, data validation, and other common operations.
"""

import json
import re
import time
import uuid
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar, Union

T = TypeVar("T")


def sanitize_string(value: str, allow_newlines: bool = False) -> str:
    """
    Sanitize a string by removing or escaping potentially dangerous characters.
    
    Args:
        value: The string to sanitize
        allow_newlines: Whether to preserve newline characters
        
    Returns:
        Sanitized string
        
    Example:
        >>> sanitize_string("<script>alert('xss')</script>")
        '&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;'
    """
    if not value:
        return ""
    
    # HTML escape common dangerous characters
    replacements = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#x27;",
    }
    
    result = value
    for char, replacement in replacements.items():
        result = result.replace(char, replacement)
    
    # Optionally remove newlines
    if not allow_newlines:
        result = result.replace("\n", " ").replace("\r", "")
    
    return result


def truncate_string(
    value: str,
    max_length: int,
    suffix: str = "..."
) -> str:
    """
    Truncate a string to a maximum length with optional suffix.
    
    Args:
        value: The string to truncate
        max_length: Maximum length of the result
        suffix: Suffix to append if truncated
        
    Returns:
        Truncated string
        
    Example:
        >>> truncate_string("Hello, World!", 10)
        'Hello, ...'
    """
    if not value or max_length <= 0:
        return ""
    
    if len(value) <= max_length:
        return value
    
    suffix_len = len(suffix)
    if max_length <= suffix_len:
        return suffix[:max_length]
    
    return value[:max_length - suffix_len] + suffix


def generate_unique_id(prefix: str = "") -> str:
    """
    Generate a unique identifier string.
    
    Args:
        prefix: Optional prefix for the ID
        
    Returns:
        Unique identifier string
        
    Example:
        >>> generate_unique_id("doc")
        'doc-a1b2c3d4-e5f6-7890-abcd-ef1234567890'
    """
    unique_part = str(uuid.uuid4())
    if prefix:
        return f"{prefix}-{unique_part}"
    return unique_part


def parse_json_safely(
    json_string: str,
    default: Optional[T] = None
) -> Union[Dict[str, Any], T]:
    """
    Safely parse a JSON string with error handling.
    
    Args:
        json_string: The JSON string to parse
        default: Default value to return on parse error
        
    Returns:
        Parsed JSON object or default value
        
    Example:
        >>> parse_json_safely('{"key": "value"}')
        {'key': 'value'}
        >>> parse_json_safely('invalid', default={})
        {}
    """
    if not json_string:
        return default if default is not None else {}
    
    try:
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else {}


def merge_dicts(
    base: Dict[str, Any],
    override: Dict[str, Any],
    deep: bool = True
) -> Dict[str, Any]:
    """
    Merge two dictionaries, with override taking precedence.
    
    Args:
        base: The base dictionary
        override: The dictionary to merge in
        deep: Whether to perform deep merging for nested dicts
        
    Returns:
        Merged dictionary
        
    Example:
        >>> merge_dicts({'a': 1, 'b': 2}, {'b': 3, 'c': 4})
        {'a': 1, 'b': 3, 'c': 4}
    """
    result = dict(base)
    
    for key, value in override.items():
        if deep and key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value, deep=True)
        else:
            result[key] = value
    
    return result


def format_timestamp(
    dt: Optional[datetime] = None,
    format_string: str = "%Y-%m-%dT%H:%M:%SZ"
) -> str:
    """
    Format a datetime object as an ISO 8601 timestamp string.
    
    Args:
        dt: The datetime to format (defaults to current UTC time)
        format_string: The strftime format string
        
    Returns:
        Formatted timestamp string
        
    Example:
        >>> format_timestamp(datetime(2024, 1, 1, 12, 0, 0))
        '2024-01-01T12:00:00Z'
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    
    return dt.strftime(format_string)


def validate_email(email: str) -> bool:
    """
    Validate an email address format.
    
    Args:
        email: The email address to validate
        
    Returns:
        True if valid, False otherwise
        
    Example:
        >>> validate_email("user@example.com")
        True
        >>> validate_email("invalid-email")
        False
    """
    if not email or not isinstance(email, str):
        return False
    
    # Basic email regex pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def retry_with_backoff(
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    initial_delay: float = 1.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """
    Decorator factory for retrying functions with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        backoff_factor: Factor to multiply delay by after each attempt
        initial_delay: Initial delay in seconds
        exceptions: Tuple of exceptions to catch and retry on
        
    Returns:
        Decorator function
        
    Example:
        >>> @retry_with_backoff(max_attempts=3)
        ... def unstable_function():
        ...     pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(delay)
                        delay *= backoff_factor
            
            # Re-raise the last exception if all attempts failed
            if last_exception is not None:
                raise last_exception
        
        return wrapper
    return decorator


def chunk_list(items: list, chunk_size: int) -> list:
    """
    Split a list into chunks of specified size.
    
    Args:
        items: The list to chunk
        chunk_size: Size of each chunk
        
    Returns:
        List of chunks
        
    Example:
        >>> chunk_list([1, 2, 3, 4, 5], 2)
        [[1, 2], [3, 4], [5]]
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def flatten_dict(
    d: Dict[str, Any],
    parent_key: str = "",
    separator: str = "."
) -> Dict[str, Any]:
    """
    Flatten a nested dictionary into a single-level dictionary.
    
    Args:
        d: The dictionary to flatten
        parent_key: Prefix for keys (used in recursion)
        separator: Separator between nested keys
        
    Returns:
        Flattened dictionary
        
    Example:
        >>> flatten_dict({'a': {'b': 1, 'c': 2}})
        {'a.b': 1, 'a.c': 2}
    """
    items = []
    
    for key, value in d.items():
        new_key = f"{parent_key}{separator}{key}" if parent_key else key
        
        if isinstance(value, dict):
            items.extend(flatten_dict(value, new_key, separator).items())
        else:
            items.append((new_key, value))
    
    return dict(items)


def safe_get(
    d: Dict[str, Any],
    *keys: str,
    default: Optional[T] = None
) -> Union[Any, T]:
    """
    Safely get a nested value from a dictionary.
    
    Args:
        d: The dictionary to search
        *keys: The sequence of keys to follow
        default: Default value if path doesn't exist
        
    Returns:
        The value at the path or default
        
    Example:
        >>> safe_get({'a': {'b': {'c': 1}}}, 'a', 'b', 'c')
        1
        >>> safe_get({'a': 1}, 'a', 'b', default='not found')
        'not found'
    """
    result = d
    
    for key in keys:
        if isinstance(result, dict) and key in result:
            result = result[key]
        else:
            return default
    
    return result
