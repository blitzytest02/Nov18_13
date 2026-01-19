"""
Unit tests for utility helper functions.

Tests cover:
- String manipulation utilities
- JSON parsing utilities
- Dictionary utilities
- Date/time utilities
- Validation utilities
- Retry utilities
"""

import json
import time
from datetime import datetime, timezone

import pytest

from src.app.utils.helpers import (
    sanitize_string,
    truncate_string,
    generate_unique_id,
    parse_json_safely,
    merge_dicts,
    format_timestamp,
    validate_email,
    retry_with_backoff,
    chunk_list,
    flatten_dict,
    safe_get,
)


@pytest.mark.unit
class TestSanitizeString:
    """Tests for sanitize_string function."""
    
    def test_sanitize_empty_string(self):
        """Test sanitizing empty string."""
        assert sanitize_string("") == ""
    
    def test_sanitize_html_tags(self):
        """Test HTML tag escaping."""
        result = sanitize_string("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
    
    def test_sanitize_ampersand(self):
        """Test ampersand escaping."""
        result = sanitize_string("Tom & Jerry")
        assert "&amp;" in result
    
    def test_sanitize_quotes(self):
        """Test quote escaping."""
        result = sanitize_string("Say \"hello\" and 'goodbye'")
        assert "&quot;" in result
        assert "&#x27;" in result
    
    def test_sanitize_preserves_normal_text(self):
        """Test that normal text is preserved."""
        result = sanitize_string("Normal text without special chars")
        assert result == "Normal text without special chars"
    
    def test_sanitize_removes_newlines_by_default(self):
        """Test that newlines are removed by default."""
        result = sanitize_string("Line 1\nLine 2\r\nLine 3")
        assert "\n" not in result
        assert "\r" not in result
    
    def test_sanitize_preserves_newlines_when_allowed(self):
        """Test that newlines are preserved when allowed."""
        result = sanitize_string("Line 1\nLine 2", allow_newlines=True)
        assert "\n" in result


@pytest.mark.unit
class TestTruncateString:
    """Tests for truncate_string function."""
    
    def test_truncate_empty_string(self):
        """Test truncating empty string."""
        assert truncate_string("", 10) == ""
    
    def test_truncate_short_string(self):
        """Test that short strings are not truncated."""
        result = truncate_string("Short", 10)
        assert result == "Short"
    
    def test_truncate_exact_length(self):
        """Test string at exact length."""
        result = truncate_string("1234567890", 10)
        assert result == "1234567890"
    
    def test_truncate_long_string(self):
        """Test truncating long string."""
        result = truncate_string("Hello, World!", 10)
        assert len(result) == 10
        assert result.endswith("...")
    
    def test_truncate_custom_suffix(self):
        """Test truncating with custom suffix."""
        result = truncate_string("Hello, World!", 10, suffix="…")
        assert result.endswith("…")
    
    def test_truncate_zero_length(self):
        """Test truncating to zero length."""
        result = truncate_string("Hello", 0)
        assert result == ""
    
    def test_truncate_length_less_than_suffix(self):
        """Test when max length is less than suffix length."""
        result = truncate_string("Hello", 2)
        assert result == ".."


@pytest.mark.unit
class TestGenerateUniqueId:
    """Tests for generate_unique_id function."""
    
    def test_generate_unique_id_format(self):
        """Test that ID follows UUID format."""
        result = generate_unique_id()
        # Should be UUID format: 8-4-4-4-12
        parts = result.split("-")
        assert len(parts) == 5
    
    def test_generate_unique_id_with_prefix(self):
        """Test generating ID with prefix."""
        result = generate_unique_id("doc")
        assert result.startswith("doc-")
    
    def test_generate_unique_ids_are_unique(self):
        """Test that generated IDs are unique."""
        ids = [generate_unique_id() for _ in range(100)]
        assert len(set(ids)) == 100


@pytest.mark.unit
class TestParseJsonSafely:
    """Tests for parse_json_safely function."""
    
    def test_parse_valid_json(self):
        """Test parsing valid JSON."""
        result = parse_json_safely('{"key": "value"}')
        assert result == {"key": "value"}
    
    def test_parse_invalid_json_returns_default(self):
        """Test that invalid JSON returns default."""
        result = parse_json_safely("not json", default={})
        assert result == {}
    
    def test_parse_empty_string_returns_default(self):
        """Test that empty string returns default."""
        result = parse_json_safely("", default={"empty": True})
        assert result == {"empty": True}
    
    def test_parse_none_default(self):
        """Test with None as default (returns empty dict)."""
        result = parse_json_safely("invalid")
        assert result == {}
    
    def test_parse_complex_json(self):
        """Test parsing complex JSON structure."""
        json_str = '{"nested": {"array": [1, 2, 3]}, "number": 42}'
        result = parse_json_safely(json_str)
        assert result["nested"]["array"] == [1, 2, 3]
        assert result["number"] == 42


@pytest.mark.unit
class TestMergeDicts:
    """Tests for merge_dicts function."""
    
    def test_merge_simple_dicts(self):
        """Test merging simple dictionaries."""
        result = merge_dicts({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}
    
    def test_merge_override(self):
        """Test that override takes precedence."""
        result = merge_dicts({"a": 1}, {"a": 2})
        assert result["a"] == 2
    
    def test_merge_deep(self):
        """Test deep merging of nested dicts."""
        base = {"nested": {"a": 1, "b": 2}}
        override = {"nested": {"b": 3, "c": 4}}
        
        result = merge_dicts(base, override, deep=True)
        
        assert result["nested"]["a"] == 1
        assert result["nested"]["b"] == 3
        assert result["nested"]["c"] == 4
    
    def test_merge_shallow(self):
        """Test shallow merging replaces nested dicts."""
        base = {"nested": {"a": 1, "b": 2}}
        override = {"nested": {"c": 3}}
        
        result = merge_dicts(base, override, deep=False)
        
        assert result["nested"] == {"c": 3}
    
    def test_merge_preserves_original(self):
        """Test that original dicts are not modified."""
        base = {"a": 1}
        override = {"b": 2}
        
        merge_dicts(base, override)
        
        assert base == {"a": 1}
        assert override == {"b": 2}


@pytest.mark.unit
class TestFormatTimestamp:
    """Tests for format_timestamp function."""
    
    def test_format_default(self):
        """Test default ISO format."""
        dt = datetime(2024, 1, 15, 12, 30, 45)
        result = format_timestamp(dt)
        assert result == "2024-01-15T12:30:45Z"
    
    def test_format_custom(self):
        """Test custom format string."""
        dt = datetime(2024, 1, 15)
        result = format_timestamp(dt, format_string="%Y-%m-%d")
        assert result == "2024-01-15"
    
    def test_format_none_uses_current_time(self):
        """Test that None datetime uses current time."""
        result = format_timestamp(None)
        # Should be a valid timestamp string
        assert "T" in result
        assert result.endswith("Z")


@pytest.mark.unit
class TestValidateEmail:
    """Tests for validate_email function."""
    
    def test_valid_email(self):
        """Test valid email addresses."""
        assert validate_email("user@example.com") is True
        assert validate_email("user.name@domain.org") is True
        assert validate_email("user+tag@company.co.uk") is True
    
    def test_invalid_email_no_at(self):
        """Test email without @ symbol."""
        assert validate_email("invalid-email") is False
    
    def test_invalid_email_no_domain(self):
        """Test email without domain."""
        assert validate_email("user@") is False
    
    def test_invalid_email_no_tld(self):
        """Test email without TLD."""
        assert validate_email("user@domain") is False
    
    def test_empty_email(self):
        """Test empty email."""
        assert validate_email("") is False
    
    def test_none_email(self):
        """Test None email."""
        assert validate_email(None) is False
    
    def test_non_string_email(self):
        """Test non-string email."""
        assert validate_email(123) is False


@pytest.mark.unit
class TestRetryWithBackoff:
    """Tests for retry_with_backoff decorator."""
    
    def test_retry_succeeds_first_try(self):
        """Test successful execution on first try."""
        call_count = 0
        
        @retry_with_backoff(max_attempts=3)
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = successful_func()
        
        assert result == "success"
        assert call_count == 1
    
    def test_retry_on_failure(self):
        """Test retry on failure."""
        call_count = 0
        
        @retry_with_backoff(max_attempts=3, initial_delay=0.01)
        def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Not yet")
            return "success"
        
        result = failing_func()
        
        assert result == "success"
        assert call_count == 3
    
    def test_retry_exhausted_raises_error(self):
        """Test that error is raised when retries exhausted."""
        @retry_with_backoff(max_attempts=2, initial_delay=0.01)
        def always_fails():
            raise ValueError("Always fails")
        
        with pytest.raises(ValueError, match="Always fails"):
            always_fails()
    
    def test_retry_specific_exceptions(self):
        """Test retry only on specific exceptions."""
        @retry_with_backoff(
            max_attempts=3,
            initial_delay=0.01,
            exceptions=(ValueError,)
        )
        def raises_type_error():
            raise TypeError("Wrong type")
        
        with pytest.raises(TypeError):
            raises_type_error()


@pytest.mark.unit
class TestChunkList:
    """Tests for chunk_list function."""
    
    def test_chunk_list_even_split(self):
        """Test chunking that splits evenly."""
        result = chunk_list([1, 2, 3, 4, 5, 6], 2)
        assert result == [[1, 2], [3, 4], [5, 6]]
    
    def test_chunk_list_uneven_split(self):
        """Test chunking with remainder."""
        result = chunk_list([1, 2, 3, 4, 5], 2)
        assert result == [[1, 2], [3, 4], [5]]
    
    def test_chunk_list_single_chunk(self):
        """Test chunking with size larger than list."""
        result = chunk_list([1, 2, 3], 10)
        assert result == [[1, 2, 3]]
    
    def test_chunk_list_empty(self):
        """Test chunking empty list."""
        result = chunk_list([], 2)
        assert result == []
    
    def test_chunk_list_invalid_size(self):
        """Test chunking with invalid size raises error."""
        with pytest.raises(ValueError):
            chunk_list([1, 2, 3], 0)


@pytest.mark.unit
class TestFlattenDict:
    """Tests for flatten_dict function."""
    
    def test_flatten_simple_dict(self):
        """Test flattening simple dictionary."""
        result = flatten_dict({"a": 1, "b": 2})
        assert result == {"a": 1, "b": 2}
    
    def test_flatten_nested_dict(self):
        """Test flattening nested dictionary."""
        result = flatten_dict({"a": {"b": 1}})
        assert result == {"a.b": 1}
    
    def test_flatten_deeply_nested(self):
        """Test flattening deeply nested dictionary."""
        result = flatten_dict({"a": {"b": {"c": 1}}})
        assert result == {"a.b.c": 1}
    
    def test_flatten_custom_separator(self):
        """Test flattening with custom separator."""
        result = flatten_dict({"a": {"b": 1}}, separator="/")
        assert result == {"a/b": 1}
    
    def test_flatten_empty_dict(self):
        """Test flattening empty dictionary."""
        result = flatten_dict({})
        assert result == {}


@pytest.mark.unit
class TestSafeGet:
    """Tests for safe_get function."""
    
    def test_safe_get_single_key(self):
        """Test getting single key."""
        result = safe_get({"a": 1}, "a")
        assert result == 1
    
    def test_safe_get_nested_keys(self):
        """Test getting nested keys."""
        result = safe_get({"a": {"b": {"c": 1}}}, "a", "b", "c")
        assert result == 1
    
    def test_safe_get_missing_key(self):
        """Test getting missing key returns default."""
        result = safe_get({"a": 1}, "b", default="default")
        assert result == "default"
    
    def test_safe_get_missing_nested_key(self):
        """Test getting missing nested key returns default."""
        result = safe_get({"a": {"b": 1}}, "a", "c", default="default")
        assert result == "default"
    
    def test_safe_get_none_default(self):
        """Test default None is returned for missing keys."""
        result = safe_get({"a": 1}, "b")
        assert result is None
    
    def test_safe_get_non_dict_intermediate(self):
        """Test when intermediate value is not a dict."""
        result = safe_get({"a": 1}, "a", "b", default="default")
        assert result == "default"
