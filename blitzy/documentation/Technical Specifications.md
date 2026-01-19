# Technical Specification

# 0. Agent Action Plan

## 0.1 Intent Clarification

### 0.1.1 Core Testing Objective

Based on the provided requirements, the Blitzy platform understands that the testing objective is to **establish a comprehensive test suite for a Python Flask application that will be created by refactoring/converting an existing Node.js server**.

**Request Categorization:** Refactor existing product with full test coverage for the new Flask implementation

**Testing Requirements with Enhanced Clarity:**

- **Primary Objective:** Create unit tests, integration tests, and functional tests for the new Flask-based Python 3 application that preserves all functionalities of the original Node.js project
- **Functional Preservation Testing:** Verify that every endpoint, middleware, service, and utility function from the original Node.js codebase has equivalent functionality in the Flask implementation
- **API Contract Testing:** Ensure all REST API endpoints maintain the same request/response contracts (HTTP methods, paths, status codes, payload schemas)
- **Edge Case Coverage:** Test boundary conditions, error handling, and exceptional scenarios for all converted functionality
- **Integration Verification:** Validate that the Flask application integrates correctly with external dependencies (databases, cloud services, third-party APIs)

**Implicit Testing Needs Surfaced:**

- Route handler testing with Flask's `test_client()`
- Request/response serialization verification
- Authentication and authorization middleware testing
- Database interaction testing (if applicable)
- Cloud service integration mocking (Google Cloud Storage, Pub/Sub)
- Async operation testing for background tasks
- Configuration and environment variable validation

### 0.1.2 Special Instructions and Constraints

**Critical Directives Captured:**

- **Full Functionality Preservation:** All functionalities of the original Node.js project must be preserved and verified through tests
- **Framework Alignment:** Tests must follow Flask testing conventions using `pytest` as the primary test framework
- **Flask-Specific Testing Patterns:** Utilize Flask's built-in test client and application context management

**Testing Requirements:**

- Follow existing repository test patterns where applicable
- Use `pytest-flask` for Flask-specific fixtures and helpers
- Implement proper test isolation using fixtures for app and client instances
- Mock external dependencies (cloud services, databases) to ensure test reliability

**Preserved User Example:**
> "Can you rewrite this node.js server in python 3 using flask, preserving all functionalities of the original project?"

**Web Search Requirements Documented:**

- Flask 3.x testing best practices with pytest
- pytest-flask version compatibility with Flask 3.0+
- Mocking strategies for Google Cloud services (Storage, Pub/Sub)
- Flask application factory pattern for testability

### 0.1.3 Technical Interpretation

These testing requirements translate to the following technical test implementation strategy:

- **To verify route handlers**, we will create Flask test client-based tests that validate HTTP method handling, path routing, and response generation for each endpoint
- **To ensure API contract compliance**, we will implement parametrized tests that verify request parsing, response serialization, and status code behavior
- **To validate business logic preservation**, we will create unit tests for service layer functions, utilities, and helper modules with comprehensive input/output verification
- **To verify external integrations**, we will implement integration tests with mocked cloud services using `pytest-mock` and `unittest.mock`
- **To ensure error handling robustness**, we will create tests that trigger error conditions and verify appropriate HTTP error responses and exception handling

### 0.1.4 Coverage Requirements Interpretation

**Explicit Coverage Targets:**

- The user's request implies comprehensive coverage to ensure "all functionalities" are preserved
- Per Technical Specification Section 6.6, minimum 80% code coverage is mandated for critical paths

**Implicit Coverage Expectations:**

- **Route Coverage:** 100% of Flask routes must have corresponding test cases
- **Service Layer Coverage:** 90%+ coverage for business logic and service modules
- **Utility Function Coverage:** 85%+ coverage for helper functions and utilities
- **Error Handler Coverage:** 100% coverage for custom error handlers and exception responses
- **Configuration Coverage:** Tests must verify all environment-dependent configurations

**Coverage Alignment with Industry Standards:**

To achieve comprehensive testing for a Flask application refactored from Node.js, coverage should include:

- Unit tests for all isolated functions and methods
- Integration tests for database operations and external API calls
- Functional tests for complete user workflows and API sequences
- Edge case tests for boundary conditions, null inputs, and type coercion scenarios
- Regression tests to catch functionality drift from the original Node.js behavior

## 0.2 Test Discovery and Analysis

### 0.2.1 Existing Test Infrastructure Assessment

**Repository Analysis Results:**

The repository search revealed that the current codebase (`archie-job-reverse-document-generator`) at `/app` is already a Python application with the following test-related files:

| File Path | Type | Description |
|-----------|------|-------------|
| `/app/main.test.py` | Integration Script | Manual integration testing using `CodeGraphBuilder` and `asyncio` for graph building operations |
| `/app/done.test.py` | Integration Script | Pub/Sub notification testing for completion workflows |
| `/app/retry.test.py` | Integration Script | Retry mechanism testing for Pub/Sub message handling |

**Critical Discovery:**

Repository analysis reveals that the current "test" files (`*.test.py`) are **manual integration scripts** rather than automated unit tests following pytest conventions. These scripts execute actual cloud operations and are not structured as proper test suites.

**Testing Framework Detection:**

- **Current State:** No pytest configuration files detected (`pytest.ini`, `pyproject.toml [tool.pytest]`, `conftest.py`)
- **Dependencies File:** `/app/requirements.txt` contains:
  ```
  google-cloud-storage
  blitzy-platform-shared
  ```
- **No pytest dependency** is currently declared in requirements.txt
- **Test runner configuration:** Not present

**Mock/Stub Libraries Detection:**

- No mocking libraries currently installed
- Cloud service calls in existing scripts use real clients

**Test Data Fixtures:**

- No structured test fixtures or factories present
- Test data is hardcoded in integration scripts

### 0.2.2 Architecture Analysis for Test Planning

The existing Python application architecture discovered:

**Core Modules Requiring Tests:**

| Module | Location | Test Priority |
|--------|----------|---------------|
| `main.py` | `/app/main.py` | High - Entry point with async handlers |
| `helper.py` | `/app/lib/reverse_document/helper.py` | High - Core business logic |
| `models.py` | `/app/lib/reverse_document/models.py` | Medium - Pydantic models |
| `state.py` | `/app/lib/reverse_document/state.py` | Medium - State management |
| `prompts.py` | `/app/lib/reverse_document/prompts.py` | Low - Static prompt definitions |
| `doc.py` | `/app/lib/reverse_document/doc.py` | Low - Documentation strings |

**External Dependencies Requiring Mocking:**

- `google.cloud.storage` - Cloud Storage operations
- `google.cloud.pubsub_v1` - Pub/Sub messaging
- `langgraph` / `langchain` - AI/LLM operations
- `blitzy_platform_shared` - Internal shared utilities

### 0.2.3 Web Search Research Conducted

**Flask Testing Best Practices (2024-2025):**

- pytest is the recommended testing framework for Flask applications, providing simpler syntax and powerful fixtures
- Flask's built-in `test_client()` enables HTTP request testing without running a live server
- pytest-flask (version 1.3.0) provides Flask 3.0 compatibility and useful fixtures (`app`, `client`, `live_server`)
- Test organization best practice: Separate `tests/unit/` and `tests/functional/` directories

**Mocking Strategies for Cloud Services:**

- Use `unittest.mock` or `pytest-mock` for mocking Google Cloud clients
- Create fixture-based mock factories for consistent test data
- Isolate tests from external services to ensure reliability and speed

**Test Organization Conventions:**

- Test files should follow `test_*.py` or `*_test.py` naming patterns
- Use `conftest.py` for shared fixtures and configuration
- Implement application factory pattern for testable Flask apps

**Common Pitfalls to Avoid:**

- Not using `TESTING = True` configuration flag
- Failing to properly manage application context in tests
- Not isolating database state between tests
- Missing cleanup in fixtures (use `yield` with cleanup code)

### 0.2.4 Flask Application Structure for Testing

For the refactored Flask application, the recommended testable structure:

```
src/
├── app/
│   ├── __init__.py          # Application factory
│   ├── routes/              # Route blueprints
│   ├── services/            # Business logic
│   ├── models/              # Data models
│   └── config.py            # Configuration
tests/
├── conftest.py              # Shared fixtures
├── unit/
│   ├── test_services.py     # Service unit tests
│   └── test_models.py       # Model unit tests
├── functional/
│   ├── test_routes.py       # Route functional tests
│   └── test_api.py          # API endpoint tests
└── integration/
    ├── test_database.py     # Database integration
    └── test_cloud.py        # Cloud service integration
```

This structure enables:
- Clear separation of test types
- Easy selective test execution
- Proper fixture scoping
- Maintainable test organization

## 0.3 Testing Scope Analysis

### 0.3.1 Test Target Identification

**Primary Code to be Tested:**

The Flask application resulting from the Node.js conversion will require comprehensive testing across the following components:

| Module/Class | Location | Test Categories Required |
|-------------|----------|-------------------------|
| Flask Application Factory | `src/app/__init__.py` | Unit (configuration), Functional (initialization) |
| Route Handlers | `src/app/routes/*.py` | Unit (handlers), Functional (HTTP), Integration (full stack) |
| Service Layer | `src/app/services/*.py` | Unit (business logic), Integration (external calls) |
| Data Models | `src/app/models/*.py` | Unit (validation, serialization) |
| Middleware | `src/app/middleware/*.py` | Unit (processing), Functional (request pipeline) |
| Utilities | `src/app/utils/*.py` | Unit (isolated functions) |
| Configuration | `src/app/config.py` | Unit (environment parsing) |

**Existing Test File Mapping:**

| Source File | Existing Test File | Test Categories Present |
|-------------|-------------------|------------------------|
| `/app/main.py` | `/app/main.test.py` | Manual integration (not automated) |
| `/app/lib/reverse_document/helper.py` | None | No coverage |
| `/app/lib/reverse_document/models.py` | None | No coverage |
| `/app/lib/reverse_document/state.py` | None | No coverage |
| `/app/lib/reverse_document/prompts.py` | None | No coverage |

**Dependencies Requiring Mocking:**

| Dependency | Mock Strategy | Rationale |
|-----------|---------------|-----------|
| `google.cloud.storage.Client` | `unittest.mock.MagicMock` | Isolate from GCS operations |
| `google.cloud.pubsub_v1.PublisherClient` | Fixture with mock | Prevent actual message publishing |
| `google.cloud.pubsub_v1.SubscriberClient` | Fixture with mock | Control message consumption |
| `langgraph` / `langchain` components | Module-level patches | Avoid LLM API calls |
| `blitzy_platform_shared.code_graph.builder.CodeGraphBuilder` | Mock class | Control graph operations |
| Database connections (if applicable) | In-memory SQLite or mock | Ensure test isolation |

### 0.3.2 Version Compatibility Research

**Python Version Compatibility:**

Based on Technical Specification Section 6.6 and current repository analysis, the recommended Python version is **Python 3.11+** for optimal compatibility with modern Flask and testing libraries.

**Recommended Testing Stack for Flask 3.x:**

| Component | Package | Version | Rationale |
|-----------|---------|---------|-----------|
| Testing Framework | `pytest` | 8.3.x | Latest stable, broad plugin ecosystem |
| Flask Testing Plugin | `pytest-flask` | 1.3.0 | Flask 3.0 compatibility confirmed |
| Async Testing | `pytest-asyncio` | 0.24.x | For async route handlers |
| Mocking Library | `pytest-mock` | 3.14.x | Simplified mocking interface |
| Coverage Tool | `pytest-cov` | 6.0.x | Coverage reporting with pytest |
| HTTP Testing | `requests-mock` | 1.12.x | For mocking external HTTP calls |
| Factory Library | `factory-boy` | 3.3.x | Test data generation |

**Flask and Dependencies Version Matrix:**

| Package | Minimum Version | Recommended Version | Notes |
|---------|----------------|---------------------|-------|
| Flask | 3.0.0 | 3.1.2 | Latest stable release |
| Werkzeug | 3.0.0 | 3.1.x | Required by Flask 3.x |
| Jinja2 | 3.1.2 | 3.1.x | Template engine |
| Click | 8.1.3 | 8.1.x | CLI support |
| itsdangerous | 2.1.2 | 2.2.x | Security utilities |

**Version Conflict Resolutions:**

- **pytest-flask 1.3.0** has confirmed Flask 3.0 compatibility (removed deprecated `request_ctx`)
- **Werkzeug 3.1.x** may have compatibility issues with older pytest-flask versions; use pytest-flask 1.3.0+
- **pytest 8.x** requires Python 3.8+ and provides best async support

### 0.3.3 Test Type Matrix

| Test Type | Scope | Framework | Isolation Level |
|-----------|-------|-----------|-----------------|
| Unit Tests | Individual functions/methods | pytest | Full isolation with mocks |
| Functional Tests | Route handlers, request/response | pytest + Flask test_client | Application context |
| Integration Tests | Database, external services | pytest + real/mock services | Controlled external access |
| Contract Tests | API schema validation | pytest + jsonschema | Response validation |
| Regression Tests | Comparison with Node.js behavior | pytest + parametrize | Behavioral parity |

### 0.3.4 Critical Path Identification

**High-Priority Test Areas (ordered by criticality):**

1. **API Endpoint Functionality** - All routes must return correct responses
2. **Request Validation** - Input parsing and validation logic
3. **Authentication/Authorization** - Security middleware (if present)
4. **Business Logic Services** - Core processing functions
5. **External Integration Points** - Cloud service interactions
6. **Error Handling** - Exception responses and error codes
7. **Configuration Loading** - Environment-based settings

## 0.4 Test Implementation Design

### 0.4.1 Test Strategy Selection

**Test Types to Implement:**

| Test Type | Focus Area | Priority |
|-----------|------------|----------|
| **Unit Tests** | Isolated service functions, model validation, utility methods | High |
| **Integration Tests** | Database operations, cloud service interactions, external API calls | High |
| **Functional Tests** | Route handlers, request/response cycles, middleware chains | High |
| **Edge Case Tests** | Boundary conditions, empty inputs, malformed data, type coercion | Medium |
| **Error Handling Tests** | Exception scenarios, HTTP error responses, validation failures | High |
| **Performance Tests** | Response time thresholds (optional) | Low |

**Testing Pyramid Adherence:**

```
        /\
       /  \  E2E Tests (5%)
      /----\
     /      \  Integration Tests (25%)
    /--------\
   /          \  Unit Tests (70%)
  --------------
```

### 0.4.2 Test Case Blueprint

**Application Factory (`src/app/__init__.py`):**

```
Component: Flask Application Factory (create_app)
Test Categories:
- Happy path: App creates with valid configuration, blueprints registered
- Edge cases: Missing environment variables, invalid config values
- Error cases: Malformed configuration, missing required settings
```

**Route Handlers (`src/app/routes/*.py`):**

```
Component: API Route Handlers
Test Categories:
- Happy path: Valid requests return correct status codes and data
- Edge cases: Empty payloads, maximum payload sizes, special characters
- Error cases: Invalid JSON, missing required fields, unauthorized access
- Performance boundaries: Large response handling, pagination
```

**Service Layer (`src/app/services/*.py`):**

```
Component: Business Logic Services
Test Categories:
- Happy path: Correct processing with valid inputs
- Edge cases: Null values, empty collections, boundary integers
- Error cases: Invalid data types, database failures, external service errors
- Async operations: Concurrent processing, timeout handling
```

**Data Models (`src/app/models/*.py`):**

```
Component: Pydantic/Dataclass Models
Test Categories:
- Happy path: Valid data serialization/deserialization
- Edge cases: Optional fields, default values, nested objects
- Error cases: Type validation failures, constraint violations
```

**Cloud Integration (`src/app/services/cloud_*.py`):**

```
Component: Google Cloud Service Integrations
Test Categories:
- Happy path: Successful storage uploads, message publishing
- Edge cases: Empty files, maximum file sizes, special bucket names
- Error cases: Network failures, authentication errors, quota exceeded
- Mock verification: Correct API calls with expected parameters
```

### 0.4.3 Existing Test Extension Strategy

**Tests to Transform:**

- **`/app/main.test.py`** → Refactor into automated pytest tests under `tests/integration/test_graph_builder.py`
  - Extract test scenarios from manual script
  - Add proper assertions and fixtures
  - Implement mock for `CodeGraphBuilder`

- **`/app/done.test.py`** → Convert to `tests/integration/test_pubsub_notifications.py`
  - Add parametrized test cases
  - Mock Pub/Sub client interactions
  - Verify message payloads

- **`/app/retry.test.py`** → Transform into `tests/integration/test_retry_mechanism.py`
  - Add retry count verification
  - Test exponential backoff behavior
  - Mock subscription pulls

**Tests to Create (New Coverage):**

- `tests/unit/test_models.py` - Pydantic model validation
- `tests/unit/test_helper.py` - Helper function unit tests
- `tests/unit/test_state.py` - State management tests
- `tests/functional/test_routes.py` - Flask route handlers
- `tests/functional/test_api_contracts.py` - API schema validation

### 0.4.4 Test Data and Fixtures Design

**Required Test Data Structures:**

| Data Type | Purpose | Implementation |
|-----------|---------|----------------|
| User Context | Test user scenarios | Factory with faker |
| Tech Spec Documents | Document processing | JSON fixtures |
| Graph State | State management | TypedDict factories |
| Cloud Responses | Mock service responses | JSON/dict templates |

**Fixture Organization Strategy:**

```python
# tests/conftest.py - Global fixtures

@pytest.fixture
def app():
    """Create Flask application for testing."""
    app = create_app({"TESTING": True})
    yield app

@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()

@pytest.fixture
def mock_storage_client():
    """Mock Google Cloud Storage client."""
    with patch("google.cloud.storage.Client"):
        yield MagicMock()
```

**Mock Object Specifications:**

| Mock Target | Return Values | Side Effects |
|-------------|---------------|--------------|
| `storage.Client.bucket()` | Mock bucket object | None |
| `storage.Blob.upload_from_string()` | None | Record call args |
| `pubsub.PublisherClient.publish()` | Future with message_id | None |
| `CodeGraphBuilder.build()` | Mock graph result | None |

**Test Database/State Management:**

- Use in-memory structures for state management tests
- Reset state fixtures between tests using `autouse=True` fixtures
- Implement session-scoped fixtures for expensive setup operations

## 0.5 Test File Transformation Mapping

### 0.5.1 File-by-File Test Plan

**Test Transformation Modes:**
- **CREATE** - Create a new test file
- **UPDATE** - Update an existing test file  
- **DELETE** - Remove an obsolete test file
- **REFERENCE** - Use as an example for test patterns and styles

| Target Test File | Transformation | Source File/Reference | Purpose/Changes |
|-----------------|----------------|----------------------|-----------------|
| `tests/conftest.py` | CREATE | Flask documentation patterns | Shared fixtures: app factory, test client, mock services |
| `tests/unit/__init__.py` | CREATE | N/A | Package marker for unit tests |
| `tests/unit/test_models.py` | CREATE | `/app/lib/reverse_document/models.py` | Unit tests for Pydantic models (DocumentSection, DocumentSectionStatus) |
| `tests/unit/test_state.py` | CREATE | `/app/lib/reverse_document/state.py` | Unit tests for ReverseDocumentState TypedDict and get_state function |
| `tests/unit/test_helper.py` | CREATE | `/app/lib/reverse_document/helper.py` | Unit tests for ReverseDocumentHelper class methods with mocked dependencies |
| `tests/unit/test_config.py` | CREATE | `src/app/config.py` | Unit tests for configuration loading and environment variable parsing |
| `tests/unit/test_utils.py` | CREATE | `src/app/utils/*.py` | Unit tests for utility functions |
| `tests/functional/__init__.py` | CREATE | N/A | Package marker for functional tests |
| `tests/functional/test_routes.py` | CREATE | `src/app/routes/*.py` | Functional tests for all Flask route handlers using test_client |
| `tests/functional/test_api_contracts.py` | CREATE | API specification | Request/response schema validation tests |
| `tests/functional/test_middleware.py` | CREATE | `src/app/middleware/*.py` | Middleware processing tests |
| `tests/integration/__init__.py` | CREATE | N/A | Package marker for integration tests |
| `tests/integration/test_graph_builder.py` | CREATE | `/app/main.test.py` | Refactored integration tests for CodeGraphBuilder with proper mocking |
| `tests/integration/test_pubsub.py` | CREATE | `/app/done.test.py`, `/app/retry.test.py` | Consolidated Pub/Sub integration tests with mocked clients |
| `tests/integration/test_storage.py` | CREATE | Cloud storage operations | Google Cloud Storage integration tests with mocked client |
| `tests/fixtures/__init__.py` | CREATE | N/A | Package marker for test fixtures |
| `tests/fixtures/document_fixtures.py` | CREATE | `/app/lib/reverse_document/models.py` | Test data factories for DocumentSection models |
| `tests/fixtures/state_fixtures.py` | CREATE | `/app/lib/reverse_document/state.py` | Test data factories for ReverseDocumentState |
| `tests/fixtures/cloud_responses.py` | CREATE | GCS/Pub/Sub documentation | Mock response templates for cloud services |
| `tests/mocks/__init__.py` | CREATE | N/A | Package marker for mock objects |
| `tests/mocks/mock_cloud_clients.py` | CREATE | Google Cloud SDK | Mock implementations for Storage and Pub/Sub clients |
| `tests/mocks/mock_llm.py` | CREATE | langchain/langgraph | Mock implementations for LLM components |
| `/app/main.test.py` | DELETE | N/A | Remove manual integration script (replaced by automated tests) |
| `/app/done.test.py` | DELETE | N/A | Remove manual integration script (replaced by automated tests) |
| `/app/retry.test.py` | DELETE | N/A | Remove manual integration script (replaced by automated tests) |
| `pytest.ini` | CREATE | pytest documentation | Pytest configuration with test paths, markers, coverage settings |
| `.coveragerc` | CREATE | pytest-cov documentation | Coverage configuration with source paths and exclusions |

### 0.5.2 New Test Files Detail

**`tests/conftest.py` - Shared Fixtures:**
```
- Test categories: Configuration, fixtures, plugins
- Fixtures provided: app, client, runner, mock_storage, mock_pubsub
- Scope: Session and function-level fixtures
```

**`tests/unit/test_models.py` - Model Unit Tests:**
```
- Test categories: Validation, serialization, edge cases
- Test methods:
  - test_document_section_valid_data
  - test_document_section_status_enum
  - test_document_sections_list_validation
  - test_document_section_invalid_heading
  - test_document_section_empty_changes_when_unchanged
- Mock dependencies: None (pure data models)
```

**`tests/unit/test_helper.py` - Helper Function Tests:**
```
- Test categories: Business logic, tool execution, state transitions
- Test methods:
  - test_reverse_document_helper_initialization
  - test_get_tools_returns_expected_tools
  - test_process_document_section
  - test_handle_llm_response
- Mock dependencies: langchain, langgraph, CodeGraphBuilder
```

**`tests/unit/test_state.py` - State Management Tests:**
```
- Test categories: TypedDict compliance, get_state function
- Test methods:
  - test_reverse_document_state_required_fields
  - test_get_state_returns_all_fields
  - test_get_state_preserves_values
- Mock dependencies: CodeGraphBuilder
```

**`tests/functional/test_routes.py` - Route Handler Tests:**
```
- Test categories: HTTP methods, status codes, response bodies
- Test methods:
  - test_health_check_endpoint
  - test_process_document_endpoint_success
  - test_process_document_endpoint_invalid_payload
  - test_process_document_endpoint_unauthorized
- Assertions focus: Status codes, JSON responses, headers
```

**`tests/integration/test_graph_builder.py` - Graph Builder Integration:**
```
- Test categories: End-to-end graph building, async operations
- Test methods:
  - test_build_graph_success
  - test_build_graph_with_invalid_input
  - test_graph_builder_retry_on_failure
- Integration points: CodeGraphBuilder, state management
```

**`tests/integration/test_pubsub.py` - Pub/Sub Integration:**
```
- Test categories: Message publishing, subscription handling
- Test methods:
  - test_publish_completion_message
  - test_handle_retry_message
  - test_subscription_pull_and_acknowledge
- Mock dependencies: google.cloud.pubsub_v1
```

### 0.5.3 Test Configuration Updates

**`pytest.ini` Configuration:**
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short --strict-markers
markers =
    unit: Unit tests (fast, isolated)
    functional: Functional tests (Flask routes)
    integration: Integration tests (external services)
    slow: Slow running tests
```

**`.coveragerc` Configuration:**
```ini
[run]
source = src/app
branch = True
omit =
    */tests/*
    */__pycache__/*
    */migrations/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise NotImplementedError
fail_under = 80
```

### 0.5.4 Cross-File Test Dependencies

**Shared Fixtures Location and Usage:**

| Fixture | Location | Used By |
|---------|----------|---------|
| `app` | `tests/conftest.py` | All functional and integration tests |
| `client` | `tests/conftest.py` | Route handler tests |
| `mock_storage_client` | `tests/conftest.py` | Storage integration tests |
| `mock_pubsub_publisher` | `tests/conftest.py` | Pub/Sub integration tests |
| `sample_document_section` | `tests/fixtures/document_fixtures.py` | Model and state tests |
| `sample_state` | `tests/fixtures/state_fixtures.py` | Helper and integration tests |

**Mock Objects Location and Purpose:**

| Mock | Location | Purpose |
|------|----------|---------|
| `MockStorageClient` | `tests/mocks/mock_cloud_clients.py` | Simulate GCS operations |
| `MockPubSubPublisher` | `tests/mocks/mock_cloud_clients.py` | Simulate message publishing |
| `MockLLMChain` | `tests/mocks/mock_llm.py` | Simulate LLM responses |
| `MockCodeGraphBuilder` | `tests/mocks/mock_llm.py` | Simulate graph building |

**Import Updates Required:**

```python
# All test files should import from conftest implicitly

#### Explicit imports for fixtures:

from tests.fixtures.document_fixtures import sample_document
from tests.fixtures.state_fixtures import create_test_state
from tests.mocks.mock_cloud_clients import MockStorageClient
```

## 0.6 Dependency Inventory

### 0.6.1 Testing Dependencies

**Core Testing Packages:**

| Registry | Package Name | Version | Purpose |
|----------|--------------|---------|---------|
| pip | pytest | 8.3.4 | Primary testing framework with fixtures and assertions |
| pip | pytest-flask | 1.3.0 | Flask-specific fixtures (app, client, live_server) |
| pip | pytest-cov | 6.0.0 | Coverage measurement and reporting |
| pip | pytest-mock | 3.14.0 | Simplified mocking interface with mocker fixture |
| pip | pytest-asyncio | 0.24.0 | Async test support for asyncio code |
| pip | pytest-xdist | 3.5.0 | Parallel test execution |

**Flask Application Packages:**

| Registry | Package Name | Version | Purpose |
|----------|--------------|---------|---------|
| pip | Flask | 3.1.2 | Web framework (target application) |
| pip | Werkzeug | 3.1.3 | WSGI utilities (Flask dependency) |
| pip | Jinja2 | 3.1.4 | Template engine |
| pip | click | 8.1.7 | CLI support |
| pip | itsdangerous | 2.2.0 | Security utilities |

**Mocking and Test Data Packages:**

| Registry | Package Name | Version | Purpose |
|----------|--------------|---------|---------|
| pip | factory-boy | 3.3.1 | Test data factory creation |
| pip | faker | 30.8.0 | Fake data generation for tests |
| pip | requests-mock | 1.12.1 | HTTP request mocking |
| pip | responses | 0.25.3 | Alternative HTTP mocking library |
| pip | freezegun | 1.4.0 | Time mocking for date-dependent tests |

**Cloud Service Mocking:**

| Registry | Package Name | Version | Purpose |
|----------|--------------|---------|---------|
| pip | google-cloud-storage | 2.18.2 | GCS client (with mock support) |
| pip | google-cloud-pubsub | 2.27.1 | Pub/Sub client (with mock support) |
| pip | google-cloud-testutils | 1.4.0 | Google Cloud testing utilities |

**Code Quality and Linting:**

| Registry | Package Name | Version | Purpose |
|----------|--------------|---------|---------|
| pip | coverage | 7.6.4 | Code coverage measurement (pytest-cov backend) |
| pip | pytest-clarity | 1.0.1 | Improved assertion diff output |
| pip | pytest-sugar | 1.0.0 | Enhanced test output formatting |

### 0.6.2 Requirements File Updates

**`requirements-test.txt` (New File):**

```
# Testing Framework

pytest==8.3.4
pytest-flask==1.3.0
pytest-cov==6.0.0
pytest-mock==3.14.0
pytest-asyncio==0.24.0
pytest-xdist==3.5.0

#### Test Data and Mocking

factory-boy==3.3.1
faker==30.8.0
requests-mock==1.12.1
freezegun==1.4.0

#### Code Quality

coverage==7.6.4
pytest-clarity==1.0.1
pytest-sugar==1.0.0
```

**`requirements.txt` Updates:**

The main `requirements.txt` should include Flask and its dependencies:

```
# Flask Application

Flask==3.1.2
Werkzeug==3.1.3
Jinja2==3.1.4
click==8.1.7
itsdangerous==2.2.0

#### Existing Dependencies (preserved)

google-cloud-storage==2.18.2
google-cloud-pubsub==2.27.1
blitzy-platform-shared

#### Data Validation

pydantic==2.10.3
```

### 0.6.3 Import Updates (If Applicable)

**Test Files Requiring Import Structure:**

| Test File | Import Pattern |
|-----------|----------------|
| `tests/unit/test_models.py` | `from src.app.models import DocumentSection, DocumentSectionStatus` |
| `tests/unit/test_helper.py` | `from src.app.services.helper import ReverseDocumentHelper` |
| `tests/unit/test_state.py` | `from src.app.services.state import ReverseDocumentState, get_state` |
| `tests/functional/test_routes.py` | `from src.app import create_app` |
| `tests/integration/test_pubsub.py` | `from google.cloud import pubsub_v1` |

**Import Transformation Rules:**

For the refactored Flask application, imports should follow this pattern:

| Old Import (Current) | New Import (Flask App) |
|---------------------|----------------------|
| `from lib.reverse_document.models import *` | `from src.app.models.document import *` |
| `from lib.reverse_document.helper import *` | `from src.app.services.document_helper import *` |
| `from lib.reverse_document.state import *` | `from src.app.services.state_manager import *` |

**Conftest Import Configuration:**

```python
# tests/conftest.py

import sys
from pathlib import Path

#### Add src to path for imports

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from src.app import create_app
```

### 0.6.4 Dependency Version Compatibility Matrix

| Package | Min Python | Flask Compat | Notes |
|---------|-----------|--------------|-------|
| pytest 8.3.x | 3.8+ | Any | Stable release |
| pytest-flask 1.3.0 | 3.8+ | 3.0+ | Flask 3.0 compatible |
| pytest-asyncio 0.24.x | 3.8+ | Any | Latest async support |
| factory-boy 3.3.x | 3.8+ | N/A | Independent |
| google-cloud-storage 2.18.x | 3.8+ | N/A | Latest stable |
| pydantic 2.10.x | 3.8+ | Any | Latest v2 release |

## 0.7 Coverage and Quality Targets

### 0.7.1 Coverage Metrics

**Current Coverage Status:**

| Component | Current Coverage | Notes |
|-----------|-----------------|-------|
| `/app/main.py` | 0% | No automated tests |
| `/app/lib/reverse_document/helper.py` | 0% | No automated tests |
| `/app/lib/reverse_document/models.py` | 0% | No automated tests |
| `/app/lib/reverse_document/state.py` | 0% | No automated tests |
| **Overall** | **0%** | Manual scripts only, no pytest coverage |

**Target Coverage Goals:**

| Component | Target Coverage | Rationale |
|-----------|----------------|-----------|
| Route Handlers | 95% | Critical user-facing code |
| Service Layer | 90% | Core business logic |
| Model Validation | 100% | Data integrity critical |
| Configuration | 85% | Environment handling |
| Utility Functions | 85% | Shared functionality |
| Error Handlers | 100% | Error response consistency |
| Middleware | 90% | Request processing |
| **Overall Minimum** | **80%** | Per Tech Spec 6.6 mandate |

**Coverage Gap Analysis:**

| Module | Current | Target | Gap | Priority |
|--------|---------|--------|-----|----------|
| `src/app/routes/*.py` | 0% | 95% | 95% | HIGH |
| `src/app/services/*.py` | 0% | 90% | 90% | HIGH |
| `src/app/models/*.py` | 0% | 100% | 100% | HIGH |
| `src/app/config.py` | 0% | 85% | 85% | MEDIUM |
| `src/app/utils/*.py` | 0% | 85% | 85% | MEDIUM |
| `src/app/middleware/*.py` | 0% | 90% | 90% | MEDIUM |

**Per-File Coverage Targets:**

| File Pattern | Minimum Coverage |
|-------------|------------------|
| `**/routes/*.py` | 95% |
| `**/services/*.py` | 90% |
| `**/models/*.py` | 100% |
| `**/middleware/*.py` | 90% |
| `**/utils/*.py` | 85% |
| `**/config.py` | 85% |

### 0.7.2 Test Quality Criteria

**Assertion Density Expectations:**

| Test Type | Min Assertions/Test | Rationale |
|-----------|---------------------|-----------|
| Unit Tests | 1-3 | Focused single-responsibility |
| Functional Tests | 2-5 | Request + response validation |
| Integration Tests | 3-7 | Multi-component verification |

**Test Isolation Requirements:**

- Each test must be executable in isolation without dependencies on other tests
- Tests must not share mutable state
- Database/storage state must be reset between tests
- Mock objects must be freshly instantiated per test or properly reset

**Performance Constraints:**

| Test Category | Max Execution Time | Target |
|---------------|-------------------|--------|
| Individual Unit Test | 100ms | <50ms |
| Individual Functional Test | 500ms | <200ms |
| Individual Integration Test | 2000ms | <1000ms |
| Full Test Suite | 5 minutes | <3 minutes |

**Maintainability Standards:**

- Test function names must clearly describe the scenario being tested
- Use `pytest.mark.parametrize` for testing multiple inputs
- Group related tests in classes where appropriate
- Keep test files under 500 lines; split if exceeded
- Document non-obvious test setup with comments

**Repository Test Pattern Conventions:**

Based on the existing codebase patterns:
- Use `snake_case` for test function names
- Prefix test functions with `test_`
- Use descriptive names: `test_<function>_<scenario>_<expected_result>`
- Example: `test_document_section_with_invalid_heading_raises_validation_error`

### 0.7.3 Quality Gates

**Pre-Commit Quality Checks:**

| Check | Threshold | Action on Failure |
|-------|-----------|-------------------|
| Unit Tests Pass | 100% | Block commit |
| Coverage Threshold | 80% | Block commit |
| Linting (if configured) | No errors | Block commit |

**CI/CD Quality Gates:**

| Stage | Requirement | Action on Failure |
|-------|-------------|-------------------|
| Unit Tests | 100% pass | Block merge |
| Integration Tests | 100% pass | Block merge |
| Coverage | ≥80% overall | Block merge |
| Coverage Delta | No decrease >2% | Warn |

**Test Reliability Standards:**

- No flaky tests allowed (tests must pass consistently)
- Retry logic only for integration tests with external dependencies
- Maximum 1 retry for integration tests
- Flaky tests must be quarantined and fixed within 1 sprint

### 0.7.4 Coverage Exclusions

**Intentionally Excluded from Coverage:**

```python
# .coveragerc exclusions

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise NotImplementedError
    if TYPE_CHECKING:
    @abstractmethod
    pass
```

**Excluded Directories:**

- `tests/` - Test code itself
- `*/__pycache__/` - Bytecode cache
- `*/migrations/` - Database migrations (if applicable)
- `docs/` - Documentation
- `scripts/` - Utility scripts (non-production)

## 0.8 Scope Boundaries

### 0.8.1 Exhaustively In Scope

**New Test Files (with trailing patterns):**

- `tests/**/__init__.py` - Package markers for all test directories
- `tests/conftest.py` - Shared pytest fixtures and configuration
- `tests/unit/**/*_test.py` - All unit test files
- `tests/unit/**/test_*.py` - Alternative naming pattern unit tests
- `tests/functional/**/*_test.py` - All functional test files
- `tests/functional/**/test_*.py` - Alternative naming pattern functional tests
- `tests/integration/**/*_test.py` - All integration test files
- `tests/integration/**/test_*.py` - Alternative naming pattern integration tests
- `tests/fixtures/**/*.py` - All test fixture files
- `tests/mocks/**/*.py` - All mock object files

**Test File Updates:**

- `tests/unit/test_models.py` - Pydantic model validation tests
- `tests/unit/test_state.py` - State management tests
- `tests/unit/test_helper.py` - Helper function tests (with mocked LLM)
- `tests/unit/test_config.py` - Configuration loading tests
- `tests/functional/test_routes.py` - Flask route handler tests
- `tests/functional/test_api_contracts.py` - API contract validation
- `tests/functional/test_middleware.py` - Middleware processing tests
- `tests/integration/test_graph_builder.py` - Graph builder integration
- `tests/integration/test_pubsub.py` - Pub/Sub integration tests
- `tests/integration/test_storage.py` - Cloud storage integration

**Test Configuration:**

- `pytest.ini` - Pytest configuration with markers and options
- `pyproject.toml` - Alternative pytest configuration section `[tool.pytest.ini_options]`
- `.coveragerc` - Coverage tool configuration
- `setup.cfg` - Alternative coverage configuration section `[coverage:run]`
- `tox.ini` - Multi-environment test configuration (if needed)

**Test Utilities and Helpers:**

- `tests/helpers/**/*.py` - Shared test helper functions
- `tests/helpers/assertions.py` - Custom assertion utilities
- `tests/helpers/generators.py` - Test data generators
- `tests/mocks/**/*.py` - Mock object implementations
- `tests/mocks/mock_cloud_clients.py` - Google Cloud client mocks
- `tests/mocks/mock_llm.py` - LangChain/LangGraph mocks
- `tests/factories/**/*.py` - Factory-boy factories
- `tests/factories/document_factory.py` - Document model factories
- `tests/factories/state_factory.py` - State object factories
- `tests/utils/**/*.py` - Test utility modules

**Documentation Updates:**

- `README.md` - Testing section with commands and instructions
- `docs/testing/**/*.md` - Detailed testing documentation
- `docs/testing/README.md` - Testing guide
- `docs/testing/CONTRIBUTING.md` - Test contribution guidelines
- `TESTING.md` - Top-level testing documentation (alternative)

**Dependency Manifest Updates:**

- `requirements.txt` - Add Flask dependencies
- `requirements-test.txt` - Testing dependencies (new file)
- `requirements-dev.txt` - Development dependencies (if exists)
- `pyproject.toml` - Dependencies section updates (if using)
- `setup.py` - Test requirements in extras_require (if exists)

### 0.8.2 Explicitly Out of Scope

**Source Code Modifications:**

- `src/app/**/*.py` - Application source code (create only, no modification unless for testability)
- `/app/lib/**/*.py` - Existing library code (reference only)
- `/app/main.py` - Existing entry point (reference only)
- Production configuration files
- Database schema modifications
- Infrastructure code changes

**Excluded Test Types:**

- Performance/load testing (separate effort)
- Security penetration testing (separate effort)
- Browser-based E2E testing (not applicable for API)
- Visual regression testing (not applicable)
- Chaos engineering tests (infrastructure scope)

**Refactoring Beyond Testing Needs:**

- Code optimization for performance
- Architecture redesign
- Dependency version upgrades (unless required for tests)
- Feature additions while adding tests
- Technical debt cleanup unrelated to testing

**Unrelated Test Files:**

- Tests for unmodified/legacy components
- Tests for third-party libraries
- Tests for infrastructure code
- Tests for deployment scripts
- Tests for documentation generation

**Files Explicitly Excluded Per User Instructions:**

- No files explicitly excluded by user in this request
- Standard exclusions apply (vendor directories, build artifacts)

### 0.8.3 Conditional Scope Items

**Included If Present in Flask Application:**

| Component | Include If | Test Type |
|-----------|-----------|-----------|
| Authentication middleware | Auth routes exist | Functional |
| Database models | ORM configured | Unit + Integration |
| Caching layer | Cache configured | Integration |
| Rate limiting | Rate limiter present | Functional |
| Background tasks | Celery/workers configured | Integration |
| WebSocket handlers | WebSocket routes exist | Functional |

**Scope Expansion Triggers:**

- Discovery of additional Flask blueprints → Add corresponding route tests
- Discovery of custom error handlers → Add error handling tests
- Discovery of request validators → Add validation tests
- Discovery of response serializers → Add serialization tests

### 0.8.4 Boundary Decision Matrix

| Item | In Scope? | Rationale |
|------|-----------|-----------|
| Unit tests for converted Flask code | ✅ Yes | Core requirement |
| Integration tests with mocked services | ✅ Yes | Verify external calls |
| Functional tests for API endpoints | ✅ Yes | Ensure API contracts |
| Performance benchmarks | ❌ No | Separate effort |
| Source code bug fixes | ❌ No | Not testing scope |
| New feature implementation | ❌ No | Conversion only |
| Database migration tests | ⚠️ Conditional | If DB present |
| Authentication flow tests | ⚠️ Conditional | If auth present |

## 0.9 Execution Parameters

### 0.9.1 Test Execution Commands

**Primary Test Execution:**

```bash
# Run all tests

pytest

#### Run all tests with verbose output

pytest -v

#### Run all tests with coverage reporting

pytest --cov=src/app --cov-report=html --cov-report=term-missing

#### Run tests with parallel execution (4 workers)

pytest -n 4
```

**Selective Test Execution:**

```bash
# Run only unit tests

pytest tests/unit/ -v

#### Run only functional tests

pytest tests/functional/ -v

#### Run only integration tests

pytest tests/integration/ -v

#### Run tests matching a pattern

pytest -k "test_document" -v

#### Run tests with specific marker

pytest -m unit -v
pytest -m "not slow" -v
```

**Coverage Measurement:**

```bash
# Generate coverage report

pytest --cov=src/app --cov-report=term-missing

#### Generate HTML coverage report

pytest --cov=src/app --cov-report=html

#### Generate XML coverage report (for CI)

pytest --cov=src/app --cov-report=xml

#### Fail if coverage below threshold

pytest --cov=src/app --cov-fail-under=80
```

**Debug Mode Execution:**

```bash
# Run with debug output (print statements visible)

pytest -s -v

#### Run with full traceback on failures

pytest --tb=long

#### Run and drop into debugger on failure

pytest --pdb

#### Run specific test with debugging

pytest tests/unit/test_models.py::test_document_section_valid -s -v
```

### 0.9.2 Environment Setup Commands

**Virtual Environment Setup:**

```bash
# Create virtual environment

python3 -m venv venv

#### Activate virtual environment (Linux/Mac)

source venv/bin/activate

#### Activate virtual environment (Windows)

venv\Scripts\activate

#### Install dependencies

pip install -r requirements.txt
pip install -r requirements-test.txt
```

**Environment Variable Configuration:**

```bash
# Set required environment variables for testing

export FLASK_ENV=testing
export FLASK_APP=src/app:create_app
export TESTING=true
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

**Test Database Setup (if applicable):**

```bash
# Create test database (SQLite in-memory)

export DATABASE_URL=sqlite:///:memory:

#### Or use a test PostgreSQL database

export DATABASE_URL=postgresql://test:test@localhost/test_db
```

### 0.9.3 CI/CD Integration Commands

**GitHub Actions Workflow Commands:**

```yaml
# .github/workflows/test.yml snippet

- name: Run Tests
  run: |
    pytest --cov=src/app \
           --cov-report=xml \
           --cov-fail-under=80 \
           --junitxml=test-results.xml
```

**Pre-Commit Hook Commands:**

```bash
# Run tests before commit

pytest tests/unit/ -q --tb=no

#### Quick smoke test

pytest -x -q tests/unit/
```

**Watch Mode Command (Development):**

```bash
# Run tests on file changes (requires pytest-watch)

ptw -- --last-failed --new-first

#### Alternative with pytest-xdist

pytest -f --looponfail
```

### 0.9.4 Test Markers Configuration

**Available Markers:**

```python
# pytest.ini or pyproject.toml markers

markers =
    unit: marks test as unit test (fast, no external deps)
    functional: marks test as functional test (Flask app context)
    integration: marks test as integration test (external services)
    slow: marks test as slow running (>1 second)
    smoke: marks test as smoke test (critical path only)
    wip: marks test as work in progress (skip in CI)
```

**Using Markers:**

```bash
# Run only unit tests

pytest -m unit

#### Run all except slow tests

pytest -m "not slow"

#### Run smoke tests only

pytest -m smoke

#### Skip work in progress tests

pytest -m "not wip"
```

### 0.9.5 Test Output and Reporting

**Console Output Options:**

```bash
# Minimal output (dots)

pytest -q

#### Verbose output (test names)

pytest -v

#### Extra verbose (full test output)

pytest -vv

#### Show local variables in tracebacks

pytest -l

#### Show test durations

pytest --durations=10
```

**Report Generation:**

```bash
# JUnit XML report (CI integration)

pytest --junitxml=reports/junit.xml

#### HTML report (pytest-html plugin)

pytest --html=reports/report.html

#### Coverage HTML report

pytest --cov=src/app --cov-report=html:reports/coverage
```

### 0.9.6 Specific Test Patterns in Repository

**Test Naming Convention:**

```
test_<module>_<function>_<scenario>_<expected>
```

**Examples:**

- `test_models_document_section_valid_data_succeeds`
- `test_routes_health_check_returns_200`
- `test_helper_process_document_invalid_input_raises_error`

**Test File Organization:**

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── unit/
│   ├── __init__.py
│   ├── test_models.py       # Model tests
│   ├── test_state.py        # State tests
│   └── test_helper.py       # Helper tests
├── functional/
│   ├── __init__.py
│   ├── test_routes.py       # Route tests
│   └── test_api.py          # API tests
└── integration/
    ├── __init__.py
    ├── test_pubsub.py       # Pub/Sub tests
    └── test_storage.py      # Storage tests
```

## 0.10 Special Instructions for Testing

### 0.10.1 Testing-Specific Requirements

**Framework Conversion Testing Directive:**

The primary testing objective is to verify that the Flask application correctly implements all functionality from the original Node.js server. This requires:

- **Behavioral Parity Testing:** Each test should verify that the Flask implementation produces the same outputs as the Node.js original for equivalent inputs
- **API Contract Preservation:** All HTTP endpoints must maintain identical request/response schemas
- **Error Response Consistency:** Error codes and messages must match the original behavior

**Minimal Change Principle:**

- **ONLY modify test files and test-related configurations**
- Test additions should not require source code changes unless absolutely necessary for testability
- Prefer dependency injection and configuration-based testing over code modifications

**Source Code Modification Guidelines:**

- **DO NOT modify source code unless absolutely necessary for testability**
- If source modifications are required, document them explicitly with rationale
- Prefer mock injection over code restructuring
- Use application factory pattern to enable testing configuration

### 0.10.2 Test Pattern Directives

**Follow Existing Test Patterns:**

Based on repository analysis, the following patterns should be maintained:

- Use `pytest` as the sole testing framework (no unittest mixing)
- Use fixtures for test setup and teardown (not setUp/tearDown methods)
- Use parametrize for testing multiple scenarios
- Use marks for test categorization

**Test Isolation Requirements:**

- Ensure all tests can run independently and in parallel
- Use function-scoped fixtures by default
- Reset mocks between tests using `mocker.resetall()` or fresh fixture instances
- Do not rely on test execution order

**Mocking Strategy Requirements:**

- **Use `pytest-mock` for external dependencies**
- Mock at the boundary (external service clients, not internal functions)
- Verify mock calls with `assert_called_with` or `call_args`
- Use `MagicMock` for complex return value structures

**Example Mocking Pattern:**

```python
def test_upload_document(mocker, client):
    mock_storage = mocker.patch("src.app.services.storage.Client")
    mock_storage.return_value.bucket.return_value.blob.return_value = MagicMock()
    # Test implementation
```

### 0.10.3 Code Style and Convention Requirements

**Maintain Backward Compatibility in Test Utilities:**

- Test helper functions should support both old and new code paths during migration
- Fixture signatures should be stable and documented
- Avoid breaking changes to shared test utilities

**Match Existing Code Style and Naming Conventions:**

- Function names: `snake_case` (e.g., `test_document_section_valid_data`)
- Class names: `PascalCase` (e.g., `TestDocumentSection`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `SAMPLE_DOCUMENT_DATA`)
- Docstrings: Google style for test documentation

**Assertion Style:**

```python
# Preferred: Simple assertions

assert response.status_code == 200
assert "message" in response.json

#### Avoid: Overly complex assertions

assert response.status_code == 200 and "message" in response.json and response.json["message"] == "ok"
```

### 0.10.4 Flask-Specific Testing Guidelines

**Application Context Management:**

```python
# Always use application context for database operations

def test_database_query(app):
    with app.app_context():
        result = db.session.query(Model).all()
        assert len(result) > 0
```

**Request Context for Route Testing:**

```python
# Use test client for route testing

def test_route(client):
    response = client.get("/api/endpoint")
    assert response.status_code == 200
```

**Configuration Testing:**

```python
# Test with different configurations

@pytest.fixture
def app_with_debug():
    app = create_app({"DEBUG": True, "TESTING": True})
    return app
```

### 0.10.5 Cloud Service Testing Guidelines

**Google Cloud Storage Mocking:**

```python
@pytest.fixture
def mock_gcs(mocker):
    mock_client = mocker.patch("google.cloud.storage.Client")
    mock_bucket = MagicMock()
    mock_client.return_value.bucket.return_value = mock_bucket
    return mock_bucket
```

**Google Cloud Pub/Sub Mocking:**

```python
@pytest.fixture
def mock_pubsub(mocker):
    mock_publisher = mocker.patch("google.cloud.pubsub_v1.PublisherClient")
    mock_publisher.return_value.publish.return_value.result.return_value = "msg-id"
    return mock_publisher
```

**LLM/LangChain Mocking:**

```python
@pytest.fixture
def mock_llm_chain(mocker):
    mock_chain = mocker.patch("langchain.chains.LLMChain")
    mock_chain.return_value.run.return_value = "mocked response"
    return mock_chain
```

### 0.10.6 Continuous Integration Requirements

**CI Test Execution Order:**

1. Lint checks (if configured)
2. Unit tests (fastest feedback)
3. Functional tests
4. Integration tests (slowest)
5. Coverage reporting

**CI Failure Handling:**

- Unit test failures block all subsequent stages
- Integration test failures are reported but may not block (based on configuration)
- Coverage failures generate warnings in development, block in production branches

**Test Artifacts to Preserve:**

- JUnit XML reports for test results
- Coverage XML/HTML reports
- Test logs for failed tests
- Screenshots/recordings (if applicable for E2E)

### 0.10.7 Documentation Requirements

**Required Test Documentation:**

- Each test file must have a module-level docstring describing its purpose
- Complex test fixtures must be documented with usage examples
- Non-obvious test scenarios must include comments explaining the setup

**Example Documentation:**

```python
"""
Test module for DocumentSection model validation.

Tests cover:
- Valid document section creation
- Field validation rules
- Status enum behavior
- Changes list validation based on status
"""

def test_document_section_with_changed_status_requires_changes():
    """
    Verify that a DocumentSection with CHANGED status must have
    a non-empty changes list.
    """
    pass
```

