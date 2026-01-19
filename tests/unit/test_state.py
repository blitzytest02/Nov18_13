"""
Unit tests for ReverseDocumentState and state management functions.

Tests cover:
- ReverseDocumentState TypedDict compliance
- get_state function
- State update functions
- State validation
"""

import pytest

from src.app.services.state_manager import (
    ReverseDocumentState,
    get_state,
    update_state,
    add_document_section,
    get_current_section,
    advance_section,
    mark_completed,
    validate_state,
)
from src.app.models.document import DocumentSection, DocumentSectionStatus


@pytest.mark.unit
class TestGetState:
    """Tests for get_state function."""
    
    def test_get_state_returns_typed_dict(self):
        """Test that get_state returns a ReverseDocumentState."""
        state = get_state()
        assert isinstance(state, dict)
    
    def test_get_state_default_values(self):
        """Test get_state with default values."""
        state = get_state()
        
        assert state["tech_spec"] == ""
        assert state["document_sections"] == []
        assert state["current_section_index"] == 0
        assert state["completed"] is False
        assert state["error"] is None
        assert state["metadata"] == {}
    
    def test_get_state_with_tech_spec(self):
        """Test get_state with tech spec provided."""
        state = get_state(tech_spec="My tech spec")
        
        assert state["tech_spec"] == "My tech spec"
    
    def test_get_state_with_document_sections(self):
        """Test get_state with document sections."""
        sections = [{"heading": "Section 1"}]
        state = get_state(document_sections=sections)
        
        assert state["document_sections"] == sections
    
    def test_get_state_with_current_section_index(self):
        """Test get_state with current section index."""
        state = get_state(current_section_index=5)
        
        assert state["current_section_index"] == 5
    
    def test_get_state_with_completed(self):
        """Test get_state with completed flag."""
        state = get_state(completed=True)
        
        assert state["completed"] is True
    
    def test_get_state_with_error(self):
        """Test get_state with error message."""
        state = get_state(error="Something went wrong")
        
        assert state["error"] == "Something went wrong"
    
    def test_get_state_with_metadata(self):
        """Test get_state with metadata."""
        metadata = {"key": "value", "count": 42}
        state = get_state(metadata=metadata)
        
        assert state["metadata"] == metadata
    
    def test_get_state_with_all_parameters(self):
        """Test get_state with all parameters provided."""
        state = get_state(
            tech_spec="Full spec",
            document_sections=[{"heading": "Test"}],
            current_section_index=3,
            completed=True,
            error="Test error",
            metadata={"test": True}
        )
        
        assert state["tech_spec"] == "Full spec"
        assert len(state["document_sections"]) == 1
        assert state["current_section_index"] == 3
        assert state["completed"] is True
        assert state["error"] == "Test error"
        assert state["metadata"]["test"] is True


@pytest.mark.unit
class TestUpdateState:
    """Tests for update_state function."""
    
    def test_update_state_preserves_existing_values(self):
        """Test that update_state preserves unmodified values."""
        original = get_state(tech_spec="Original", completed=False)
        updated = update_state(original, completed=True)
        
        assert updated["tech_spec"] == "Original"
        assert updated["completed"] is True
    
    def test_update_state_creates_new_dict(self):
        """Test that update_state creates a new dictionary."""
        original = get_state()
        updated = update_state(original, tech_spec="New")
        
        assert original is not updated
        assert original["tech_spec"] == ""
        assert updated["tech_spec"] == "New"
    
    def test_update_state_multiple_fields(self):
        """Test updating multiple fields at once."""
        original = get_state()
        updated = update_state(
            original,
            tech_spec="Updated",
            completed=True,
            error="Error occurred"
        )
        
        assert updated["tech_spec"] == "Updated"
        assert updated["completed"] is True
        assert updated["error"] == "Error occurred"


@pytest.mark.unit
class TestAddDocumentSection:
    """Tests for add_document_section function."""
    
    def test_add_document_section_appends_to_list(self):
        """Test that add_document_section appends to document_sections."""
        state = get_state()
        section = DocumentSection(heading="New Section")
        
        new_state = add_document_section(state, section)
        
        assert len(new_state["document_sections"]) == 1
        assert new_state["document_sections"][0]["heading"] == "New Section"
    
    def test_add_document_section_preserves_existing(self):
        """Test that existing sections are preserved."""
        existing_sections = [{"heading": "Existing"}]
        state = get_state(document_sections=existing_sections)
        section = DocumentSection(heading="New Section")
        
        new_state = add_document_section(state, section)
        
        assert len(new_state["document_sections"]) == 2
        assert new_state["document_sections"][0]["heading"] == "Existing"
        assert new_state["document_sections"][1]["heading"] == "New Section"
    
    def test_add_document_section_converts_to_dict(self):
        """Test that section is converted to dict."""
        state = get_state()
        section = DocumentSection(
            heading="Test",
            status=DocumentSectionStatus.CHANGED,
            changes=["Change"]
        )
        
        new_state = add_document_section(state, section)
        
        section_dict = new_state["document_sections"][0]
        assert isinstance(section_dict, dict)
        assert section_dict["status"] == "CHANGED"


@pytest.mark.unit
class TestGetCurrentSection:
    """Tests for get_current_section function."""
    
    def test_get_current_section_returns_section(self):
        """Test that get_current_section returns the current section."""
        sections = [
            {"heading": "Section 0"},
            {"heading": "Section 1"},
            {"heading": "Section 2"}
        ]
        state = get_state(document_sections=sections, current_section_index=1)
        
        current = get_current_section(state)
        
        assert current["heading"] == "Section 1"
    
    def test_get_current_section_first_section(self):
        """Test getting first section at index 0."""
        sections = [{"heading": "First"}]
        state = get_state(document_sections=sections, current_section_index=0)
        
        current = get_current_section(state)
        
        assert current["heading"] == "First"
    
    def test_get_current_section_empty_list(self):
        """Test get_current_section with empty sections list."""
        state = get_state(document_sections=[])
        
        current = get_current_section(state)
        
        assert current is None
    
    def test_get_current_section_out_of_bounds(self):
        """Test get_current_section when index is out of bounds."""
        sections = [{"heading": "Only One"}]
        state = get_state(document_sections=sections, current_section_index=5)
        
        current = get_current_section(state)
        
        assert current is None
    
    def test_get_current_section_negative_index(self):
        """Test get_current_section with negative index."""
        sections = [{"heading": "Test"}]
        state = get_state(document_sections=sections, current_section_index=-1)
        
        current = get_current_section(state)
        
        assert current is None


@pytest.mark.unit
class TestAdvanceSection:
    """Tests for advance_section function."""
    
    def test_advance_section_increments_index(self):
        """Test that advance_section increments the index."""
        sections = [{"heading": "1"}, {"heading": "2"}, {"heading": "3"}]
        state = get_state(document_sections=sections, current_section_index=0)
        
        new_state = advance_section(state)
        
        assert new_state["current_section_index"] == 1
        assert new_state["completed"] is False
    
    def test_advance_section_marks_completed_at_end(self):
        """Test that advance_section marks completed when reaching end."""
        sections = [{"heading": "1"}, {"heading": "2"}]
        state = get_state(document_sections=sections, current_section_index=1)
        
        new_state = advance_section(state)
        
        assert new_state["current_section_index"] == 2
        assert new_state["completed"] is True
    
    def test_advance_section_empty_list(self):
        """Test advance_section with empty sections list."""
        state = get_state(document_sections=[], current_section_index=0)
        
        new_state = advance_section(state)
        
        assert new_state["current_section_index"] == 1
        assert new_state["completed"] is True


@pytest.mark.unit
class TestMarkCompleted:
    """Tests for mark_completed function."""
    
    def test_mark_completed_sets_flag(self):
        """Test that mark_completed sets completed flag."""
        state = get_state(completed=False)
        
        new_state = mark_completed(state)
        
        assert new_state["completed"] is True
    
    def test_mark_completed_with_error(self):
        """Test mark_completed with error message."""
        state = get_state()
        
        new_state = mark_completed(state, error="Processing failed")
        
        assert new_state["completed"] is True
        assert new_state["error"] == "Processing failed"
    
    def test_mark_completed_preserves_other_fields(self):
        """Test that other fields are preserved."""
        state = get_state(tech_spec="Test spec", current_section_index=5)
        
        new_state = mark_completed(state)
        
        assert new_state["tech_spec"] == "Test spec"
        assert new_state["current_section_index"] == 5


@pytest.mark.unit
class TestValidateState:
    """Tests for validate_state function."""
    
    def test_validate_state_valid(self):
        """Test validation passes for valid state."""
        state = get_state(tech_spec="Valid")
        
        assert validate_state(state) is True
    
    def test_validate_state_missing_tech_spec(self):
        """Test validation fails when tech_spec is missing."""
        state = {
            "document_sections": [],
            "current_section_index": 0,
            "completed": False
        }
        
        assert validate_state(state) is False
    
    def test_validate_state_missing_document_sections(self):
        """Test validation fails when document_sections is missing."""
        state = {
            "tech_spec": "Valid",
            "current_section_index": 0,
            "completed": False
        }
        
        assert validate_state(state) is False
    
    def test_validate_state_missing_current_section_index(self):
        """Test validation fails when current_section_index is missing."""
        state = {
            "tech_spec": "Valid",
            "document_sections": [],
            "completed": False
        }
        
        assert validate_state(state) is False
    
    def test_validate_state_missing_completed(self):
        """Test validation fails when completed is missing."""
        state = {
            "tech_spec": "Valid",
            "document_sections": [],
            "current_section_index": 0
        }
        
        assert validate_state(state) is False
    
    def test_validate_state_wrong_type_tech_spec(self):
        """Test validation fails when tech_spec is wrong type."""
        state = {
            "tech_spec": 123,
            "document_sections": [],
            "current_section_index": 0,
            "completed": False
        }
        
        assert validate_state(state) is False
    
    def test_validate_state_wrong_type_document_sections(self):
        """Test validation fails when document_sections is wrong type."""
        state = {
            "tech_spec": "Valid",
            "document_sections": "not a list",
            "current_section_index": 0,
            "completed": False
        }
        
        assert validate_state(state) is False
    
    def test_validate_state_wrong_type_index(self):
        """Test validation fails when current_section_index is wrong type."""
        state = {
            "tech_spec": "Valid",
            "document_sections": [],
            "current_section_index": "not an int",
            "completed": False
        }
        
        assert validate_state(state) is False
    
    def test_validate_state_wrong_type_completed(self):
        """Test validation fails when completed is wrong type."""
        state = {
            "tech_spec": "Valid",
            "document_sections": [],
            "current_section_index": 0,
            "completed": "not a bool"
        }
        
        assert validate_state(state) is False


@pytest.mark.unit
class TestStateImmutability:
    """Tests to verify state functions maintain immutability."""
    
    def test_update_state_does_not_modify_original(self):
        """Test that update_state doesn't modify the original state."""
        original = get_state(tech_spec="Original")
        original_copy = dict(original)
        
        update_state(original, tech_spec="Modified")
        
        assert original == original_copy
    
    def test_add_document_section_does_not_modify_original(self):
        """Test that add_document_section doesn't modify original sections list."""
        sections = [{"heading": "Existing"}]
        original = get_state(document_sections=sections)
        original_sections_len = len(original["document_sections"])
        
        section = DocumentSection(heading="New")
        add_document_section(original, section)
        
        assert len(original["document_sections"]) == original_sections_len
    
    def test_advance_section_does_not_modify_original(self):
        """Test that advance_section doesn't modify the original state."""
        original = get_state(current_section_index=0)
        
        advance_section(original)
        
        assert original["current_section_index"] == 0
    
    def test_mark_completed_does_not_modify_original(self):
        """Test that mark_completed doesn't modify the original state."""
        original = get_state(completed=False)
        
        mark_completed(original)
        
        assert original["completed"] is False
