# Figma Integration Technical Guide

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Main Flows](#main-flows)
3. [Code Navigation Guide](#code-navigation-guide)
4. [Testing Approach](#testing-approach)
5. [Troubleshooting](#troubleshooting)
6. [Code Examples](#code-examples)

---

## Architecture Overview

The Figma integration implements a clean three-layer architecture using **Dependency Injection (DI)** and the **Repository Pattern** to achieve separation of concerns, testability, and maintainability.

### Architectural Layers

```
┌─────────────────────────────────────────────────────────────┐
│                      Route Layer                             │
│  - Request validation                                        │
│  - Authorization checks                                      │
│  - Response formatting                                       │
│  - NO business logic                                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                     Service Layer                            │
│  - Business logic implementation                             │
│  - Transaction coordination                                  │
│  - Uses repositories via interfaces                          │
│  - NO direct external dependencies                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   Repository Layer                           │
│  - Database operations (IFigmaRepository)                    │
│  - Secret Manager operations (ISecretRepository)             │
│  - Figma API calls (IFigmaAPIRepository)                     │
│  - Configuration access (IConfigRepository)                  │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Principles

#### 1. Dependency Injection

The service layer receives repository dependencies through constructor injection, enabling flexible configuration:

```python
class FigmaService:
    def __init__(
        self,
        figma_repo: Optional[IFigmaRepository] = None,
        secret_repo: Optional[ISecretRepository] = None,
        figma_api_repo: Optional[IFigmaAPIRepository] = None,
        config_repo: Optional[IConfigRepository] = None
    ):
        # Use provided repositories or instantiate defaults
        self.figma_repo = figma_repo or FigmaRepository()
        self.secret_repo = secret_repo or SecretRepository()
        self.figma_api_repo = figma_api_repo or FigmaAPIRepository()
        self.config_repo = config_repo or ConfigRepository()
```

**Benefits:**
- Production code uses default implementations (simple instantiation)
- Test code injects fake implementations (full control)
- No need to pass repositories through route handlers
- Single point of configuration per service instance

#### 2. Repository Pattern

All external system interactions are abstracted behind interfaces:

- **IFigmaRepository**: Database operations for `figma_installation`, `figma_installation_access`, and `figma_attachment` tables
- **ISecretRepository**: Google Secret Manager operations (create, read, update, delete secrets)
- **IFigmaAPIRepository**: Figma API interactions (validate PAT, access frames, retrieve metadata)
- **IConfigRepository**: Application configuration access (feature flags, GCP project ID)

**Benefits:**
- Services remain testable without real databases, Secret Manager, or Figma API
- Clear contracts defined by interfaces
- Easy to swap implementations (e.g., local development vs. production)
- Faked repositories enable fast, deterministic unit tests

#### 3. Transaction Consistency

Critical operations maintain consistency between the database and Google Secret Manager through careful transaction management. If Secret Manager operations fail, database changes are rolled back to prevent orphaned records.

**Pattern:**
```python
try:
    with db.transaction():
        # Step 1: Database operation
        installation = figma_repo.create_installation(...)
        
        # Step 2: Secret Manager operation (with retries)
        secret_name = f"figma-secret-{installation.id}"
        secret_repo.create_secret(secret_name, pat, retry_count=3)
        
        # Both succeed: transaction commits automatically
except SecretManagerError:
    # Secret Manager failed: transaction rolls back automatically
    raise
```

### Security Considerations

1. **PAT Storage**: Personal Access Tokens are stored exclusively in Google Secret Manager using the naming pattern `figma-secret-<installation_id>`, never in the application database.

2. **PAT Exposure Prevention**: The actual PAT value is never included in API responses. Only derived status ("Active" or "Expired") is returned.

3. **Role-Based Authorization**: Sharing installations requires ADMIN or SUPER_ADMIN role, verified by querying `teams` and `teammembers` tables.

4. **Feature Flag**: All functionality respects the `FIGMA_INTEGRATION_ENABLED` flag, checked at the route level before processing requests.

---

## Main Flows

### Flow 1: Create Installation

This flow demonstrates transactional consistency between the database and Secret Manager.

**API Endpoint:** `POST /v1/figma/installations`

**Request Body:**
```json
{
  "name": "My Design System",
  "description": "Company design system files",
  "pat": "figd_AbCdEfGhIjKlMnOp...",
  "team_id": 42
}
```

**Detailed Step-by-Step Flow:**

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ POST /v1/figma/installations
       │ { name, description, pat, team_id }
       ▼
┌─────────────────────────────────────────┐
│  Route Handler (figma_routes.py)        │
│  1. Validate request body               │
│  2. Check feature flag enabled          │
│  3. Verify user authentication          │
└──────┬──────────────────────────────────┘
       │ Call create_installation()
       ▼
┌─────────────────────────────────────────┐
│  FigmaService                            │
│  4. Begin database transaction          │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  IFigmaRepository.create_installation()  │
│  5. INSERT INTO figma_installation       │
│  6. Return installation with generated ID│
└──────┬──────────────────────────────────┘
       │ installation.id = 123
       ▼
┌─────────────────────────────────────────┐
│  FigmaService                            │
│  7. Construct secret name:               │
│     "figma-secret-123"                   │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  ISecretRepository.create_secret()       │
│  8. Create secret in Secret Manager      │
│  9. Retry up to 3 times on failure       │
└──────┬──────────────────────────────────┘
       │
       ├─ SUCCESS ─────────────────┐
       │                            │
       ▼                            ▼
┌──────────────────┐      ┌────────────────────┐
│ Commit DB txn    │      │ Rollback DB txn    │
│ Return 201       │      │ Return 500 error   │
└──────────────────┘      └────────────────────┘
```

**Critical Implementation Details:**

- **Transaction Scope**: Database transaction begins before creating the installation record and remains open until Secret Manager confirms storage.
  
- **Secret Naming Convention**: Always follows `figma-secret-{installation_id}` pattern to enable predictable lookups and cleanup.
  
- **Retry Logic**: Secret Manager operations include 3 retry attempts with exponential backoff to handle transient network issues.
  
- **Rollback Trigger**: Any exception from Secret Manager (after retries) triggers immediate transaction rollback, preventing orphaned database records.

**Error Scenarios:**

| Error Condition | System Response |
|----------------|-----------------|
| Invalid PAT format | Return 400, no database write |
| Database constraint violation | Return 409, transaction rolled back |
| Secret Manager failure (after retries) | Return 500, transaction rolled back |
| Secret Manager permission denied | Return 500, transaction rolled back, log IAM issue |

### Flow 2: Share Installation

This flow demonstrates role-based authorization and access control.

**API Endpoint:** `POST /v1/figma/installations/{id}/share`

**Request Body:**
```json
{
  "user_id": 456,
  "access_level": "viewer"
}
```

**Detailed Step-by-Step Flow:**

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ POST /v1/figma/installations/123/share
       │ { user_id: 456, access_level: "viewer" }
       ▼
┌─────────────────────────────────────────┐
│  Route Handler (figma_routes.py)        │
│  1. Validate request body               │
│  2. Extract requesting user from context│
│     requesting_user_id = 789            │
└──────┬──────────────────────────────────┘
       │ Call share_installation()
       ▼
┌─────────────────────────────────────────┐
│  FigmaService.share_installation()       │
│  3. Verify installation exists          │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  Authorization Check                     │
│  4. Query teams table for user 789      │
│  5. Query teammembers for role          │
└──────┬──────────────────────────────────┘
       │
       ├─ Role = ADMIN or SUPER_ADMIN ──┐
       │                                  │
       ▼                                  ▼
┌──────────────────┐           ┌─────────────────┐
│ 6. Grant access  │           │ Return 403      │
│    via           │           │ "Unauthorized"  │
│    grant_access()│           └─────────────────┘
└────┬─────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│  IFigmaRepository.grant_access()         │
│  7. INSERT INTO figma_installation_access│
│     - figma_installation_id = 123       │
│     - user_id = 456                     │
│     - access_level = "viewer"           │
│     - granted_by = 789                  │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  Return 200                              │
│  { access_id, installation_id, user_id } │
└─────────────────────────────────────────┘
```

**Authorization Logic Details:**

The authorization check queries the following tables:

```sql
-- Check if requesting user is ADMIN or SUPER_ADMIN
SELECT tm.role 
FROM teammembers tm
JOIN teams t ON tm.team_id = t.id
WHERE tm.user_id = 789
  AND tm.role IN ('ADMIN', 'SUPER_ADMIN')
  AND tm.deleted_at IS NULL;
```

**Important Behaviors:**

- **Idempotency**: Attempting to grant access to a user who already has access updates the existing record (same installation + user combination).
  
- **Audit Trail**: The `granted_by` field records which administrator granted access, supporting compliance and debugging.
  
- **Soft Delete**: Revoking access sets `deleted_at` timestamp rather than hard-deleting, preserving access history.

### Flow 3: Attach Frames

This flow demonstrates Figma API integration and validation.

**API Endpoint:** `POST /v1/figma/attachments`

**Request Body:**
```json
{
  "project_id": 100,
  "tech_spec_id": 200,
  "installation_id": 123,
  "frames": [
    {
      "url": "https://www.figma.com/file/ABC123/Design?node-id=1:2",
      "description": "Login screen mockup"
    },
    {
      "url": "https://www.figma.com/file/ABC123/Design?node-id=3:4",
      "description": "Dashboard layout"
    }
  ]
}
```

**Detailed Step-by-Step Flow:**

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ POST /v1/figma/attachments
       │ { project_id, installation_id, frames }
       ▼
┌─────────────────────────────────────────┐
│  Route Handler (figma_routes.py)        │
│  1. Validate request body               │
│  2. Verify user has project access      │
└──────┬──────────────────────────────────┘
       │ Call attach_frames()
       ▼
┌─────────────────────────────────────────┐
│  FigmaService.attach_frames()            │
│  3. Retrieve installation record        │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  ISecretRepository.get_secret()          │
│  4. Fetch PAT from Secret Manager:       │
│     secret_name = "figma-secret-123"    │
└──────┬──────────────────────────────────┘
       │ pat = "figd_AbCdEf..."
       │
       │ For each frame in frames:
       ▼
┌─────────────────────────────────────────┐
│  IFigmaAPIRepository.validate_frame_     │
│  access()                                │
│  5. Call Figma API with PAT and URL     │
│  6. Parse file_key and node_id from URL │
│  7. GET /v1/files/{file_key}/nodes      │
│     ?ids={node_id}                      │
└──────┬──────────────────────────────────┘
       │
       ├─ SUCCESS (200 OK) ────┐
       │                        │
       ▼                        ▼
┌──────────────────┐  ┌────────────────────┐
│ Extract title    │  │ Return validation  │
│ from response    │  │ error to client    │
│ frame_title =    │  │ Skip this frame    │
│ "Login Screen"   │  └────────────────────┘
└────┬─────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│  IFigmaRepository.create_attachment()    │
│  8. INSERT INTO figma_attachment OR      │
│     UPDATE if frame_url already exists   │
│     for this project_id                  │
│     - project_id = 100                   │
│     - frame_url = "https://..."          │
│     - frame_title = "Login Screen"       │
│     - description = "Login screen mockup"│
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  Return 201                              │
│  [ { attachment_id, frame_url, title }, ]│
└─────────────────────────────────────────┘
```

**Frame URL Parsing:**

The service extracts the file key and node ID from Figma URLs:

```
https://www.figma.com/file/ABC123/DesignFile?node-id=1:2
                            ^^^^^^              ^^^
                          file_key            node_id
```

**Figma API Call:**

```http
GET https://api.figma.com/v1/files/ABC123/nodes?ids=1:2
Authorization: Bearer figd_AbCdEf...
```

**Response Processing:**

```json
{
  "nodes": {
    "1:2": {
      "document": {
        "name": "Login Screen"
      }
    }
  }
}
```

The `name` field becomes the `frame_title` stored in the database.

**Important Behaviors:**

- **Additive Operation**: Calling this endpoint multiple times with different frames adds them all to the project.
  
- **Idempotent Updates**: If the same `frame_url` is submitted again for the same `project_id`, the existing attachment is updated (description and title refreshed).
  
- **Partial Success**: If one frame validation fails, other frames in the batch are still processed. Response includes both successes and failures.
  
- **No File Downloads**: Only the frame URL, title, and description are stored. No actual Figma files are downloaded or uploaded to GCS.

---

## Code Navigation Guide

This section provides exact file paths for all components of the Figma integration, organized by layer.

### Repository Layer

#### Interfaces (Contracts)

| Interface | File Path | Purpose |
|-----------|-----------|---------|
| IFigmaRepository | `src/repositories/interfaces/i_figma_repository.py` | Defines database operations for figma_installation, figma_installation_access, and figma_attachment tables |
| ISecretRepository | `src/repositories/interfaces/i_secret_repository.py` | Defines Google Secret Manager operations (create, read, update, delete) |
| IFigmaAPIRepository | `src/repositories/interfaces/i_figma_api_repository.py` | Defines Figma API interactions (validate PAT, access frames, metadata) |
| IConfigRepository | `src/repositories/interfaces/i_config_repository.py` | Defines configuration access (feature flags, GCP project ID) |

#### Implementations

| Implementation | File Path | External Dependency |
|----------------|-----------|---------------------|
| FigmaRepository | `src/repositories/figma_repository.py` | PostgreSQL via SQLAlchemy |
| SecretRepository | `src/repositories/secret_repository.py` | Google Secret Manager (`google-cloud-secret-manager`) |
| FigmaAPIRepository | `src/repositories/figma_api_repository.py` | Figma REST API (HTTPS) |
| ConfigRepository | `src/repositories/config_repository.py` | Environment variables, config files |

**Key Methods by Repository:**

**FigmaRepository**
```
create_installation(user_id, name, description, team_id) -> Installation
get_installation(installation_id) -> Optional[Installation]
update_installation(installation_id, **kwargs) -> Installation
soft_delete_installation(installation_id) -> bool
list_installations(user_id, team_id) -> List[Installation]
grant_access(installation_id, user_id, granted_by, access_level) -> Access
revoke_access(installation_id, user_id) -> bool
list_access(installation_id) -> List[Access]
create_attachment(project_id, installation_id, frame_url, created_by, ...) -> Attachment
get_attachment(attachment_id) -> Optional[Attachment]
list_attachments(project_id, tech_spec_id) -> List[Attachment]
soft_delete_attachment(attachment_id) -> bool
```

**SecretRepository**
```
create_secret(secret_name, secret_value, retry_count=3) -> bool
get_secret(secret_name) -> Optional[str]
update_secret(secret_name, secret_value, retry_count=3) -> bool
delete_secret(secret_name, retry_count=3) -> bool
```

**FigmaAPIRepository**
```
validate_pat(pat) -> bool
validate_frame_access(pat, frame_url) -> Dict[str, Any]
get_frame_metadata(pat, frame_url) -> Optional[Dict]
```

**ConfigRepository**
```
get(key, default=None) -> Any
get_bool(key, default=False) -> bool
get_int(key, default=0) -> int
get_project_id() -> str
```

### Service Layer

| Service | File Path | Dependencies |
|---------|-----------|--------------|
| FigmaService | `src/services/figma_service.py` | IFigmaRepository, ISecretRepository, IFigmaAPIRepository, IConfigRepository |

**Key Methods:**
```
create_installation(user_id, name, pat, description, team_id) -> Dict
get_installation(installation_id) -> Dict
update_pat(installation_id, new_pat, user_id) -> Dict
delete_installation(installation_id, user_id) -> bool
share_installation(installation_id, target_user_id, requesting_user_id, access_level) -> Dict
unshare_installation(installation_id, target_user_id, requesting_user_id) -> bool
list_installations(user_id, team_id) -> List[Dict]
validate_frame(frame_url, installation_id) -> Dict
attach_frames(project_id, installation_id, frames, created_by, tech_spec_id) -> List[Dict]
get_attachment(attachment_id) -> Dict
list_attachments(project_id, tech_spec_id) -> List[Dict]
delete_attachment(attachment_id, user_id) -> bool
get_installation_by_project(project_id) -> Dict  # Internal API with PAT included
```

### Route Layer

| Route Module | File Path | Service Used |
|--------------|-----------|--------------|
| Admin Service Routes | `src/routes/figma_routes.py` | FigmaService |

**Endpoints Defined:**

| Method | Endpoint | Handler Function |
|--------|----------|------------------|
| POST | `/v1/figma/installations` | `create_installation()` |
| GET | `/v1/figma/installations` | `list_installations()` |
| GET | `/v1/figma/installations/{id}` | `get_installation(id)` |
| PUT | `/v1/figma/installations/{id}/pat` | `update_pat(id)` |
| DELETE | `/v1/figma/installations/{id}` | `delete_installation(id)` |
| POST | `/v1/figma/installations/{id}/share` | `share_installation(id)` |
| DELETE | `/v1/figma/installations/{id}/share` | `unshare_installation(id)` |
| GET | `/v1/figma/installations/{id}/access` | `list_access(id)` |
| POST | `/v1/figma/frames/validate` | `validate_frame()` |
| POST | `/v1/figma/attachments` | `create_attachments()` |
| GET | `/v1/figma/attachments` | `list_attachments()` |
| GET | `/v1/figma/attachments/{id}` | `get_attachment(id)` |
| DELETE | `/v1/figma/attachments/{id}` | `delete_attachment(id)` |
| GET | `/internal/figma/installations/by-project/{project_id}` | `get_installation_by_project(project_id)` |

### Database Models

| Model | File Path | Table Name |
|-------|-----------|------------|
| FigmaInstallation | `src/models/figma_installation.py` | `figma_installation` |
| FigmaInstallationAccess | `src/models/figma_installation_access.py` | `figma_installation_access` |
| FigmaAttachment | `src/models/figma_attachment.py` | `figma_attachment` |

### Database Migrations

| Migration | File Path | Purpose |
|-----------|-----------|---------|
| Add Figma Tables | `alembic/versions/YYYYMMDD_add_figma_tables.py` | Creates figma_installation, figma_installation_access, and figma_attachment tables with indexes |

### Test Infrastructure

| Component | File Path | Purpose |
|-----------|-----------|---------|
| Fake Figma Repository | `tests/fakes/fake_figma_repository.py` | In-memory implementation for testing |
| Fake Secret Repository | `tests/fakes/fake_secret_repository.py` | In-memory secret storage for testing |
| Fake Figma API Repository | `tests/fakes/fake_figma_api_repository.py` | Configurable Figma API responses |
| Fake Config Repository | `tests/fakes/fake_config_repository.py` | Test configuration values |
| Service Tests | `tests/unit/test_figma_service.py` | Unit tests for FigmaService |
| Route Tests | `tests/unit/test_figma_routes.py` | Unit tests for route handlers |

### Documentation

| Document | File Path | Purpose |
|----------|-----------|---------|
| Technical Guide | `docs/figma_technical_guide.md` | This document |
| Test Guidelines | `docs/TEST.md` | General testing approach (pre-existing) |

---

## Testing Approach

The Figma integration follows the testing guidelines documented in `archie-service-backend/docs/TEST.md`, using **faked repositories** to enable fast, deterministic unit tests without external dependencies.

### Test Philosophy

**Key Principles:**
1. **Unit tests only** (no integration tests initially)
2. **Fake all external dependencies** (databases, Secret Manager, Figma API, configuration)
3. **In-memory state** for fakes to simulate real behavior
4. **Deterministic results** (no network calls, no real databases)
5. **Fast execution** (entire test suite runs in seconds)

### Fake Repository Pattern

Each repository interface has a corresponding fake implementation that maintains in-memory state:

#### Example: FakeSecretRepository

```python
# tests/fakes/fake_secret_repository.py
from typing import Optional, Dict
from src.repositories.interfaces.i_secret_repository import ISecretRepository

class FakeSecretRepository(ISecretRepository):
    """
    In-memory fake for Google Secret Manager operations.
    
    Simulates secret storage without requiring actual GCP access.
    Supports testing both success and failure scenarios.
    """
    
    def __init__(self):
        self._secrets: Dict[str, str] = {}
        self._fail_next_operation = False  # For testing error scenarios
    
    def create_secret(self, secret_name: str, secret_value: str, retry_count: int = 3) -> bool:
        """Simulate creating a secret."""
        if self._fail_next_operation:
            self._fail_next_operation = False
            raise SecretManagerError("Simulated Secret Manager failure")
        
        if secret_name in self._secrets:
            raise SecretManagerError(f"Secret {secret_name} already exists")
        
        self._secrets[secret_name] = secret_value
        return True
    
    def get_secret(self, secret_name: str) -> Optional[str]:
        """Simulate retrieving a secret."""
        return self._secrets.get(secret_name)
    
    def update_secret(self, secret_name: str, secret_value: str, retry_count: int = 3) -> bool:
        """Simulate updating a secret (creates new version)."""
        if self._fail_next_operation:
            self._fail_next_operation = False
            raise SecretManagerError("Simulated Secret Manager failure")
        
        if secret_name not in self._secrets:
            raise SecretManagerError(f"Secret {secret_name} not found")
        
        self._secrets[secret_name] = secret_value
        return True
    
    def delete_secret(self, secret_name: str, retry_count: int = 3) -> bool:
        """Simulate deleting a secret."""
        if self._fail_next_operation:
            self._fail_next_operation = False
            raise SecretManagerError("Simulated Secret Manager failure")
        
        if secret_name in self._secrets:
            del self._secrets[secret_name]
            return True
        return False
    
    # Test helper methods
    def fail_next_operation(self):
        """Configure fake to fail the next operation (for testing error handling)."""
        self._fail_next_operation = True
    
    def reset(self):
        """Reset fake state between tests."""
        self._secrets.clear()
        self._fail_next_operation = False
```

### Writing Tests with Fakes

#### Test Structure

```python
# tests/unit/test_figma_service.py
import pytest
from src.services.figma_service import FigmaService
from tests.fakes.fake_figma_repository import FakeFigmaRepository
from tests.fakes.fake_secret_repository import FakeSecretRepository
from tests.fakes.fake_figma_api_repository import FakeFigmaAPIRepository
from tests.fakes.fake_config_repository import FakeConfigRepository

@pytest.fixture
def figma_repo():
    """Provide fresh FakeFigmaRepository for each test."""
    repo = FakeFigmaRepository()
    yield repo
    repo.reset()

@pytest.fixture
def secret_repo():
    """Provide fresh FakeSecretRepository for each test."""
    repo = FakeSecretRepository()
    yield repo
    repo.reset()

@pytest.fixture
def figma_api_repo():
    """Provide fresh FakeFigmaAPIRepository for each test."""
    repo = FakeFigmaAPIRepository()
    yield repo
    repo.reset()

@pytest.fixture
def config_repo():
    """Provide fresh FakeConfigRepository for each test."""
    return FakeConfigRepository({
        'FIGMA_INTEGRATION_ENABLED': True,
        'GCP_PROJECT_ID': 'test-project-123'
    })

@pytest.fixture
def figma_service(figma_repo, secret_repo, figma_api_repo, config_repo):
    """Provide FigmaService with faked dependencies."""
    return FigmaService(
        figma_repo=figma_repo,
        secret_repo=secret_repo,
        figma_api_repo=figma_api_repo,
        config_repo=config_repo
    )
```

#### Example Test Cases

**Test 1: Successful Installation Creation**

```python
def test_create_installation_success(figma_service, secret_repo):
    """Test that creating installation stores both DB record and secret."""
    # Arrange
    user_id = 1
    name = "My Figma Integration"
    pat = "figd_test_token_12345"
    
    # Act
    result = figma_service.create_installation(
        user_id=user_id,
        name=name,
        pat=pat,
        description="Test installation"
    )
    
    # Assert
    assert result['id'] is not None
    assert result['name'] == name
    assert 'pat' not in result  # PAT should not be in response
    
    # Verify secret was stored
    secret_name = f"figma-secret-{result['id']}"
    stored_pat = secret_repo.get_secret(secret_name)
    assert stored_pat == pat
```

**Test 2: Rollback on Secret Manager Failure**

```python
def test_create_installation_rollback_on_secret_failure(figma_service, figma_repo, secret_repo):
    """Test that DB changes are rolled back when Secret Manager fails."""
    # Arrange
    user_id = 1
    name = "Test Installation"
    pat = "figd_test_token_12345"
    
    # Configure secret repo to fail next operation
    secret_repo.fail_next_operation()
    
    # Act & Assert
    with pytest.raises(SecretManagerError):
        figma_service.create_installation(
            user_id=user_id,
            name=name,
            pat=pat
        )
    
    # Verify no installation was created in DB
    installations = figma_repo.list_installations(user_id=user_id)
    assert len(installations) == 0
```

**Test 3: Authorization Check for Sharing**

```python
def test_share_installation_requires_admin_role(figma_service, figma_repo):
    """Test that only ADMIN or SUPER_ADMIN can share installations."""
    # Arrange
    # Create installation owned by user 1
    installation = figma_repo.create_installation(
        user_id=1,
        name="Test Installation"
    )
    
    # User 2 is a regular user (not admin)
    figma_repo.set_user_role(user_id=2, role='MEMBER')
    
    # Act & Assert
    with pytest.raises(UnauthorizedError):
        figma_service.share_installation(
            installation_id=installation.id,
            target_user_id=3,
            requesting_user_id=2,  # Regular user
            access_level='viewer'
        )
```

**Test 4: Frame Validation with Figma API**

```python
def test_validate_frame_success(figma_service, figma_api_repo):
    """Test validating frame access returns title."""
    # Arrange
    frame_url = "https://www.figma.com/file/ABC123/Design?node-id=1:2"
    installation_id = 1
    
    # Configure fake API to return success
    figma_api_repo.set_response_for_url(
        frame_url,
        valid=True,
        title="Login Screen"
    )
    
    # Act
    result = figma_service.validate_frame(
        frame_url=frame_url,
        installation_id=installation_id
    )
    
    # Assert
    assert result['valid'] is True
    assert result['title'] == "Login Screen"
    assert 'message' not in result
```

### Running Tests

**Execute all Figma tests:**
```bash
pytest tests/unit/test_figma_service.py tests/unit/test_figma_routes.py -v
```

**Run with coverage report:**
```bash
pytest tests/unit/test_figma_service.py \
       tests/unit/test_figma_routes.py \
       --cov=src.services.figma_service \
       --cov=src.routes.figma_routes \
       --cov-report=html
```

**Run specific test:**
```bash
pytest tests/unit/test_figma_service.py::test_create_installation_success -v
```

**Run tests matching pattern:**
```bash
pytest tests/unit/ -k "rollback" -v
```

### Test Coverage Goals

- **Service Layer**: >80% code coverage, focusing on:
  - Happy path scenarios
  - Error handling and rollback logic
  - Authorization checks
  - Edge cases (duplicate records, invalid inputs)

- **Route Layer**: >80% code coverage, focusing on:
  - Request validation
  - Feature flag enforcement
  - Authentication/authorization
  - Response formatting

### Debugging Failed Tests

**Common Issues:**

1. **Fake State Leaking Between Tests**
   - **Symptom**: Tests pass individually but fail when run together
   - **Solution**: Ensure fixtures call `reset()` after each test

2. **Missing Mock Configuration**
   - **Symptom**: Unexpected None values or KeyErrors
   - **Solution**: Configure fake repositories with required data before test execution

3. **Assertion on Internal State**
   - **Symptom**: Tests are brittle and break with refactoring
   - **Solution**: Assert on public interface behavior, not internal implementation

---

## Troubleshooting

### Secret Manager Issues

#### Issue 1: Permission Denied (403) Errors

**Symptom:**
```
google.api_core.exceptions.PermissionDenied: 403 Permission denied on resource project TEST_PROJECT
```

**Cause:** Service account lacks required IAM roles for Secret Manager operations.

**Solution:**

1. Verify the service account being used:
   ```bash
   gcloud auth list
   ```

2. Grant required IAM roles:
   ```bash
   # For full CRUD operations (development/admin)
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
     --role="roles/secretmanager.admin"
   
   # For read-only access (production services)
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
     --role="roles/secretmanager.secretAccessor"
   ```

3. Verify the role assignment:
   ```bash
   gcloud projects get-iam-policy PROJECT_ID \
     --flatten="bindings[].members" \
     --filter="bindings.members:serviceAccount:SERVICE_ACCOUNT_EMAIL"
   ```

#### Issue 2: Secret Not Found

**Symptom:**
```
google.api_core.exceptions.NotFound: 404 Secret [projects/123/secrets/figma-secret-456] not found
```

**Possible Causes:**
- Installation was created but Secret Manager operation failed (inconsistent state)
- Secret was deleted manually outside the application
- Wrong project ID configured

**Solution:**

1. Check if installation exists in database:
   ```sql
   SELECT * FROM figma_installation WHERE id = 456;
   ```

2. If installation exists but secret doesn't, recreate secret:
   - Use the Update PAT API to store a new PAT
   - Or manually create secret via `gcloud`:
     ```bash
     echo -n "NEW_PAT_VALUE" | gcloud secrets create figma-secret-456 \
       --data-file=- \
       --project=PROJECT_ID
     ```

3. Verify project ID configuration:
   ```python
   from src.repositories.config_repository import ConfigRepository
   config = ConfigRepository()
   print(config.get_project_id())  # Should match GCP project
   ```

#### Issue 3: Transaction Rollback Not Working

**Symptom:** Database records created even though Secret Manager operation failed.

**Cause:** Transaction context not properly configured or Secret Manager exception not propagated.

**Debugging Steps:**

1. Verify transaction context is active:
   ```python
   # In figma_service.py
   def create_installation(self, ...):
       print(f"Transaction active: {db.in_transaction()}")  # Should be True
   ```

2. Verify exception propagation:
   ```python
   try:
       secret_repo.create_secret(secret_name, pat, retry_count=3)
   except SecretManagerError as e:
       logger.error(f"Secret Manager failed: {e}")
       raise  # CRITICAL: Must re-raise to trigger rollback
   ```

3. Check database transaction isolation level (should be READ COMMITTED or higher)

### Figma API Issues

#### Issue 4: PAT Validation Fails

**Symptom:** PAT status shows "Expired" even for newly created tokens.

**Possible Causes:**
- PAT revoked in Figma dashboard
- PAT lacks required scopes (e.g., `file_content:read`)
- Figma API rate limiting
- Network connectivity issues

**Solution:**

1. Test PAT manually:
   ```bash
   curl -H "Authorization: Bearer YOUR_PAT" \
     https://api.figma.com/v1/me
   ```

2. Verify PAT scopes in Figma:
   - Go to Figma → Settings → Personal Access Tokens
   - Ensure token has `file_content:read` scope at minimum

3. Check rate limits:
   ```python
   # In figma_api_repository.py logs
   logger.info(f"Rate limit remaining: {response.headers.get('X-RateLimit-Remaining')}")
   ```

4. Implement caching for PAT status to reduce API calls:
   ```python
   # Cache PAT validation results for 5 minutes
   @cached(ttl=300)
   def validate_pat(self, pat: str) -> bool:
       # ... API call ...
   ```

#### Issue 5: Frame URL Parsing Fails

**Symptom:**
```
ValueError: Cannot extract file_key from URL: https://www.figma.com/design/...
```

**Cause:** Figma changed URL format or unsupported URL pattern.

**Solution:**

1. Check current URL format in logs and compare to expected patterns:
   ```
   Expected: https://www.figma.com/file/{file_key}/{title}?node-id={node_id}
   Or: https://www.figma.com/design/{file_key}/{title}?node-id={node_id}
   ```

2. Update URL parsing regex in `figma_api_repository.py`:
   ```python
   import re
   
   def parse_frame_url(self, url: str) -> Dict[str, str]:
       """Extract file_key and node_id from Figma URL."""
       # Support both /file/ and /design/ patterns
       pattern = r'https://www\.figma\.com/(?:file|design)/([^/]+)/[^?]*\?.*node-id=([^&]+)'
       match = re.match(pattern, url)
       if not match:
           raise ValueError(f"Cannot parse Figma URL: {url}")
       return {'file_key': match.group(1), 'node_id': match.group(2)}
   ```

### Database Issues

#### Issue 6: Duplicate Attachment Error

**Symptom:**
```
IntegrityError: duplicate key value violates unique constraint "figma_attachment_project_id_frame_url_key"
```

**Cause:** Attempting to insert attachment with same project_id + frame_url when one already exists (not soft-deleted).

**Expected Behavior:** This should not happen if `create_attachment()` properly implements upsert logic.

**Solution:**

1. Verify upsert implementation in `figma_repository.py`:
   ```python
   def create_attachment(self, project_id, installation_id, frame_url, ...):
       """Create or update attachment (upsert)."""
       # Check for existing attachment
       existing = db.query(FigmaAttachment).filter(
           FigmaAttachment.project_id == project_id,
           FigmaAttachment.frame_url == frame_url,
           FigmaAttachment.deleted_at.is_(None)
       ).first()
       
       if existing:
           # Update existing record
           existing.description = description
           existing.frame_title = frame_title
           existing.updated_at = datetime.utcnow()
           db.flush()
           return existing
       else:
           # Create new record
           attachment = FigmaAttachment(...)
           db.add(attachment)
           db.flush()
           return attachment
   ```

2. If error persists, check for race conditions in concurrent requests (add row-level locking if needed)

#### Issue 7: Soft-Deleted Records Appear in Queries

**Symptom:** Deleted installations or attachments still returned by list APIs.

**Cause:** Queries not filtering by `deleted_at IS NULL`.

**Solution:**

Verify all query methods include soft-delete filter:
```python
def list_installations(self, user_id=None, team_id=None):
    query = db.query(FigmaInstallation).filter(
        FigmaInstallation.deleted_at.is_(None)  # CRITICAL: Filter soft-deleted
    )
    if user_id:
        query = query.filter(FigmaInstallation.user_id == user_id)
    # ... additional filters ...
    return query.all()
```

### Configuration Issues

#### Issue 8: Feature Flag Not Working

**Symptom:** Figma endpoints accessible even when `FIGMA_INTEGRATION_ENABLED=false`.

**Cause:** Feature flag check not implemented or bypassed.

**Solution:**

1. Verify flag value:
   ```python
   from src.repositories.config_repository import ConfigRepository
   config = ConfigRepository()
   print(config.get_bool('FIGMA_INTEGRATION_ENABLED'))
   ```

2. Ensure route handlers check flag:
   ```python
   # In figma_routes.py
   @app.route('/v1/figma/installations', methods=['POST'])
   def create_installation():
       config = ConfigRepository()
       if not config.get_bool('FIGMA_INTEGRATION_ENABLED'):
           return jsonify({'error': 'Figma integration is disabled'}), 404
       # ... rest of handler ...
   ```

3. Consider implementing decorator for reusability:
   ```python
   def require_figma_enabled(f):
       @wraps(f)
       def decorated_function(*args, **kwargs):
           config = ConfigRepository()
           if not config.get_bool('FIGMA_INTEGRATION_ENABLED'):
               return jsonify({'error': 'Figma integration is disabled'}), 404
           return f(*args, **kwargs)
       return decorated_function
   
   @app.route('/v1/figma/installations', methods=['POST'])
   @require_figma_enabled
   def create_installation():
       # ... handler implementation ...
   ```

### Authorization Issues

#### Issue 9: Regular Users Can Share Installations

**Symptom:** Users without ADMIN/SUPER_ADMIN role successfully share installations.

**Cause:** Authorization check not properly implemented or bypassed.

**Solution:**

1. Verify role query in `figma_service.py`:
   ```python
   def share_installation(self, installation_id, target_user_id, requesting_user_id, access_level):
       # Verify requesting user has appropriate role
       user_role = self._get_user_role(requesting_user_id)
       if user_role not in ['ADMIN', 'SUPER_ADMIN']:
           raise UnauthorizedError(f"User {requesting_user_id} lacks permission to share installations")
       # ... rest of method ...
   
   def _get_user_role(self, user_id):
       """Query teams and teammembers for user role."""
       result = db.query(TeamMember.role).filter(
           TeamMember.user_id == user_id,
           TeamMember.deleted_at.is_(None)
       ).first()
       return result.role if result else 'MEMBER'
   ```

2. Add logging for authorization decisions:
   ```python
   logger.info(f"User {requesting_user_id} (role={user_role}) attempting to share installation {installation_id}")
   ```

3. Write test to verify behavior:
   ```python
   def test_share_installation_denies_regular_users(figma_service):
       with pytest.raises(UnauthorizedError):
           figma_service.share_installation(
               installation_id=1,
               target_user_id=2,
               requesting_user_id=3,  # Regular user
               access_level='viewer'
           )
   ```

---

## Code Examples

### Example 1: Service Initialization with Dependency Injection

**Production Code:**
```python
# src/routes/figma_routes.py
from flask import Blueprint, request, jsonify
from src.services.figma_service import FigmaService

figma_bp = Blueprint('figma', __name__)

# Service uses default repository implementations
figma_service = FigmaService()  # Repositories auto-initialized

@figma_bp.route('/v1/figma/installations', methods=['POST'])
def create_installation():
    """Create new Figma installation."""
    data = request.get_json()
    
    try:
        result = figma_service.create_installation(
            user_id=request.user_id,  # From authentication middleware
            name=data['name'],
            pat=data['pat'],
            description=data.get('description'),
            team_id=data.get('team_id')
        )
        return jsonify(result), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

**Test Code:**
```python
# tests/unit/test_figma_routes.py
import pytest
from tests.fakes.fake_figma_repository import FakeFigmaRepository
from tests.fakes.fake_secret_repository import FakeSecretRepository
from tests.fakes.fake_figma_api_repository import FakeFigmaAPIRepository
from tests.fakes.fake_config_repository import FakeConfigRepository
from src.services.figma_service import FigmaService

@pytest.fixture
def test_figma_service():
    """Create FigmaService with faked dependencies for testing."""
    return FigmaService(
        figma_repo=FakeFigmaRepository(),
        secret_repo=FakeSecretRepository(),
        figma_api_repo=FakeFigmaAPIRepository(),
        config_repo=FakeConfigRepository({'FIGMA_INTEGRATION_ENABLED': True})
    )
```

### Example 2: Creating an Installation

**Complete Flow with Error Handling:**

```python
# src/services/figma_service.py
from typing import Dict, Optional
import logging
from src.repositories.interfaces.i_figma_repository import IFigmaRepository
from src.repositories.interfaces.i_secret_repository import ISecretRepository
from src.repositories.figma_repository import FigmaRepository
from src.repositories.secret_repository import SecretRepository

logger = logging.getLogger(__name__)

class FigmaService:
    def __init__(
        self,
        figma_repo: Optional[IFigmaRepository] = None,
        secret_repo: Optional[ISecretRepository] = None,
        # ... other repos ...
    ):
        self.figma_repo = figma_repo or FigmaRepository()
        self.secret_repo = secret_repo or SecretRepository()
    
    def create_installation(
        self,
        user_id: int,
        name: str,
        pat: str,
        description: Optional[str] = None,
        team_id: Optional[int] = None
    ) -> Dict:
        """
        Create Figma installation with transactional Secret Manager storage.
        
        Ensures consistency between database and Secret Manager by rolling back
        database changes if secret storage fails after retries.
        
        :param user_id: Owner of the installation
        :param name: Display name for the installation
        :param pat: Figma Personal Access Token
        :param description: Optional description
        :param team_id: Optional team association
        :return: Installation dict without PAT value
        :raises: SecretManagerError if secret storage fails after retries
        """
        logger.info(f"Creating Figma installation '{name}' for user {user_id}")
        
        # Validate PAT format (basic check)
        if not pat.startswith('figd_'):
            raise ValueError("Invalid PAT format: must start with 'figd_'")
        
        try:
            # Begin database transaction (context-managed)
            with self.figma_repo.transaction():
                # Step 1: Create database record
                installation = self.figma_repo.create_installation(
                    user_id=user_id,
                    name=name,
                    description=description,
                    team_id=team_id
                )
                installation_id = installation.id
                
                logger.info(f"Created installation record with ID {installation_id}")
                
                # Step 2: Store PAT in Secret Manager
                secret_name = f"figma-secret-{installation_id}"
                
                try:
                    self.secret_repo.create_secret(
                        secret_name=secret_name,
                        secret_value=pat,
                        retry_count=3
                    )
                    logger.info(f"Stored secret {secret_name} in Secret Manager")
                except SecretManagerError as e:
                    logger.error(f"Failed to store secret after retries: {e}")
                    # Transaction will rollback automatically when exception propagates
                    raise
                
                # Both operations succeeded - transaction commits automatically
                
                # Return installation without PAT
                return {
                    'id': installation.id,
                    'name': installation.name,
                    'description': installation.description,
                    'user_id': installation.user_id,
                    'team_id': installation.team_id,
                    'status': installation.status,
                    'created_at': installation.created_at.isoformat(),
                    'updated_at': installation.updated_at.isoformat()
                }
                
        except SecretManagerError:
            # Database already rolled back by transaction context
            logger.error(f"Installation creation aborted for user {user_id}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating installation: {e}")
            raise
```

### Example 3: Sharing Installation with Authorization

**Service Method:**

```python
def share_installation(
    self,
    installation_id: int,
    target_user_id: int,
    requesting_user_id: int,
    access_level: str = 'viewer'
) -> Dict:
    """
    Grant user access to Figma installation.
    
    Only ADMIN and SUPER_ADMIN roles can share installations.
    
    :param installation_id: Installation to share
    :param target_user_id: User receiving access
    :param requesting_user_id: User granting access (must be ADMIN/SUPER_ADMIN)
    :param access_level: Access level to grant (viewer, editor, admin)
    :return: Access record dict
    :raises: UnauthorizedError if requesting user lacks permission
    :raises: NotFoundError if installation doesn't exist
    """
    logger.info(f"User {requesting_user_id} sharing installation {installation_id} with user {target_user_id}")
    
    # Step 1: Verify installation exists
    installation = self.figma_repo.get_installation(installation_id)
    if not installation:
        raise NotFoundError(f"Installation {installation_id} not found")
    
    # Step 2: Check authorization - query teams/teammembers for role
    requesting_user_role = self._get_user_role(requesting_user_id)
    
    if requesting_user_role not in ['ADMIN', 'SUPER_ADMIN']:
        logger.warning(f"User {requesting_user_id} (role={requesting_user_role}) denied share attempt")
        raise UnauthorizedError(
            f"Only ADMIN and SUPER_ADMIN users can share installations. Your role: {requesting_user_role}"
        )
    
    logger.info(f"User {requesting_user_id} authorized (role={requesting_user_role})")
    
    # Step 3: Grant access (idempotent - updates existing or creates new)
    access = self.figma_repo.grant_access(
        installation_id=installation_id,
        user_id=target_user_id,
        granted_by=requesting_user_id,
        access_level=access_level
    )
    
    logger.info(f"Access granted: user {target_user_id} can access installation {installation_id} as {access_level}")
    
    return {
        'id': access.id,
        'installation_id': access.installation_id,
        'user_id': access.user_id,
        'access_level': access.access_level,
        'granted_by': access.granted_by,
        'created_at': access.created_at.isoformat()
    }

def _get_user_role(self, user_id: int) -> str:
    """
    Query teams and teammembers tables to determine user's role.
    
    Returns the highest role if user is member of multiple teams.
    """
    from src.models import TeamMember
    
    result = db.query(TeamMember.role).filter(
        TeamMember.user_id == user_id,
        TeamMember.deleted_at.is_(None)
    ).order_by(
        # Order by role priority: SUPER_ADMIN > ADMIN > MEMBER
        db.case(
            (TeamMember.role == 'SUPER_ADMIN', 1),
            (TeamMember.role == 'ADMIN', 2),
            else_=3
        )
    ).first()
    
    return result.role if result else 'MEMBER'
```

### Example 4: Attaching Frames with Validation

**Service Method:**

```python
from typing import List

def attach_frames(
    self,
    project_id: int,
    installation_id: int,
    frames: List[Dict],
    created_by: int,
    tech_spec_id: Optional[int] = None
) -> List[Dict]:
    """
    Attach Figma frames to project after validation.
    
    This operation is additive and idempotent:
    - Multiple calls add more frames
    - Same frame URL overwrites previous attachment
    
    :param project_id: Project to attach frames to
    :param installation_id: Figma installation to use for validation
    :param frames: List of {url, description} dicts
    :param created_by: User creating attachments
    :param tech_spec_id: Optional tech spec association
    :return: List of created/updated attachment dicts
    """
    logger.info(f"Attaching {len(frames)} frames to project {project_id}")
    
    # Step 1: Retrieve installation and PAT
    installation = self.figma_repo.get_installation(installation_id)
    if not installation:
        raise NotFoundError(f"Installation {installation_id} not found")
    
    secret_name = f"figma-secret-{installation_id}"
    pat = self.secret_repo.get_secret(secret_name)
    if not pat:
        raise SecretManagerError(f"PAT not found for installation {installation_id}")
    
    # Step 2: Process each frame
    results = []
    
    for frame in frames:
        frame_url = frame['url']
        description = frame.get('description', '')
        
        try:
            # Step 3: Validate frame access via Figma API
            validation_result = self.figma_api_repo.validate_frame_access(
                pat=pat,
                frame_url=frame_url
            )
            
            if not validation_result['valid']:
                logger.warning(f"Frame validation failed: {validation_result['message']}")
                results.append({
                    'url': frame_url,
                    'success': False,
                    'error': validation_result['message']
                })
                continue
            
            frame_title = validation_result.get('title', '')
            
            # Step 4: Create or update attachment
            attachment = self.figma_repo.create_attachment(
                project_id=project_id,
                installation_id=installation_id,
                frame_url=frame_url,
                created_by=created_by,
                frame_title=frame_title,
                description=description,
                tech_spec_id=tech_spec_id
            )
            
            logger.info(f"Attached frame {frame_url} as attachment {attachment.id}")
            
            results.append({
                'id': attachment.id,
                'url': attachment.frame_url,
                'title': attachment.frame_title,
                'description': attachment.description,
                'success': True
            })
            
        except Exception as e:
            logger.error(f"Error processing frame {frame_url}: {e}")
            results.append({
                'url': frame_url,
                'success': False,
                'error': str(e)
            })
    
    logger.info(f"Attached {sum(1 for r in results if r['success'])} of {len(frames)} frames")
    
    return results
```

**Usage from Route Handler:**

```python
@figma_bp.route('/v1/figma/attachments', methods=['POST'])
def create_attachments():
    """Attach Figma frames to project."""
    data = request.get_json()
    
    # Validate request
    required_fields = ['project_id', 'installation_id', 'frames']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Verify user has project access (authorization)
    if not has_project_access(request.user_id, data['project_id']):
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Delegate to service
    try:
        results = figma_service.attach_frames(
            project_id=data['project_id'],
            installation_id=data['installation_id'],
            frames=data['frames'],
            created_by=request.user_id,
            tech_spec_id=data.get('tech_spec_id')
        )
        return jsonify({'attachments': results}), 201
    except NotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error creating attachments: {e}")
        return jsonify({'error': 'Internal server error'}), 500
```

---

## Summary

This technical guide provides a comprehensive reference for the Figma integration implementation. Key takeaways:

1. **Architecture**: Three-layer design (Routes → Service → Repositories) with dependency injection enables clean separation and testability.

2. **Transactions**: Database and Secret Manager operations are coordinated to maintain consistency, with automatic rollback on failures.

3. **Testing**: Faked repositories allow fast, deterministic unit tests without external dependencies.

4. **Security**: PATs stored exclusively in Secret Manager, never exposed in API responses, with role-based authorization for sharing.

5. **Navigation**: All components organized in clear directory structure with predictable naming conventions.

For questions or issues not covered here, consult:
- `docs/TEST.md` for general testing guidelines
- Source code docstrings for detailed method documentation
- `alembic/versions/` for database schema details
- Repository interfaces in `src/repositories/interfaces/` for API contracts

---

**Document Version**: 1.0  
**Last Updated**: 2024  
**Maintained By**: Platform Engineering Team
