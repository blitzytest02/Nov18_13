"""
Mock implementations for LLM and LangChain components.

This module provides mock classes for testing LLM interactions and
code graph building without making actual API calls.
"""

from typing import Any, Callable, Dict, List, Optional
from unittest.mock import MagicMock

from tests.fixtures.cloud_responses import (
    CODE_GRAPH_BUILD_RESULT,
    LLM_COMPLETION_RESPONSE,
    LLM_TOOL_CALL_RESPONSE,
)


class MockLLMResponse:
    """
    Mock LLM response object.
    
    Simulates the response structure from LLM API calls.
    """
    
    def __init__(
        self,
        content: str = "Mock LLM response",
        role: str = "assistant",
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        finish_reason: str = "stop"
    ):
        self.content = content
        self.role = role
        self.tool_calls = tool_calls
        self.finish_reason = finish_reason
        self.usage = {
            "prompt_tokens": 50,
            "completion_tokens": len(content.split()),
            "total_tokens": 50 + len(content.split())
        }


class MockLLMChain:
    """
    Mock implementation of a LangChain LLM chain.
    
    Simulates chain execution without actual LLM calls.
    """
    
    def __init__(
        self,
        default_response: str = "Mock chain response",
        responses: Optional[Dict[str, str]] = None
    ):
        self.default_response = default_response
        self.responses = responses or {}
        self.call_history: List[Dict[str, Any]] = []
    
    def run(self, input_text: str, **kwargs: Any) -> str:
        """
        Run the chain with input.
        
        Args:
            input_text: Input text to process
            **kwargs: Additional arguments
            
        Returns:
            Mock response string
        """
        self.call_history.append({
            "input": input_text,
            "kwargs": kwargs
        })
        
        # Return specific response if available
        for pattern, response in self.responses.items():
            if pattern in input_text:
                return response
        
        return self.default_response
    
    def invoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invoke the chain with structured input.
        
        Args:
            input_data: Input dictionary
            
        Returns:
            Mock response dictionary
        """
        input_text = str(input_data)
        response = self.run(input_text)
        return {"output": response}
    
    async def arun(self, input_text: str, **kwargs: Any) -> str:
        """Async version of run."""
        return self.run(input_text, **kwargs)
    
    async def ainvoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Async version of invoke."""
        return self.invoke(input_data)
    
    def clear_history(self) -> None:
        """Clear call history."""
        self.call_history = []


class MockChatModel:
    """
    Mock implementation of a LangChain chat model.
    
    Simulates chat model behavior without actual API calls.
    """
    
    def __init__(
        self,
        model_name: str = "mock-gpt-4",
        default_response: str = "Mock chat response"
    ):
        self.model_name = model_name
        self.default_response = default_response
        self.call_history: List[Dict[str, Any]] = []
    
    def __call__(self, messages: List[Dict[str, str]], **kwargs: Any) -> MockLLMResponse:
        """
        Call the chat model with messages.
        
        Args:
            messages: List of message dictionaries
            **kwargs: Additional arguments
            
        Returns:
            MockLLMResponse object
        """
        self.call_history.append({
            "messages": messages,
            "kwargs": kwargs
        })
        return MockLLMResponse(content=self.default_response)
    
    def invoke(
        self,
        messages: List[Dict[str, str]],
        **kwargs: Any
    ) -> MockLLMResponse:
        """Invoke the model."""
        return self(messages, **kwargs)
    
    async def ainvoke(
        self,
        messages: List[Dict[str, str]],
        **kwargs: Any
    ) -> MockLLMResponse:
        """Async invoke the model."""
        return self(messages, **kwargs)
    
    def bind_tools(self, tools: List[Any]) -> "MockChatModel":
        """Bind tools to the model (returns self for chaining)."""
        return self


class MockCodeGraphBuilder:
    """
    Mock implementation of CodeGraphBuilder.
    
    Simulates code graph building without actual processing.
    """
    
    def __init__(
        self,
        project_id: str = "test-project",
        build_result: Optional[Dict[str, Any]] = None
    ):
        self.project_id = project_id
        self.build_result = build_result or CODE_GRAPH_BUILD_RESULT
        self.build_calls: List[Dict[str, Any]] = []
        self._should_fail = False
        self._fail_message = "Build failed"
    
    def build(
        self,
        source_code: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build a code graph from source code.
        
        Args:
            source_code: Source code to analyze
            options: Optional build options
            
        Returns:
            Build result dictionary
        """
        self.build_calls.append({
            "source_code": source_code,
            "options": options
        })
        
        if self._should_fail:
            raise Exception(self._fail_message)
        
        return self.build_result
    
    async def build_async(
        self,
        source_code: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Async version of build."""
        return self.build(source_code, options)
    
    def set_fail(self, should_fail: bool, message: str = "Build failed") -> None:
        """Configure the builder to fail on next build."""
        self._should_fail = should_fail
        self._fail_message = message
    
    def clear_history(self) -> None:
        """Clear build history."""
        self.build_calls = []


class MockTool:
    """
    Mock implementation of a LangChain tool.
    """
    
    def __init__(
        self,
        name: str,
        description: str = "Mock tool",
        handler: Optional[Callable] = None
    ):
        self.name = name
        self.description = description
        self._handler = handler or (lambda x: f"Executed {name}")
        self.call_history: List[Any] = []
    
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the tool."""
        self.call_history.append({"args": args, "kwargs": kwargs})
        return self._handler(*args, **kwargs)
    
    def run(self, input_data: Any) -> Any:
        """Run the tool with input."""
        return self(input_data)


class MockAgent:
    """
    Mock implementation of a LangChain agent.
    """
    
    def __init__(
        self,
        tools: Optional[List[MockTool]] = None,
        default_response: str = "Mock agent response"
    ):
        self.tools = tools or []
        self.default_response = default_response
        self.run_history: List[Dict[str, Any]] = []
    
    def run(self, input_text: str, **kwargs: Any) -> str:
        """
        Run the agent with input.
        
        Args:
            input_text: Input text
            **kwargs: Additional arguments
            
        Returns:
            Agent response
        """
        self.run_history.append({
            "input": input_text,
            "kwargs": kwargs
        })
        return self.default_response
    
    def invoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke the agent."""
        response = self.run(str(input_data))
        return {"output": response}
    
    async def arun(self, input_text: str, **kwargs: Any) -> str:
        """Async run."""
        return self.run(input_text, **kwargs)


def create_mock_llm_chain(
    responses: Optional[Dict[str, str]] = None
) -> MockLLMChain:
    """
    Create a configured mock LLM chain.
    
    Args:
        responses: Optional pattern-response mapping
        
    Returns:
        MockLLMChain instance
    """
    return MockLLMChain(responses=responses)


def create_mock_chat_model(
    model_name: str = "mock-gpt-4"
) -> MockChatModel:
    """
    Create a configured mock chat model.
    
    Args:
        model_name: Model name to use
        
    Returns:
        MockChatModel instance
    """
    return MockChatModel(model_name=model_name)


def create_mock_code_graph_builder(
    build_result: Optional[Dict[str, Any]] = None
) -> MockCodeGraphBuilder:
    """
    Create a configured mock code graph builder.
    
    Args:
        build_result: Optional custom build result
        
    Returns:
        MockCodeGraphBuilder instance
    """
    return MockCodeGraphBuilder(build_result=build_result)


def create_mock_tool(
    name: str,
    handler: Optional[Callable] = None
) -> MockTool:
    """
    Create a mock tool.
    
    Args:
        name: Tool name
        handler: Optional custom handler function
        
    Returns:
        MockTool instance
    """
    return MockTool(name=name, handler=handler)


def create_mock_agent(
    tools: Optional[List[str]] = None
) -> MockAgent:
    """
    Create a mock agent with tools.
    
    Args:
        tools: Optional list of tool names
        
    Returns:
        MockAgent instance
    """
    mock_tools = [MockTool(name) for name in (tools or [])]
    return MockAgent(tools=mock_tools)
