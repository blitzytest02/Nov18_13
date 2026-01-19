"""
Unit tests for DocumentSection models.

Tests cover:
- Valid document section creation
- Field validation rules
- Status enum behavior
- Changes list validation based on status
- Serialization and deserialization
"""

import pytest
from pydantic import ValidationError

from src.app.models.document import DocumentSection, DocumentSectionStatus


@pytest.mark.unit
class TestDocumentSectionStatus:
    """Tests for DocumentSectionStatus enum."""
    
    def test_status_unchanged_value(self):
        """Test UNCHANGED status has correct value."""
        assert DocumentSectionStatus.UNCHANGED.value == "UNCHANGED"
    
    def test_status_changed_value(self):
        """Test CHANGED status has correct value."""
        assert DocumentSectionStatus.CHANGED.value == "CHANGED"
    
    def test_status_new_value(self):
        """Test NEW status has correct value."""
        assert DocumentSectionStatus.NEW.value == "NEW"
    
    def test_status_deleted_value(self):
        """Test DELETED status has correct value."""
        assert DocumentSectionStatus.DELETED.value == "DELETED"
    
    def test_status_pending_value(self):
        """Test PENDING status has correct value."""
        assert DocumentSectionStatus.PENDING.value == "PENDING"
    
    def test_status_from_string(self):
        """Test creating status from string value."""
        status = DocumentSectionStatus("CHANGED")
        assert status == DocumentSectionStatus.CHANGED
    
    def test_invalid_status_raises_error(self):
        """Test that invalid status string raises ValueError."""
        with pytest.raises(ValueError):
            DocumentSectionStatus("INVALID")
    
    def test_status_is_string_subclass(self):
        """Test that status values can be used as strings."""
        status = DocumentSectionStatus.UNCHANGED
        assert isinstance(status, str)
        assert status == "UNCHANGED"


@pytest.mark.unit
class TestDocumentSection:
    """Tests for DocumentSection model."""
    
    def test_document_section_valid_data(self):
        """Test creating a document section with valid data."""
        section = DocumentSection(
            heading="Test Heading",
            content="Test content",
            status=DocumentSectionStatus.UNCHANGED
        )
        assert section.heading == "Test Heading"
        assert section.content == "Test content"
        assert section.status == DocumentSectionStatus.UNCHANGED
        assert section.changes == []
    
    def test_document_section_with_all_fields(self):
        """Test creating a document section with all fields populated."""
        section = DocumentSection(
            heading="Complete Section",
            content="Full content here",
            status=DocumentSectionStatus.CHANGED,
            changes=["Change 1", "Change 2"],
            order=5
        )
        assert section.heading == "Complete Section"
        assert section.content == "Full content here"
        assert section.status == DocumentSectionStatus.CHANGED
        assert section.changes == ["Change 1", "Change 2"]
        assert section.order == 5
    
    def test_document_section_default_values(self):
        """Test that default values are set correctly."""
        section = DocumentSection(heading="Minimal")
        assert section.content == ""
        assert section.status == DocumentSectionStatus.UNCHANGED
        assert section.changes == []
        assert section.order is None
    
    def test_document_section_empty_heading_raises_error(self):
        """Test that empty heading raises validation error."""
        with pytest.raises(ValidationError):
            DocumentSection(heading="")
    
    def test_document_section_whitespace_heading_raises_error(self):
        """Test that whitespace-only heading raises validation error."""
        with pytest.raises(ValidationError):
            DocumentSection(heading="   ")
    
    def test_document_section_heading_stripped(self):
        """Test that heading is stripped of leading/trailing whitespace."""
        section = DocumentSection(heading="  Trimmed Heading  ")
        assert section.heading == "Trimmed Heading"
    
    def test_document_section_changed_without_changes_raises_error(self):
        """Test that CHANGED status without changes raises error."""
        with pytest.raises(ValueError, match="must have at least one change"):
            DocumentSection(
                heading="Test",
                status=DocumentSectionStatus.CHANGED,
                changes=[]
            )
    
    def test_document_section_changed_with_changes_succeeds(self):
        """Test that CHANGED status with changes succeeds."""
        section = DocumentSection(
            heading="Test",
            status=DocumentSectionStatus.CHANGED,
            changes=["A change"]
        )
        assert section.status == DocumentSectionStatus.CHANGED
        assert len(section.changes) == 1
    
    def test_document_section_new_status_without_changes(self):
        """Test that NEW status works without changes."""
        section = DocumentSection(
            heading="New Section",
            status=DocumentSectionStatus.NEW
        )
        assert section.status == DocumentSectionStatus.NEW
        assert section.changes == []
    
    def test_document_section_deleted_status(self):
        """Test creating a section with DELETED status."""
        section = DocumentSection(
            heading="Deleted Section",
            status=DocumentSectionStatus.DELETED
        )
        assert section.status == DocumentSectionStatus.DELETED
    
    def test_document_section_pending_status(self):
        """Test creating a section with PENDING status."""
        section = DocumentSection(
            heading="Pending Section",
            status=DocumentSectionStatus.PENDING
        )
        assert section.status == DocumentSectionStatus.PENDING


@pytest.mark.unit
class TestDocumentSectionMethods:
    """Tests for DocumentSection methods."""
    
    def test_add_change_updates_status(self):
        """Test that add_change updates status to CHANGED."""
        section = DocumentSection(heading="Test")
        assert section.status == DocumentSectionStatus.UNCHANGED
        
        section.add_change("New change")
        
        assert section.status == DocumentSectionStatus.CHANGED
        assert "New change" in section.changes
    
    def test_add_change_appends_to_list(self):
        """Test that add_change appends to existing changes."""
        section = DocumentSection(
            heading="Test",
            status=DocumentSectionStatus.CHANGED,
            changes=["Existing change"]
        )
        
        section.add_change("Another change")
        
        assert len(section.changes) == 2
        assert "Another change" in section.changes
    
    def test_add_change_strips_whitespace(self):
        """Test that add_change strips whitespace from change."""
        section = DocumentSection(heading="Test")
        section.add_change("  Trimmed change  ")
        
        assert "Trimmed change" in section.changes
    
    def test_add_change_ignores_empty_string(self):
        """Test that add_change ignores empty strings."""
        section = DocumentSection(heading="Test")
        section.add_change("")
        section.add_change("   ")
        
        assert len(section.changes) == 0
        assert section.status == DocumentSectionStatus.UNCHANGED
    
    def test_clear_changes_resets_status(self):
        """Test that clear_changes resets status to UNCHANGED."""
        section = DocumentSection(
            heading="Test",
            status=DocumentSectionStatus.CHANGED,
            changes=["Change 1", "Change 2"]
        )
        
        section.clear_changes()
        
        assert section.changes == []
        assert section.status == DocumentSectionStatus.UNCHANGED
    
    def test_to_dict_returns_all_fields(self):
        """Test that to_dict returns all fields."""
        section = DocumentSection(
            heading="Test",
            content="Content",
            status=DocumentSectionStatus.CHANGED,
            changes=["Change"],
            order=1
        )
        
        result = section.to_dict()
        
        assert result["heading"] == "Test"
        assert result["content"] == "Content"
        assert result["status"] == "CHANGED"
        assert result["changes"] == ["Change"]
        assert result["order"] == 1
    
    def test_to_dict_status_is_string(self):
        """Test that to_dict returns status as string value."""
        section = DocumentSection(heading="Test")
        result = section.to_dict()
        
        assert isinstance(result["status"], str)
        assert result["status"] == "UNCHANGED"
    
    def test_from_dict_creates_section(self):
        """Test that from_dict creates a DocumentSection."""
        data = {
            "heading": "From Dict",
            "content": "Content",
            "status": "CHANGED",
            "changes": ["Change"]
        }
        
        section = DocumentSection.from_dict(data)
        
        assert section.heading == "From Dict"
        assert section.content == "Content"
        assert section.status == DocumentSectionStatus.CHANGED
        assert section.changes == ["Change"]
    
    def test_from_dict_with_status_enum(self):
        """Test that from_dict works with status as enum."""
        data = {
            "heading": "From Dict",
            "status": DocumentSectionStatus.NEW
        }
        
        section = DocumentSection.from_dict(data)
        
        assert section.status == DocumentSectionStatus.NEW
    
    def test_roundtrip_serialization(self):
        """Test that to_dict and from_dict are inverse operations."""
        original = DocumentSection(
            heading="Original",
            content="Original content",
            status=DocumentSectionStatus.CHANGED,
            changes=["Change 1", "Change 2"],
            order=3
        )
        
        data = original.to_dict()
        restored = DocumentSection.from_dict(data)
        
        assert restored.heading == original.heading
        assert restored.content == original.content
        assert restored.status == original.status
        assert restored.changes == original.changes
        assert restored.order == original.order


@pytest.mark.unit
class TestDocumentSectionValidation:
    """Tests for DocumentSection validation edge cases."""
    
    def test_heading_minimum_length(self):
        """Test that single character heading is valid."""
        section = DocumentSection(heading="X")
        assert section.heading == "X"
    
    def test_long_heading(self):
        """Test that long heading is valid."""
        long_heading = "A" * 1000
        section = DocumentSection(heading=long_heading)
        assert len(section.heading) == 1000
    
    def test_content_with_special_characters(self):
        """Test content with special characters."""
        section = DocumentSection(
            heading="Special",
            content="Content with <html> & special chars: \"quotes\" 'single'"
        )
        assert "<html>" in section.content
        assert "&" in section.content
    
    def test_content_with_newlines(self):
        """Test content with newline characters."""
        section = DocumentSection(
            heading="Multiline",
            content="Line 1\nLine 2\nLine 3"
        )
        assert "\n" in section.content
    
    def test_changes_list_preserved_order(self):
        """Test that changes list preserves order."""
        changes = ["First", "Second", "Third"]
        section = DocumentSection(
            heading="Test",
            status=DocumentSectionStatus.CHANGED,
            changes=changes
        )
        assert section.changes == changes
    
    def test_order_accepts_zero(self):
        """Test that order can be zero."""
        section = DocumentSection(heading="Test", order=0)
        assert section.order == 0
    
    def test_order_accepts_negative(self):
        """Test that order can be negative."""
        section = DocumentSection(heading="Test", order=-1)
        assert section.order == -1
