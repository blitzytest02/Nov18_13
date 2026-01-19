"""
Unit tests for ReverseDocumentHelper class.

Tests cover:
- Helper initialization
- Tool registration and execution
- State management methods
- Document section processing
- LLM response handling
"""

import pytest

from src.app.services.document_helper import ReverseDocumentHelper
from src.app.services.state_manager import get_state, ReverseDocumentState
from src.app.models.document import DocumentSection, DocumentSectionStatus


@pytest.mark.unit
class TestReverseDocumentHelperInit:
    """Tests for ReverseDocumentHelper initialization."""
    
    def test_init_default_values(self):
        """Test initialization with default values."""
        helper = ReverseDocumentHelper()
        
        assert helper.state["tech_spec"] == ""
        assert helper.tools == {}
        assert helper.llm_handler is None
    
    def test_init_with_tech_spec(self):
        """Test initialization with tech spec."""
        helper = ReverseDocumentHelper(tech_spec="My tech spec")
        
        assert helper.state["tech_spec"] == "My tech spec"
    
    def test_init_with_tools(self):
        """Test initialization with tools."""
        tools = {"tool1": lambda x: x, "tool2": lambda x: x * 2}
        helper = ReverseDocumentHelper(tools=tools)
        
        assert len(helper.tools) == 2
        assert "tool1" in helper.tools
        assert "tool2" in helper.tools
    
    def test_init_with_llm_handler(self):
        """Test initialization with LLM handler."""
        handler = lambda x: f"Response: {x}"
        helper = ReverseDocumentHelper(llm_handler=handler)
        
        assert helper.llm_handler is not None


@pytest.mark.unit
class TestToolManagement:
    """Tests for tool registration and management."""
    
    def test_get_tools_returns_dict(self):
        """Test that get_tools returns tools dictionary."""
        tools = {"tool1": lambda x: x}
        helper = ReverseDocumentHelper(tools=tools)
        
        result = helper.get_tools()
        
        assert isinstance(result, dict)
        assert "tool1" in result
    
    def test_register_tool(self):
        """Test registering a new tool."""
        helper = ReverseDocumentHelper()
        helper.register_tool("new_tool", lambda x: x)
        
        assert "new_tool" in helper.tools
    
    def test_register_tool_overwrites_existing(self):
        """Test that registering overwrites existing tool."""
        tools = {"tool": lambda x: "original"}
        helper = ReverseDocumentHelper(tools=tools)
        
        helper.register_tool("tool", lambda x: "updated")
        
        assert helper.tools["tool"]("test") == "updated"
    
    def test_unregister_tool_success(self):
        """Test unregistering an existing tool."""
        tools = {"tool": lambda x: x}
        helper = ReverseDocumentHelper(tools=tools)
        
        result = helper.unregister_tool("tool")
        
        assert result is True
        assert "tool" not in helper.tools
    
    def test_unregister_tool_not_found(self):
        """Test unregistering a non-existent tool."""
        helper = ReverseDocumentHelper()
        
        result = helper.unregister_tool("nonexistent")
        
        assert result is False
    
    def test_execute_tool_success(self):
        """Test executing a registered tool."""
        tools = {"multiply": lambda x, y: x * y}
        helper = ReverseDocumentHelper(tools=tools)
        
        result = helper.execute_tool("multiply", 3, 4)
        
        assert result == 12
    
    def test_execute_tool_with_kwargs(self):
        """Test executing a tool with keyword arguments."""
        tools = {"greet": lambda name, greeting="Hello": f"{greeting}, {name}!"}
        helper = ReverseDocumentHelper(tools=tools)
        
        result = helper.execute_tool("greet", "World", greeting="Hi")
        
        assert result == "Hi, World!"
    
    def test_execute_tool_not_found_raises_error(self):
        """Test that executing non-existent tool raises KeyError."""
        helper = ReverseDocumentHelper()
        
        with pytest.raises(KeyError, match="not registered"):
            helper.execute_tool("nonexistent")


@pytest.mark.unit
class TestStateManagement:
    """Tests for state management methods."""
    
    def test_get_state_returns_current_state(self):
        """Test that get_state returns current state."""
        helper = ReverseDocumentHelper(tech_spec="Test spec")
        
        state = helper.get_state()
        
        assert state["tech_spec"] == "Test spec"
    
    def test_set_state_updates_state(self):
        """Test that set_state updates the internal state."""
        helper = ReverseDocumentHelper()
        new_state = get_state(tech_spec="New spec", completed=True)
        
        helper.set_state(new_state)
        
        assert helper.state["tech_spec"] == "New spec"
        assert helper.state["completed"] is True
    
    def test_is_completed_false_by_default(self):
        """Test that is_completed returns False initially."""
        helper = ReverseDocumentHelper()
        
        assert helper.is_completed() is False
    
    def test_is_completed_after_complete_processing(self):
        """Test is_completed after calling complete_processing."""
        helper = ReverseDocumentHelper()
        helper.complete_processing()
        
        assert helper.is_completed() is True
    
    def test_get_error_none_by_default(self):
        """Test that get_error returns None initially."""
        helper = ReverseDocumentHelper()
        
        assert helper.get_error() is None
    
    def test_get_error_after_error(self):
        """Test get_error after setting an error."""
        helper = ReverseDocumentHelper()
        helper.complete_processing(error="Test error")
        
        assert helper.get_error() == "Test error"
    
    def test_reset_clears_state(self):
        """Test that reset clears the state."""
        helper = ReverseDocumentHelper(tech_spec="Original")
        helper.state["completed"] = True
        helper.state["current_section_index"] = 5
        
        helper.reset()
        
        assert helper.state["completed"] is False
        assert helper.state["current_section_index"] == 0
        assert helper.state["tech_spec"] == "Original"  # Preserved
    
    def test_reset_with_new_tech_spec(self):
        """Test reset with new tech spec."""
        helper = ReverseDocumentHelper(tech_spec="Original")
        
        helper.reset(tech_spec="New spec")
        
        assert helper.state["tech_spec"] == "New spec"
    
    def test_to_dict_returns_state_as_dict(self):
        """Test that to_dict returns state as dictionary."""
        helper = ReverseDocumentHelper(tech_spec="Test")
        
        result = helper.to_dict()
        
        assert isinstance(result, dict)
        assert result["tech_spec"] == "Test"


@pytest.mark.unit
class TestDocumentSectionProcessing:
    """Tests for document section processing methods."""
    
    def test_process_document_section_success(self):
        """Test processing a valid document section."""
        helper = ReverseDocumentHelper()
        section_data = {
            "heading": "Test Section",
            "content": "Test content"
        }
        
        section = helper.process_document_section(section_data)
        
        assert isinstance(section, DocumentSection)
        assert section.heading == "Test Section"
    
    def test_process_document_section_adds_to_state(self):
        """Test that processed section is added to state."""
        helper = ReverseDocumentHelper()
        section_data = {"heading": "New Section"}
        
        helper.process_document_section(section_data)
        
        assert len(helper.state["document_sections"]) == 1
    
    def test_process_document_section_empty_data_raises_error(self):
        """Test that empty section data raises ValueError."""
        helper = ReverseDocumentHelper()
        
        with pytest.raises(ValueError, match="cannot be empty"):
            helper.process_document_section({})
    
    def test_process_document_section_missing_heading_raises_error(self):
        """Test that missing heading raises ValueError."""
        helper = ReverseDocumentHelper()
        
        with pytest.raises(ValueError, match="must contain 'heading'"):
            helper.process_document_section({"content": "No heading"})
    
    def test_process_multiple_sections(self):
        """Test processing multiple sections."""
        helper = ReverseDocumentHelper()
        sections_data = [
            {"heading": "Section 1"},
            {"heading": "Section 2"},
            {"heading": "Section 3"}
        ]
        
        sections = helper.process_multiple_sections(sections_data)
        
        assert len(sections) == 3
        assert helper.get_section_count() == 3
    
    def test_get_document_sections_returns_list(self):
        """Test that get_document_sections returns sections list."""
        helper = ReverseDocumentHelper()
        helper.process_document_section({"heading": "Test"})
        
        sections = helper.get_document_sections()
        
        assert isinstance(sections, list)
        assert len(sections) == 1
    
    def test_get_section_count(self):
        """Test get_section_count returns correct count."""
        helper = ReverseDocumentHelper()
        
        assert helper.get_section_count() == 0
        
        helper.process_document_section({"heading": "Test"})
        
        assert helper.get_section_count() == 1


@pytest.mark.unit
class TestSectionNavigation:
    """Tests for section navigation methods."""
    
    def test_advance_to_next_section_returns_true(self):
        """Test advance_to_next_section returns True when more sections exist."""
        helper = ReverseDocumentHelper()
        helper.process_multiple_sections([
            {"heading": "1"},
            {"heading": "2"},
            {"heading": "3"}
        ])
        
        result = helper.advance_to_next_section()
        
        assert result is True
        assert helper.state["current_section_index"] == 1
    
    def test_advance_to_next_section_returns_false_at_end(self):
        """Test advance_to_next_section returns False at the end."""
        helper = ReverseDocumentHelper()
        helper.process_document_section({"heading": "Only"})
        
        result = helper.advance_to_next_section()
        
        assert result is False
        assert helper.is_completed()
    
    def test_complete_processing_returns_state(self):
        """Test complete_processing returns the final state."""
        helper = ReverseDocumentHelper()
        
        state = helper.complete_processing()
        
        assert isinstance(state, dict)
        assert state["completed"] is True
    
    def test_complete_processing_with_error(self):
        """Test complete_processing with error message."""
        helper = ReverseDocumentHelper()
        
        state = helper.complete_processing(error="Processing failed")
        
        assert state["completed"] is True
        assert state["error"] == "Processing failed"


@pytest.mark.unit
class TestLLMResponseHandling:
    """Tests for LLM response handling."""
    
    def test_handle_llm_response_empty_response(self):
        """Test handle_llm_response with empty response."""
        helper = ReverseDocumentHelper()
        
        result = helper.handle_llm_response("")
        
        assert result["success"] is False
        assert "error" in result
    
    def test_handle_llm_response_success(self):
        """Test handle_llm_response with valid response."""
        helper = ReverseDocumentHelper()
        
        result = helper.handle_llm_response("This is a valid response")
        
        assert result["success"] is True
        assert result["response"] == "This is a valid response"
    
    def test_handle_llm_response_with_context(self):
        """Test handle_llm_response with context."""
        helper = ReverseDocumentHelper()
        context = {"section_id": 1, "action": "analyze"}
        
        result = helper.handle_llm_response("Response", context=context)
        
        assert result["context"] == context
    
    def test_handle_llm_response_updates_metadata(self):
        """Test that handle_llm_response updates state metadata."""
        helper = ReverseDocumentHelper()
        
        helper.handle_llm_response("Test response")
        
        assert "last_llm_response" in helper.state["metadata"]


@pytest.mark.unit
class TestFromState:
    """Tests for from_state class method."""
    
    def test_from_state_creates_helper(self):
        """Test from_state creates helper from existing state."""
        state = get_state(
            tech_spec="Existing spec",
            document_sections=[{"heading": "Existing"}],
            current_section_index=1
        )
        
        helper = ReverseDocumentHelper.from_state(state)
        
        assert helper.state["tech_spec"] == "Existing spec"
        assert helper.state["current_section_index"] == 1
    
    def test_from_state_with_tools(self):
        """Test from_state with tools provided."""
        state = get_state()
        tools = {"tool": lambda x: x}
        
        helper = ReverseDocumentHelper.from_state(state, tools=tools)
        
        assert "tool" in helper.tools
    
    def test_from_state_with_llm_handler(self):
        """Test from_state with LLM handler provided."""
        state = get_state()
        handler = lambda x: x
        
        helper = ReverseDocumentHelper.from_state(state, llm_handler=handler)
        
        assert helper.llm_handler is not None
