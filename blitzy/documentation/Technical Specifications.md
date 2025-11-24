# Technical Specification

# 0. Agent Action Plan

## 0.1 Executive Summary

Based on the feature requirements, the Blitzy platform understands that the implementation request is to **add comprehensive Figma integration support to the Blitzy platform**, enabling users to connect their Figma accounts, share integrations across teams, attach Figma design frames to projects, and validate access through Personal Access Tokens (PATs).

#### Technical Translation of Requirements

The Blitzy platform has analyzed the requirements and translated them into the following precise technical objectives:

- **Primary Goal**: Implement a complete Figma integration system across multiple microservices (archie-service-admin, archie-service-backend, platform-event-listener) that enables secure storage and management of Figma Personal Access Tokens in Google Secret Manager, role-based access control for sharing integrations, and attachment of Figma design frames to projects with validation

- **Integration Pattern**: The system follows a dual-service architecture where archie-service-admin handles all business logic and database operations, while archie-service-backend acts as a public-facing gateway that performs authorization checks and routes authenticated requests to the admin service

- **Security Model**: <cite index="1-1,1-2">Personal Access Tokens grant access to Figma data through the Figma API</cite>, and these sensitive credentials must be stored in Google Secret Manager with a consistent naming pattern (figma-secret-<installation_id>), never in the application database

- **Access Control**: Integration sharing follows the existing GitHub integration pattern, where only ADMIN and SUPER_ADMIN roles (determined from teams and teammembers tables) can grant or revoke access to Figma installations for other users

- **Data Flow**: Figma frame URLs are validated against the Figma API using the stored PAT, then stored with descriptions as lightweight attachment metadata (URL + description only, no file downloads) that can be filtered by project_id and optionally tech_spec_id

#### Specific Technical Failures Addressed

The implementation must prevent the following failure scenarios:

- **Inconsistent Secret State**: If Google Secret Manager operations fail during create or delete operations, database changes must be rolled back to maintain consistency between the DB and Secret Manager

- **PAT Exposure**: The actual PAT values must never be returned through GET APIs; only PAT status (Active/Expired) should be exposed

- **Unauthorized Access**: Users without ADMIN or SUPER_ADMIN roles must not be able to share or unshare Figma integrations

- **Feature Flag Bypass**: All Figma functionality must respect the FIGMA_INTEGRATION_ENABLED feature flag

- **Code Duplication**: While avoiding refactoring existing code, the new Figma implementation must follow clean architecture patterns with proper dependency injection and repository abstractions

#### Key Architectural Constraints

- Route handlers contain **no business logic** - only request validation and authorization
- Service layer uses **dependency injection** with repositories abstracting all external dependencies
- All external systems (databases, Secret Manager, Figma API, configuration) are accessed through **repository interfaces**
- Services use **default repository implementations** at initialization to avoid explicit passing from routes
- **No refactoring** of existing code to match this pattern - localized implementation for Figma only
- Tests use **faked repositories** based on defined interfaces, following guidelines in archie-service-backend/docs/TEST.md

## 0.2 Requirements Analysis and Technical Scope

#### Comprehensive Feature Breakdown

The Blitzy platform has decomposed the requirements into nine major feature groups, each with specific technical implications:

#### Feature Group A.1: Connect Figma Integration

**Technical Understanding**: Create a new database entity and secure credential storage mechanism

- **Database Schema**: New table `figma_installation` requiring metadata fields to store:
  - Installation ID (primary key, auto-generated)
  - User/Owner reference (foreign key to user/team tables)
  - Installation name/description
  - Created timestamp
  - Updated timestamp
  - Soft delete flag (deleted_at nullable timestamp)
  - PAT status tracking (for determining Active/Expired state)

- **API Contract**: POST endpoint accepting:
  - Figma installation metadata (name, description, owner information)
  - PAT (Personal Access Token) as a required field
  - Returns: Created installation record (without PAT) and success/failure status

- **Secret Management Flow**:
  1. Validate incoming PAT format and requirements
  2. Begin database transaction
  3. Create figma_installation record to obtain installation_id
  4. Construct secret name: `figma-secret-<figma_installation_id>`
  5. Store PAT in Google Secret Manager using constructed name
  6. On Secret Manager success: commit transaction
  7. On Secret Manager failure (after retries): rollback transaction, return error

- **Error Handling**: Must implement retry logic for Secret Manager operations with transaction rollback on ultimate failure

#### Feature Group A.2: Share Figma Integration

**Technical Understanding**: Implement role-based access control for integration sharing

- **Database Schema**: New table `figma_installation_access` with schema matching `github_installation_access`:
  - Installation access ID (primary key)
  - figma_installation_id (foreign key)
  - User ID (who has access)
  - Access level/role
  - Granted by (admin who granted access)
  - Granted timestamp
  - Soft delete support

- **Authorization Logic**:
  - Query `teams` and `teammembers` tables to verify user role
  - Only ADMIN and SUPER_ADMIN roles may execute share/unshare operations
  - Validate that target installation exists and requestor has permission to share it

- **API Operations**:
  - POST `/v1/figma/installations/{id}/share` - Grant access to user(s)
  - DELETE `/v1/figma/installations/{id}/share` - Revoke access from user(s)
  - GET `/v1/figma/installations/{id}/access` - List users with access

#### Feature Group A.3: Disconnect Figma Integration

**Technical Understanding**: Soft delete with coordinated secret cleanup

- **Operation Flow**:
  1. Verify user has permission to delete installation
  2. Begin database transaction
  3. Set deleted_at timestamp on figma_installation record (soft delete)
  4. Construct secret name: `figma-secret-<figma_installation_id>`
  5. Delete secret from Google Secret Manager
  6. On Secret Manager success: commit transaction
  7. On Secret Manager failure (after retries): rollback transaction

- **Critical Requirement**: Database and Secret Manager must remain synchronized - no orphaned secrets or installations

#### Feature Group A.4: Get Figma Integration

**Technical Understanding**: Read operations with derived PAT status

- **PAT Status Determination**:
  - Call Figma API with stored PAT to verify validity
  - Return "Active" if PAT works correctly
  - Return "Expired" if PAT is rejected or invalid
  - Cache status with appropriate TTL to avoid excessive Figma API calls

- **Response Structure**:
  ```
  {
    "id": "<installation_id>",
    "name": "<installation_name>",
    "owner": "<owner_info>",
    "pat_status": "Active|Expired",
    "created_at": "<timestamp>",
    "updated_at": "<timestamp>"
  }
  ```

- **Security Constraint**: The actual PAT value must NEVER be included in API responses

#### Feature Group A.5: Update PAT for Figma Integration

**Technical Understanding**: Atomic update operation for credential rotation

- **Operation Flow**:
  1. Verify user owns or has admin access to installation
  2. Validate new PAT format
  3. Begin database transaction
  4. Update installation record's updated_at timestamp
  5. Update secret in Google Secret Manager (creates new version)
  6. On success: commit transaction
  7. On failure: rollback transaction

#### Feature Group A.6: Feature Flag

**Technical Understanding**: Runtime toggle for Figma functionality

- **Implementation Approach**:
  - Add `FIGMA_INTEGRATION_ENABLED` boolean flag to configuration
  - Check flag at API route level before processing any Figma requests
  - Return 404 or feature-disabled error when flag is false
  - Flag accessible through IConfigRepository interface

#### Feature Group A.7: Attach Figma Files to Project

**Technical Understanding**: Lightweight attachment system with validation

- **Database Schema**: New table `figma_attachments` (or similar) containing:
  - Attachment ID (primary key)
  - project_id (foreign key, required)
  - tech_spec_id (foreign key, optional)
  - figma_installation_id (foreign key, required)
  - frame_url (string, required)
  - description (text, optional)
  - title (string, from Figma API validation)
  - created_by (user ID)
  - created_at / updated_at timestamps
  - deleted_at (soft delete support)

- **API Endpoints**:
  
  **A.7.1.1 Validate API**: `POST /v1/figma/frames/validate`
  - Input: `{ "frame_url": "<url>", "installation_id": "<id>" }`
  - Process: Retrieve PAT from Secret Manager, call Figma API to validate access and retrieve frame title
  - Output: `{ "valid": true/false, "title": "<frame_title>", "message": "<error_message_if_invalid>" }`

  **A.7.1.2 Add API**: `POST /v1/figma/attachments`
  - Input: `{ "project_id": "<id>", "tech_spec_id": "<optional>", "installation_id": "<id>", "frames": [{ "url": "<url>", "description": "<desc>" }] }`
  - Process: Validate each URL, store attachment records
  - Behavior: Additive - can be called multiple times; same frame URL overwrites previous entry
  - Output: List of created/updated attachments

  **A.7.1.3 Delete API**: `DELETE /v1/figma/attachments/{id}`
  - Process: Soft delete attachment record
  - Output: Success confirmation

  **A.7.1.4 Get API**: `GET /v1/figma/attachments?project_id=<id>&tech_spec_id=<optional>`
  - Process: Query attachments by filters
  - Output: List of attachment metadata

  **A.7.1.5 Get Single API**: `GET /v1/figma/attachments/{id}`
  - Process: Retrieve single attachment by ID
  - Output: Attachment metadata

- **Key Constraint**: No file downloads or GCS uploads - only URL and description storage

#### Feature Group A.8: Dual Service Architecture

**Technical Understanding**: Backend-to-Admin service routing pattern

- **Service Responsibilities**:
  - **archie-service-admin**: 
    - Contains ALL business logic implementation
    - Direct database access
    - Direct Secret Manager access
    - Internal-only endpoints
  
  - **archie-service-backend**:
    - Public-facing endpoints at `/v1/figma/*`
    - Authorization checks (user authentication, project access verification)
    - Routes all validated requests to admin service
    - NO business logic duplication

- **Authorization Flow in Backend Service**:
  1. Verify user is authenticated
  2. Verify user has access to referenced project (if applicable)
  3. Forward request to admin service with user context
  4. Return admin service response to client

- **Single Route Handler Module**: All Figma endpoints grouped in one module per service

#### Feature Group A.9: Internal API for PAT Retrieval

**Technical Understanding**: Admin-only endpoint for internal system access

- **Endpoint**: `GET /internal/figma/installations/by-project/{project_id}`
- **Service**: archie-service-admin ONLY
- **Purpose**: Allow internal services to retrieve installation details INCLUDING the actual PAT
- **Security**: Not exposed through backend service, internal network only
- **Use Case**: Platform event listener and other internal services that need to interact with Figma API

#### Technical Implementation Notes Decoded

## B.1: Architectural Pattern (DI + Repository Pattern)

- **Route Layer**: Request validation, authorization, delegation only
- **Service Layer**: Core business logic, no external dependency awareness
- **Repository Layer**: Ports and adapters for all external systems
  - IFigmaRepository / FigmaRepository (database operations)
  - ISecretRepository / SecretRepository (Google Secret Manager)
  - IFigmaAPIRepository / FigmaAPIRepository (Figma API calls)
  - IConfigRepository / ConfigRepository (configuration, replacing consts.py)

- **Dependency Injection**: Services initialized with default repository implementations, allowing test injection of fakes

## B.2: Testing Strategy

- Implement fake repositories based on interfaces
- Follow archie-service-backend/docs/TEST.md guidelines
- Unit tests only (no integration tests initially)
- Test coverage for route handlers and services with faked dependencies

## B.3: Documentation Requirements

- Inline comments explaining "why" not "what"
- reStructuredText (reST) style docstrings for all functions/methods
- Type annotations required
- Create docs/figma_technical_guide.md with:
  - Main flows description
  - Code navigation guide
  - Architecture overview specific to Figma feature

#### Implementation Constraints and Non-Functional Requirements

## C.1: Version Management
- No pyproject.toml version bump required (manual process)

## C.2: Database Migrations
- Generate Alembic migrations for schema changes only
- Ignore legacy `migration` folder

## C.3: Multi-Service Coordination
- Changes required in:
  - archie-service-admin (primary implementation)
  - archie-service-backend (routing and authorization)
  - db-common-models (shared database models)
  - platform-event-listener (potential consumer of internal API)
  - secret-manager utility/service (if separate)

## C.4: UI Integration
- UI implementation already complete
- FIGMA_INTEGRATION_ENABLED flag in UI can be enabled for testing
- Backend must support UI's expected contract

## 0.3 Codebase Analysis & Research Findings

#### Repository Structure Analysis

**Current Repository Status**: The assigned repository contains only a minimal README.md file with content "# Nov18_13". This indicates that either:
- The repository is a placeholder for planning purposes
- The actual implementation repositories (archie-service-admin, archie-service-backend, etc.) are separate codebases
- This is a meta-repository for coordinating multi-repository changes

**Interpretation**: Per the repository investigation guidelines, when user input mentions different repositories, the assigned repository is used for planning while treating mentioned repositories as implementation targets. Therefore, this Agent Action Plan focuses on specifying the precise changes needed across the mentioned service repositories.

#### Web Search Findings - Figma API Integration

**Research Focus**: Understanding Figma Personal Access Token authentication and usage patterns

#### Key Discovery 1: Figma Authentication Mechanisms

<cite index="3-2,3-6">The Figma API supports authentication via access tokens and OAuth2</cite>. For this implementation, Personal Access Tokens (PATs) are the appropriate choice because:

- <cite index="1-1">Personal access tokens allow you to grant access to your data through the Figma API</cite>
- <cite index="2-4,2-5,2-6">Scopes define what resources the personal access token can access, such as file_content:read</cite>
- PATs are simpler than OAuth2 for direct API integration scenarios
- Each user/integration can have its own PAT with specific permissions

#### Key Discovery 2: PAT Security Best Practices

Research revealed critical security considerations for storing and managing PATs:

- <cite index="6-26">Store the Figma Personal Access Token in a secure location, such as a password manager or a secrets management service</cite>
- <cite index="6-27">Periodically rotate the API key to minimize the risk of long-term exposure</cite>
- <cite index="6-31">Utilize secret management tools like CyberArk or AWS Secrets Manager for enhanced security</cite>
- <cite index="6-19">Make sure to copy and securely store your token, as it will not be displayed again for security reasons</cite>

**Implementation Impact**: These findings validate the requirement to store PATs in Google Secret Manager rather than the application database, with support for rotation through the Update PAT API.

#### Key Discovery 3: Figma API Capabilities

<cite index="3-8,3-9">Figma API endpoints allow you to request files, images, file versions, users, comments, team projects and project files, and inspect a JSON representation of the file</cite>. This confirms that:

- Frame URL validation is possible through the Figma API
- Frame metadata (including title) can be retrieved
- PAT validity can be verified by attempting an API call

#### Web Search Findings - Google Secret Manager

**Research Focus**: Understanding Python client library for secure secret storage and retrieval

#### Key Discovery 4: Secret Manager Python Client

The official Google Cloud Secret Manager Python library provides the necessary functionality:

- <cite index="11-2,11-6,11-8">Secret Manager allows you to store, manage, and access secrets as binary blobs or text strings, working well for storing API keys needed by an application at runtime</cite>
- Library: `google-cloud-secret-manager` (install via pip)
- <cite index="14-2,14-4,14-5">Import using `from google.cloud import secretmanager` and create client with `secretmanager.SecretManagerServiceClient()`</cite>

#### Key Discovery 5: Secret Management Operations

Code patterns for required operations:

**Creating Secrets**:
```python
# Pattern from research
client = secretmanager.SecretManagerServiceClient()
parent = f"projects/{project_id}"
secret = client.create_secret(
    request={
        "parent": parent,
        "secret_id": secret_id,
        "secret": {"replication": {"automatic": {}}},
    }
)
version = client.add_secret_version(
    request={"parent": secret.name, "payload": {"data": b"secret_value"}}
)
```

**Retrieving Secrets**:
```python
response = client.access_secret_version(request={"name": version.name})
secret_value = response.payload.data.decode("UTF-8")
```

**Implementation Impact**: The repository pattern (ISecretRepository/SecretRepository) must wrap these operations, providing methods like:
- `create_secret(secret_name: str, secret_value: str) -> bool`
- `get_secret(secret_name: str) -> Optional[str]`
- `update_secret(secret_name: str, secret_value: str) -> bool`
- `delete_secret(secret_name: str) -> bool`

#### Key Discovery 6: Authentication Requirements

<cite index="14-13,14-14">Client libraries support Application Default Credentials (ADC); the libraries look for credentials in a set of defined locations</cite>. This means:
- Local development: Use `gcloud auth application-default login`
- Production: Service account credentials via environment variable
- No explicit credential passing needed in code

#### Key Discovery 7: Common Pitfalls

Research identified important error scenarios:

- <cite index="18-13">A common error is using the project NAME and not the project ID</cite> when constructing resource paths
- Permission denied errors (403) occur when service accounts lack proper IAM roles
- Secrets Manager requires specific IAM roles: `roles/secretmanager.admin` or `roles/secretmanager.secretAccessor`

**Implementation Impact**: 
- Use project_id consistently, not project_name
- Ensure service accounts have appropriate IAM roles
- Implement proper error handling for permission denied scenarios

#### Architecture Pattern Analysis

Based on requirements B.1 (Low-level Design), the implementation must follow:

#### Repository Pattern Structure

**Target File Organization** (to be created in archie-service-admin and archie-service-backend):

```
src/
├── repositories/           # New package for all repositories
│   ├── __init__.py
│   ├── interfaces/        # Repository interface definitions
│   │   ├── i_figma_repository.py
│   │   ├── i_secret_repository.py
│   │   ├── i_figma_api_repository.py
│   │   └── i_config_repository.py
│   ├── figma_repository.py        # DB operations
│   ├── secret_repository.py       # Google Secret Manager
│   ├── figma_api_repository.py    # Figma API calls
│   └── config_repository.py       # Configuration (replaces consts.py)
├── services/
│   └── figma_service.py          # Single service for all Figma logic
└── routes/
    └── figma_routes.py           # Single module for all Figma endpoints
```

#### Dependency Flow

```
Route Handler (figma_routes.py)
    ↓ (validates, authorizes)
    ↓
Service (figma_service.py)
    ↓ (uses injected repositories)
    ↓
Repositories (via interfaces)
    ↓
External Systems (DB, Secret Manager, Figma API, Config)
```

#### Reference Pattern: github_installation_access

Per requirement A.2.4, the figma_installation_access table should follow the schema of github_installation_access. Expected columns based on typical access control patterns:

- `id` - Primary key
- `github_installation_id` → `figma_installation_id` - Foreign key reference
- `user_id` - User who has access
- `access_level` or `role` - Type of access granted
- `granted_by` - Admin user who granted access
- `created_at` - Timestamp when access was granted
- `updated_at` - Timestamp of last update
- `deleted_at` - Soft delete timestamp (nullable)

#### Database Transaction Patterns

Critical requirement from A.1.5 and A.3.3: Database and Secret Manager must remain synchronized.

**Implementation Pattern**:
```python
# Pseudocode for create operation
try:
    # Begin DB transaction
    db.begin_transaction()
    
    # Create DB record
    installation = figma_repo.create_installation(data)
    installation_id = installation.id
    
    # Store secret
    secret_name = f"figma-secret-{installation_id}"
    secret_repo.create_secret(secret_name, pat_value, retry_count=3)
    
    # Commit on success
    db.commit()
    return installation
except SecretManagerError as e:
    # Rollback on Secret Manager failure
    db.rollback()
    raise
except Exception as e:
    db.rollback()
    raise
```

#### Feature Flag Integration

Per requirement A.6, the FIGMA_INTEGRATION_ENABLED flag must be checked at route level:

```python
# Route decorator or middleware pattern
@require_feature_flag("FIGMA_INTEGRATION_ENABLED")
def figma_route_handler():
    # Route implementation
```

#### Research Completeness Summary

| Research Area | Tools Used | Status | Key Findings |
|---------------|------------|--------|--------------|
| Repository Structure | bash, get_source_folder_contents | Complete | Placeholder repository identified |
| Figma API Authentication | web_search | Complete | PAT-based auth pattern confirmed |
| Figma API Capabilities | web_search | Complete | Frame validation and metadata retrieval possible |
| Secret Manager Python SDK | web_search | Complete | Client library patterns documented |
| Secret Security Best Practices | web_search | Complete | Validation for Secret Manager approach |
| Error Handling Patterns | web_search | Complete | Common pitfalls and mitigations identified |

#### Assumptions and Validation Needs

Based on the research, the following assumptions require validation against the actual codebase:

1. **Database ORM**: Assuming SQLAlchemy or similar ORM for transaction management
2. **Existing Repository Pattern**: May exist in current codebase; localize to Figma only per B.1.4
3. **Route Framework**: Assuming Flask or FastAPI for Python web framework
4. **GitHub Pattern Reference**: Actual github_installation_access schema needs verification from real codebase
5. **Configuration System**: Current approach for feature flags and config needs examination
6. **Testing Framework**: pytest assumed based on typical Python project patterns

## 0.4 Implementation Specification

#### Database Schema Specifications

#### Table 1: figma_installation

```sql
CREATE TABLE figma_installation (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,  -- Owner of the installation
    team_id BIGINT,  -- Optional team association
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'active',  -- active, expired, disabled
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP NULL,  -- Soft delete support
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

CREATE INDEX idx_figma_installation_user ON figma_installation(user_id);
CREATE INDEX idx_figma_installation_team ON figma_installation(team_id);
CREATE INDEX idx_figma_installation_deleted ON figma_installation(deleted_at);
```

**Rationale**: The status field enables tracking PAT validity state. Indexes support efficient queries by user, team, and soft-delete filtering.

#### Table 2: figma_installation_access

```sql
CREATE TABLE figma_installation_access (
    id BIGSERIAL PRIMARY KEY,
    figma_installation_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,  -- User who has access
    access_level VARCHAR(50) DEFAULT 'viewer',  -- viewer, editor, admin
    granted_by BIGINT NOT NULL,  -- Admin who granted access
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP NULL,  -- Soft delete support
    FOREIGN KEY (figma_installation_id) REFERENCES figma_installation(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (granted_by) REFERENCES users(id),
    UNIQUE(figma_installation_id, user_id, deleted_at)  -- Prevent duplicate active access
);

CREATE INDEX idx_figma_access_installation ON figma_installation_access(figma_installation_id);
CREATE INDEX idx_figma_access_user ON figma_installation_access(user_id);
CREATE INDEX idx_figma_access_deleted ON figma_installation_access(deleted_at);
```

**Rationale**: Mirrors github_installation_access pattern with role-based access control. Unique constraint prevents duplicate access grants while allowing soft delete history.

#### Table 3: figma_attachment

```sql
CREATE TABLE figma_attachment (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL,
    tech_spec_id BIGINT NULL,  -- Optional association
    figma_installation_id BIGINT NOT NULL,
    frame_url TEXT NOT NULL,
    frame_title VARCHAR(500),  -- Retrieved from Figma API
    description TEXT,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP NULL,  -- Soft delete support
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (tech_spec_id) REFERENCES tech_specs(id),
    FOREIGN KEY (figma_installation_id) REFERENCES figma_installation(id),
    FOREIGN KEY (created_by) REFERENCES users(id),
    UNIQUE(project_id, frame_url, deleted_at)  -- Prevent duplicate frame URLs per project
);

CREATE INDEX idx_figma_attachment_project ON figma_attachment(project_id);
CREATE INDEX idx_figma_attachment_techspec ON figma_attachment(tech_spec_id);
CREATE INDEX idx_figma_attachment_installation ON figma_attachment(figma_installation_id);
CREATE INDEX idx_figma_attachment_deleted ON figma_attachment(deleted_at);
```

**Rationale**: Lightweight storage for frame metadata only. Unique constraint ensures same frame URL can only exist once per project (last write wins on updates).

#### Repository Interface Definitions

#### Interface 1: IFigmaRepository

```python
from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import datetime

class IFigmaRepository(ABC):
    """
    Repository interface for Figma installation database operations.
    
    Abstracts all database interactions for Figma entities to enable
    testability and maintain separation of concerns.
    """
    
    @abstractmethod
    def create_installation(
        self,
        user_id: int,
        name: str,
        description: Optional[str] = None,
        team_id: Optional[int] = None
    ) -> FigmaInstallation:
        """Create a new Figma installation record."""
        pass
    
    @abstractmethod
    def get_installation(self, installation_id: int) -> Optional[FigmaInstallation]:
        """Retrieve installation by ID, excluding soft-deleted records."""
        pass
    
    @abstractmethod
    def update_installation(
        self,
        installation_id: int,
        **kwargs
    ) -> FigmaInstallation:
        """Update installation fields."""
        pass
    
    @abstractmethod
    def soft_delete_installation(self, installation_id: int) -> bool:
        """Soft delete installation by setting deleted_at timestamp."""
        pass
    
    @abstractmethod
    def list_installations(
        self,
        user_id: Optional[int] = None,
        team_id: Optional[int] = None
    ) -> List[FigmaInstallation]:
        """List installations with optional filters."""
        pass
    
    @abstractmethod
    def grant_access(
        self,
        installation_id: int,
        user_id: int,
        granted_by: int,
        access_level: str = "viewer"
    ) -> FigmaInstallationAccess:
        """Grant user access to installation."""
        pass
    
    @abstractmethod
    def revoke_access(self, installation_id: int, user_id: int) -> bool:
        """Revoke user access (soft delete)."""
        pass
    
    @abstractmethod
    def list_access(self, installation_id: int) -> List[FigmaInstallationAccess]:
        """List all users with access to installation."""
        pass
    
    @abstractmethod
    def create_attachment(
        self,
        project_id: int,
        installation_id: int,
        frame_url: str,
        created_by: int,
        frame_title: Optional[str] = None,
        description: Optional[str] = None,
        tech_spec_id: Optional[int] = None
    ) -> FigmaAttachment:
        """Create or update frame attachment."""
        pass
    
    @abstractmethod
    def get_attachment(self, attachment_id: int) -> Optional[FigmaAttachment]:
        """Retrieve single attachment by ID."""
        pass
    
    @abstractmethod
    def list_attachments(
        self,
        project_id: int,
        tech_spec_id: Optional[int] = None
    ) -> List[FigmaAttachment]:
        """List attachments filtered by project and optionally tech_spec."""
        pass
    
    @abstractmethod
    def soft_delete_attachment(self, attachment_id: int) -> bool:
        """Soft delete attachment."""
        pass
```

#### Interface 2: ISecretRepository

```python
from abc import ABC, abstractmethod
from typing import Optional

class ISecretRepository(ABC):
    """
    Repository interface for Google Secret Manager operations.
    
    Abstracts secret storage operations to enable testing with fakes
    and isolate Secret Manager SDK dependencies.
    """
    
    @abstractmethod
    def create_secret(
        self,
        secret_name: str,
        secret_value: str,
        retry_count: int = 3
    ) -> bool:
        """
        Create a new secret in Secret Manager.
        
        :param secret_name: Name following pattern figma-secret-<installation_id>
        :param secret_value: The PAT to store
        :param retry_count: Number of retry attempts on failure
        :return: True if successful, raises exception on failure
        :raises: SecretManagerError after retry exhaustion
        """
        pass
    
    @abstractmethod
    def get_secret(self, secret_name: str) -> Optional[str]:
        """
        Retrieve secret value from Secret Manager.
        
        :param secret_name: Name following pattern figma-secret-<installation_id>
        :return: Secret value or None if not found
        """
        pass
    
    @abstractmethod
    def update_secret(
        self,
        secret_name: str,
        secret_value: str,
        retry_count: int = 3
    ) -> bool:
        """
        Update existing secret (creates new version).
        
        :param secret_name: Name following pattern figma-secret-<installation_id>
        :param secret_value: New PAT value
        :param retry_count: Number of retry attempts on failure
        :return: True if successful, raises exception on failure
        """
        pass
    
    @abstractmethod
    def delete_secret(
        self,
        secret_name: str,
        retry_count: int = 3
    ) -> bool:
        """
        Delete secret from Secret Manager.
        
        :param secret_name: Name following pattern figma-secret-<installation_id>
        :param retry_count: Number of retry attempts on failure
        :return: True if successful, raises exception on failure
        """
        pass
```

#### Interface 3: IFigmaAPIRepository

```python
from abc import ABC, abstractmethod
from typing import Dict, Optional

class IFigmaAPIRepository(ABC):
    """
    Repository interface for Figma API operations.
    
    Abstracts external Figma API calls to enable testing and
    isolate HTTP client dependencies.
    """
    
    @abstractmethod
    def validate_pat(self, pat: str) -> bool:
        """
        Validate PAT by making test API call.
        
        :param pat: Personal Access Token to validate
        :return: True if PAT is valid and active
        """
        pass
    
    @abstractmethod
    def validate_frame_access(
        self,
        pat: str,
        frame_url: str
    ) -> Dict[str, any]:
        """
        Validate PAT has access to frame and retrieve metadata.
        
        :param pat: Personal Access Token
        :param frame_url: Figma frame URL to validate
        :return: Dict with keys: valid (bool), title (str), message (str)
        """
        pass
    
    @abstractmethod
    def get_frame_metadata(self, pat: str, frame_url: str) -> Optional[Dict]:
        """
        Retrieve frame metadata from Figma API.
        
        :param pat: Personal Access Token
        :param frame_url: Figma frame URL
        :return: Frame metadata dict or None
        """
        pass
```

#### Interface 4: IConfigRepository

```python
from abc import ABC, abstractmethod
from typing import Any

class IConfigRepository(ABC):
    """
    Repository interface for application configuration.
    
    Replaces direct usage of consts.py to enable testing with
    different configuration values.
    """
    
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve configuration value.
        
        :param key: Configuration key (e.g., 'FIGMA_INTEGRATION_ENABLED')
        :param default: Default value if key not found
        :return: Configuration value
        """
        pass
    
    @abstractmethod
    def get_bool(self, key: str, default: bool = False) -> bool:
        """Retrieve boolean configuration value."""
        pass
    
    @abstractmethod
    def get_int(self, key: str, default: int = 0) -> int:
        """Retrieve integer configuration value."""
        pass
    
    @abstractmethod
    def get_project_id(self) -> str:
        """Retrieve GCP project ID for Secret Manager operations."""
        pass
```

#### Service Layer Specification

#### FigmaService Implementation

```python
from typing import Optional, List, Dict
from .repositories.interfaces.i_figma_repository import IFigmaRepository
from .repositories.interfaces.i_secret_repository import ISecretRepository
from .repositories.interfaces.i_figma_api_repository import IFigmaAPIRepository
from .repositories.interfaces.i_config_repository import IConfigRepository

class FigmaService:
    """
    Core business logic for Figma integration feature.
    
    Coordinates operations across multiple repositories while maintaining
    transactional consistency between database and Secret Manager.
    """
    
    def __init__(
        self,
        figma_repo: Optional[IFigmaRepository] = None,
        secret_repo: Optional[ISecretRepository] = None,
        figma_api_repo: Optional[IFigmaAPIRepository] = None,
        config_repo: Optional[IConfigRepository] = None
    ):
        """
        Initialize service with repository dependencies.
        
        If no repositories provided, instantiate default implementations.
        This enables explicit injection for testing while keeping
        route handlers simple.
        """
        self.figma_repo = figma_repo or FigmaRepository()
        self.secret_repo = secret_repo or SecretRepository()
        self.figma_api_repo = figma_api_repo or FigmaAPIRepository()
        self.config_repo = config_repo or ConfigRepository()
    
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
        
        CRITICAL: Maintains consistency between DB and Secret Manager.
        On Secret Manager failure, DB changes are rolled back.
        """
        # Implementation coordinates transaction between figma_repo and secret_repo
        pass
    
    def get_installation(self, installation_id: int) -> Dict:
        """
        Retrieve installation with computed PAT status.
        
        SECURITY: Never includes actual PAT value in response.
        """
        pass
    
    def update_pat(
        self,
        installation_id: int,
        new_pat: str,
        user_id: int
    ) -> Dict:
        """
        Update PAT with transactional Secret Manager update.
        
        Verifies user authorization and maintains consistency.
        """
        pass
    
    def delete_installation(self, installation_id: int, user_id: int) -> bool:
        """
        Soft delete installation with Secret Manager cleanup.
        
        CRITICAL: Maintains consistency between DB and Secret Manager.
        """
        pass
    
    def share_installation(
        self,
        installation_id: int,
        target_user_id: int,
        requesting_user_id: int,
        access_level: str = "viewer"
    ) -> Dict:
        """
        Share installation with user if requestor has ADMIN/SUPER_ADMIN role.
        
        AUTHORIZATION: Queries teams/teammembers for role validation.
        """
        pass
    
    def validate_frame(
        self,
        frame_url: str,
        installation_id: int
    ) -> Dict:
        """
        Validate frame URL access through Figma API.
        
        Returns validation status, frame title, and error message if invalid.
        """
        pass
    
    def attach_frames(
        self,
        project_id: int,
        installation_id: int,
        frames: List[Dict],
        created_by: int,
        tech_spec_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Attach Figma frames to project (additive, idempotent).
        
        Same frame URL overwrites previous attachment.
        """
        pass
    
    # Additional methods for complete CRUD operations
```

#### API Route Specifications

#### archie-service-admin Routes

**Module**: `src/routes/figma_routes.py`

```python
# POST /v1/figma/installations
def create_installation():
    """
    Create new Figma installation.
    
    Request: { name, description, pat, team_id? }
    Response: { id, name, status, created_at, ... } (no PAT)
    """
    pass

#### GET /v1/figma/installations/{id}
def get_installation(id):
    """Retrieve installation with PAT status (Active/Expired)."""
    pass

#### PUT /v1/figma/installations/{id}/pat
def update_pat(id):
    """Update PAT for installation."""
    pass

#### DELETE /v1/figma/installations/{id}
def delete_installation(id):
    """Soft delete installation and remove secret."""
    pass

#### POST /v1/figma/installations/{id}/share
def share_installation(id):
    """Grant access to users (ADMIN/SUPER_ADMIN only)."""
    pass

#### DELETE /v1/figma/installations/{id}/share
def revoke_access(id):
    """Revoke user access (ADMIN/SUPER_ADMIN only)."""
    pass

#### POST /v1/figma/frames/validate
def validate_frame():
    """Validate frame URL and retrieve title."""
    pass

#### POST /v1/figma/attachments
def create_attachments():
    """Attach frames to project."""
    pass

#### GET /v1/figma/attachments
def list_attachments():
    """List attachments by project_id and tech_spec_id."""
    pass

#### GET /v1/figma/attachments/{id}
def get_attachment(id):
    """Get single attachment by ID."""
    pass

#### DELETE /v1/figma/attachments/{id}
def delete_attachment(id):
    """Soft delete attachment."""
    pass

#### GET /internal/figma/installations/by-project/{project_id}
def get_installation_by_project(project_id):
    """
    INTERNAL ONLY: Retrieve installation with actual PAT for project.
    
    Used by platform-event-listener and other internal services.
    NOT exposed through backend service.
    """
    pass
```

#### archie-service-backend Routes

**Module**: `src/routes/figma_routes.py`

```python
# All public endpoints mirrored from admin service
# Each route performs:
# 1. Feature flag check (FIGMA_INTEGRATION_ENABLED)
# 2. User authentication verification
# 3. Project access authorization (where applicable)
# 4. Forward request to admin service
# 5. Return admin service response

#### NO business logic duplication
#### NO direct database access
#### NO direct Secret Manager access
```

#### Transaction Management Pattern

**Critical Implementation**: Ensure atomic operations between DB and Secret Manager

```python
def create_installation_with_transaction(data, pat):
    """
    Example transaction pattern for create operation.
    
    Demonstrates rollback on Secret Manager failure to maintain
    consistency between database and external secret storage.
    """
    try:
        # Start database transaction
        with db.transaction():
            # Step 1: Create DB record
            installation = figma_repo.create_installation(
                user_id=data['user_id'],
                name=data['name'],
                description=data.get('description')
            )
            
            # Step 2: Store secret (with retries)
            secret_name = f"figma-secret-{installation.id}"
            try:
                secret_repo.create_secret(
                    secret_name=secret_name,
                    secret_value=pat,
                    retry_count=3
                )
            except SecretManagerError:
                # Secret Manager failed after retries
                # Transaction context will rollback DB changes
                raise
            
            # Both operations succeeded - commit happens automatically
            return installation
            
    except SecretManagerError as e:
        # Log error with context
        logger.error(f"Failed to store PAT for installation {data['name']}: {e}")
        raise APIError("Unable to complete installation creation", 500)
    except Exception as e:
        logger.error(f"Unexpected error creating installation: {e}")
        raise
```

#### Error Response Specifications

**Standard Error Format**:
```json
{
    "error": {
        "code": "ERROR_CODE",
        "message": "Human-readable error message",
        "details": { }
    }
}
```

**Error Codes**:
- `FEATURE_DISABLED`: FIGMA_INTEGRATION_ENABLED is false
- `UNAUTHORIZED`: User not authenticated or lacks permission
- `INSTALLATION_NOT_FOUND`: Installation ID does not exist
- `PAT_STORAGE_FAILED`: Secret Manager operation failed
- `INVALID_PAT`: PAT format or value invalid
- `FRAME_VALIDATION_FAILED`: Cannot access frame with provided PAT
- `DUPLICATE_FRAME`: Frame already attached to project

## 0.5 Scope Boundaries

#### Changes Required (EXHAUSTIVE LIST)

#### Repository 1: archie-service-admin

**New Files to Create**:

- `src/repositories/__init__.py` - Repository package initialization
- `src/repositories/interfaces/__init__.py` - Interface package initialization
- `src/repositories/interfaces/i_figma_repository.py` - Figma database operations interface
- `src/repositories/interfaces/i_secret_repository.py` - Secret Manager operations interface
- `src/repositories/interfaces/i_figma_api_repository.py` - Figma API operations interface
- `src/repositories/interfaces/i_config_repository.py` - Configuration access interface
- `src/repositories/figma_repository.py` - Figma database repository implementation
- `src/repositories/secret_repository.py` - Google Secret Manager repository implementation
- `src/repositories/figma_api_repository.py` - Figma API client repository implementation
- `src/repositories/config_repository.py` - Configuration repository implementation
- `src/services/figma_service.py` - Core Figma business logic service
- `src/routes/figma_routes.py` - All Figma API endpoints for admin service
- `src/models/figma_installation.py` - SQLAlchemy model for figma_installation table (if not in db-common-models)
- `src/models/figma_installation_access.py` - SQLAlchemy model for figma_installation_access table
- `src/models/figma_attachment.py` - SQLAlchemy model for figma_attachment table
- `tests/fakes/fake_figma_repository.py` - Test fake for IFigmaRepository
- `tests/fakes/fake_secret_repository.py` - Test fake for ISecretRepository
- `tests/fakes/fake_figma_api_repository.py` - Test fake for IFigmaAPIRepository
- `tests/fakes/fake_config_repository.py` - Test fake for IConfigRepository
- `tests/unit/test_figma_service.py` - Unit tests for FigmaService
- `tests/unit/test_figma_routes.py` - Unit tests for route handlers
- `docs/figma_technical_guide.md` - Technical implementation guide for Figma feature

**Files to Modify**:

- `src/routes/__init__.py` - Register figma_routes blueprint
- `requirements.txt` or `pyproject.toml` - Add google-cloud-secret-manager dependency
- `alembic/versions/YYYYMMDD_add_figma_tables.py` - Database migration for new tables
- Configuration file (e.g., `config.py`, `.env.example`) - Add FIGMA_INTEGRATION_ENABLED flag

**Lines of Code Estimate**: ~1,500-2,000 lines across all files

#### Repository 2: archie-service-backend

**New Files to Create**:

- `src/routes/figma_routes.py` - Public-facing Figma endpoints with authorization
- `tests/unit/test_figma_routes.py` - Unit tests for route authorization

**Files to Modify**:

- `src/routes/__init__.py` - Register figma_routes blueprint
- `src/services/admin_client.py` (or equivalent) - Add methods for routing to admin service
- Configuration file - Add FIGMA_INTEGRATION_ENABLED flag, admin service URL

**Lines of Code Estimate**: ~300-400 lines

#### Repository 3: db-common-models (if separate package)

**New Files to Create**:

- `models/figma_installation.py` - Shared SQLAlchemy model
- `models/figma_installation_access.py` - Shared SQLAlchemy model
- `models/figma_attachment.py` - Shared SQLAlchemy model

**Files to Modify**:

- `__init__.py` - Export new models
- `alembic/versions/YYYYMMDD_add_figma_tables.py` - Database migration

**Lines of Code Estimate**: ~200-300 lines

#### Repository 4: platform-event-listener

**Files to Modify** (if integration needed):

- Event handlers that might need to fetch Figma installations
- Configuration to add admin service internal API URL
- HTTP client to call `/internal/figma/installations/by-project/{project_id}`

**Lines of Code Estimate**: ~50-100 lines (if changes needed)

#### Summary Table

| Repository | New Files | Modified Files | Est. LOC | Priority |
|------------|-----------|----------------|----------|----------|
| archie-service-admin | 21 | 4 | 1,500-2,000 | CRITICAL |
| archie-service-backend | 2 | 3 | 300-400 | CRITICAL |
| db-common-models | 3 | 2 | 200-300 | CRITICAL |
| platform-event-listener | 0 | 2-3 | 50-100 | OPTIONAL |

#### Explicitly Excluded from Scope

#### DO NOT Modify:

- **Any existing services or repositories** - Per requirement B.1.5, do not refactor existing code to match the new repository pattern. Code duplication between old and new patterns is acceptable and expected.

- **attachment_metadata table and related code** - Requirement A.7.2 explicitly states to create new tables and APIs, not reuse existing attachment infrastructure.

- **consts.py for Figma code** - Create IConfigRepository instead; however, consts.py itself is not modified, just avoided in new Figma code.

- **github_installation or github_installation_access tables** - These are reference patterns only; do not modify GitHub-related code.

- **Legacy migration folder** - Per requirement C.2, ignore completely; use Alembic only.

- **pyproject.toml version field** - Per requirement C.1, version bumps are manual; do not auto-increment.

#### DO NOT Refactor:

- Existing route handlers to match new pattern
- Existing services to use dependency injection
- Existing database access code to use repository pattern
- Existing configuration access to use IConfigRepository

**Rationale**: Localized implementation minimizes risk and prevents scope creep. The new pattern is proven with Figma, then can be adopted elsewhere in future work.

#### DO NOT Add (Beyond Core Requirements):

- OAuth 2.0 authentication flow - Only Personal Access Token support required
- Figma file synchronization or caching - Only URL storage required
- Automatic PAT rotation - Manual update API only
- Figma webhook listeners - Out of scope for initial implementation
- Real-time PAT validation - Status computed on-demand only
- Bulk operations APIs - Single-item operations sufficient
- Figma organization management - Individual user PATs only
- Advanced access control (e.g., project-level permissions) - Installation-level sharing only
- UI components - UI already complete per requirement C.4
- Integration tests - Unit tests only per requirement B.2.3
- Performance optimization - Functional implementation priority
- Comprehensive monitoring dashboards - Standard logging sufficient

#### DO NOT Implement:

- Download Figma files to GCS - Per A.7.2, store URLs only
- Generate thumbnails or previews - Out of scope
- Version control for attached frames - Store current reference only
- Figma plugin development - Server-side only
- Collaboration features between Figma and Blitzy - Read-only integration

#### Scope Verification Checklist

Before marking implementation complete, verify:

- [ ] All 9 feature groups (A.1 through A.9) implemented
- [ ] All 3 database tables created with proper indexes
- [ ] All 4 repository interfaces defined
- [ ] All 4 repository implementations created
- [ ] FigmaService implements all required methods
- [ ] Admin service has all 12 route endpoints
- [ ] Backend service has all public route endpoints
- [ ] Feature flag respected in all routes
- [ ] Transaction consistency between DB and Secret Manager
- [ ] PAT never exposed in GET responses
- [ ] Role-based authorization for sharing
- [ ] Unit tests for services and routes
- [ ] Test fakes for all repository interfaces
- [ ] Technical guide document created
- [ ] Alembic migration generated
- [ ] google-cloud-secret-manager dependency added
- [ ] No existing code refactored
- [ ] No legacy migration folder touched
- [ ] No pyproject.toml version bump

#### Integration Points and Dependencies

**External Services**:
- Google Secret Manager - Must be enabled in GCP project
- Figma API - No account setup required (users provide their PATs)

**Internal Services**:
- archie-service-admin (port 8000 assumed) - Primary implementation
- archie-service-backend (port 8080 assumed) - Public gateway
- PostgreSQL database - Must have schemas for new tables
- IAM service - For user role verification (ADMIN/SUPER_ADMIN)

**Shared Resources**:
- db-common-models package - Must be updated and redeployed
- teams and teammembers tables - Read-only access for authorization
- projects and tech_specs tables - Read-only access for validation
- users table - Read-only access for ownership/access tracking

#### Testing Boundaries

**In Scope for Testing**:
- Unit tests for FigmaService with faked repositories
- Unit tests for route handlers with faked services
- Test coverage for happy path and error scenarios
- Transaction rollback verification with fakes

**Out of Scope for Testing**:
- Integration tests with real Secret Manager
- Integration tests with real Figma API
- End-to-end tests with UI
- Load testing or performance benchmarks
- Security penetration testing
- Cross-browser testing (no UI changes)

**Test File Organization**:
```
tests/
├── fakes/
│   ├── fake_figma_repository.py
│   ├── fake_secret_repository.py
│   ├── fake_figma_api_repository.py
│   └── fake_config_repository.py
├── unit/
│   ├── test_figma_service.py
│   └── test_figma_routes.py
└── conftest.py  # Shared fixtures
```

## 0.6 Testing & Validation Strategy

#### Unit Testing Approach

Per requirement B.2, testing follows the guidelines in archie-service-backend/docs/TEST.md with a focus on unit tests using faked repositories.

#### Test Fake Implementation Pattern

Each repository interface requires a corresponding fake that maintains in-memory state:

```python
# Example: FakeFigmaRepository
class FakeFigmaRepository(IFigmaRepository):
    """
    In-memory fake for testing Figma database operations.
    
    Maintains state across test operations to simulate database
    behavior without actual database dependency.
    """
    
    def __init__(self):
        self._installations = {}  # id -> installation
        self._access_records = {}  # id -> access
        self._attachments = {}  # id -> attachment
        self._next_id = 1
    
    def create_installation(self, user_id, name, description=None, team_id=None):
        installation_id = self._next_id
        self._next_id += 1
        installation = {
            'id': installation_id,
            'user_id': user_id,
            'name': name,
            'description': description,
            'team_id': team_id,
            'status': 'active',
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'deleted_at': None
        }
        self._installations[installation_id] = installation
        return installation
    
    # Additional methods mimic database behavior
```

**Key Principles for Fakes**:
- Maintain internal state that persists across method calls within a test
- Simulate database constraints (uniqueness, foreign keys)
- Support filtering and query operations
- Reset state between tests using fixtures
- Raise appropriate exceptions for error conditions

#### Test Coverage Requirements

**FigmaService Tests** (`tests/unit/test_figma_service.py`):

- **Create Installation**:
  - Successfully creates installation and stores secret
  - Rolls back on Secret Manager failure
  - Validates PAT format before storage
  - Returns installation without PAT in response

- **Get Installation**:
  - Retrieves installation with computed PAT status
  - Returns Active when PAT validates successfully
  - Returns Expired when PAT fails validation
  - Returns 404 for non-existent installation
  - Excludes soft-deleted installations

- **Update PAT**:
  - Successfully updates secret in Secret Manager
  - Rolls back on Secret Manager failure
  - Verifies user authorization before update
  - Updates installation timestamp

- **Delete Installation**:
  - Soft deletes installation record
  - Removes secret from Secret Manager
  - Rolls back on Secret Manager failure
  - Verifies user authorization

- **Share Installation**:
  - Grants access when requestor is ADMIN
  - Grants access when requestor is SUPER_ADMIN
  - Denies access for non-admin users
  - Prevents duplicate access grants
  - Records granted_by user

- **Validate Frame**:
  - Returns valid=true with title for accessible frames
  - Returns valid=false with message for inaccessible frames
  - Handles Figma API errors gracefully
  - Retrieves PAT from Secret Manager for validation

- **Attach Frames**:
  - Creates new attachments for unique URLs
  - Updates existing attachments (same URL, same project)
  - Associates with tech_spec_id when provided
  - Validates frame access before attachment
  - Handles multiple frames in single request

**Route Handler Tests** (`tests/unit/test_figma_routes.py`):

- **Feature Flag Enforcement**:
  - Returns appropriate error when FIGMA_INTEGRATION_ENABLED=false
  - Processes requests when flag=true

- **Request Validation**:
  - Rejects requests with missing required fields
  - Rejects requests with invalid data types
  - Validates field formats (URLs, IDs)

- **Authorization**:
  - Rejects unauthenticated requests
  - Verifies user owns or has access to resources
  - Enforces ADMIN/SUPER_ADMIN for sharing operations
  - Validates project access for attachment operations

- **Response Formatting**:
  - Returns proper status codes (200, 201, 204, 400, 403, 404, 500)
  - Excludes PAT from responses
  - Includes appropriate error messages
  - Follows consistent response schema

#### Test Execution Commands

```bash
# Run all Figma unit tests
pytest tests/unit/test_figma_service.py tests/unit/test_figma_routes.py -v

#### Run with coverage report
pytest tests/unit/test_figma_service.py tests/unit/test_figma_routes.py --cov=src.services.figma_service --cov=src.routes.figma_routes --cov-report=html

#### Run specific test class or method
pytest tests/unit/test_figma_service.py::TestFigmaServiceCreate -v

#### Run tests matching pattern
pytest tests/unit/ -k "figma" -v
```

#### Validation Protocol

#### Feature Validation Checklist

**A.1: Connect Figma Integration**
- [ ] POST /v1/figma/installations creates database record
- [ ] PAT stored in Secret Manager with pattern `figma-secret-<id>`
- [ ] Secret Manager failure triggers database rollback
- [ ] Response excludes PAT value
- [ ] Retry logic attempts 3 times before failing

**A.2: Share Figma Integration**
- [ ] POST .../share grants access when requestor is ADMIN
- [ ] POST .../share grants access when requestor is SUPER_ADMIN
- [ ] POST .../share denies access for regular users
- [ ] DELETE .../share revokes access (soft delete)
- [ ] figma_installation_access records created correctly

**A.3: Disconnect Figma Integration**
- [ ] DELETE sets deleted_at timestamp (soft delete)
- [ ] Secret removed from Secret Manager
- [ ] Secret Manager failure triggers rollback
- [ ] Soft-deleted installations excluded from queries

**A.4: Get Figma Integration**
- [ ] GET returns installation with PAT status
- [ ] PAT status computed as "Active" when valid
- [ ] PAT status computed as "Expired" when invalid
- [ ] Response never includes actual PAT value

**A.5: Update PAT**
- [ ] PUT updates secret in Secret Manager
- [ ] Secret Manager failure triggers rollback
- [ ] Only owner or admin can update
- [ ] Installation updated_at timestamp refreshed

**A.6: Feature Flag**
- [ ] All endpoints check FIGMA_INTEGRATION_ENABLED
- [ ] Requests rejected when flag=false
- [ ] Appropriate error message returned

**A.7: Attach Figma Files**
- [ ] POST /v1/figma/frames/validate checks frame access
- [ ] Validate API returns frame title on success
- [ ] POST /v1/figma/attachments creates records
- [ ] Same URL overwrites previous attachment
- [ ] GET filters by project_id and tech_spec_id
- [ ] DELETE soft deletes attachment
- [ ] No files downloaded or uploaded to GCS

**A.8: Dual Service Architecture**
- [ ] Backend service routes to admin service
- [ ] Backend service performs authorization first
- [ ] Admin service contains all business logic
- [ ] No logic duplication between services

**A.9: Internal API**
- [ ] GET /internal/figma/installations/by-project/{id} exists
- [ ] Returns installation WITH actual PAT
- [ ] Only accessible in admin service
- [ ] Not exposed through backend service

#### Database Consistency Verification

**Consistency Checks**:
```sql
-- Verify no orphaned secrets (installations deleted but secrets remain)
-- Manual check in Secret Manager

-- Verify no orphaned access records
SELECT COUNT(*) FROM figma_installation_access fia
LEFT JOIN figma_installation fi ON fia.figma_installation_id = fi.id
WHERE fi.id IS NULL OR fi.deleted_at IS NOT NULL;
-- Expected: 0

-- Verify no orphaned attachments
SELECT COUNT(*) FROM figma_attachment fa
LEFT JOIN figma_installation fi ON fa.figma_installation_id = fi.id
WHERE fi.id IS NULL OR fi.deleted_at IS NOT NULL;
-- Expected: 0

-- Verify unique constraint on attachments
SELECT project_id, frame_url, COUNT(*) 
FROM figma_attachment 
WHERE deleted_at IS NULL 
GROUP BY project_id, frame_url 
HAVING COUNT(*) > 1;
-- Expected: 0 rows
```

#### Secret Manager Validation

**Manual Verification Steps**:
1. Create installation and verify secret exists: `gcloud secrets versions access latest --secret=figma-secret-<id>`
2. Update PAT and verify new version created: `gcloud secrets versions list figma-secret-<id>`
3. Delete installation and verify secret removed: `gcloud secrets describe figma-secret-<id>` (should fail)
4. Verify secret naming pattern consistent across all installations

#### API Contract Validation

**Request/Response Validation**:

- All endpoints return proper Content-Type: application/json
- Error responses follow standard format
- Timestamps in ISO 8601 format
- IDs are integers (not strings)
- Boolean flags are true/false (not 1/0)
- Optional fields can be null or omitted
- Array fields return [] not null when empty

**Example API Test Script**:
```python
# test_api_contract.py
def test_create_installation_contract():
    """Verify API contract for create installation."""
    response = client.post('/v1/figma/installations', json={
        'name': 'Test Installation',
        'description': 'Test description',
        'pat': 'figd_test_token_12345'
    })
    
    assert response.status_code == 201
    data = response.json()
    
    # Verify response structure
    assert 'id' in data
    assert 'name' in data
    assert 'status' in data
    assert 'created_at' in data
    
    # Verify PAT not in response
    assert 'pat' not in data
    
    # Verify data types
    assert isinstance(data['id'], int)
    assert isinstance(data['name'], str)
    assert isinstance(data['status'], str)
```

#### Regression Prevention

**Automated Checks**:
- All tests must pass before merging
- Coverage threshold: minimum 80% for new code
- No reduction in overall test coverage
- Linting checks pass (flake8, pylint, mypy)
- Type checking passes (mypy --strict)

**Manual Review Checklist**:
- [ ] No existing tests broken by changes
- [ ] No performance degradation in existing features
- [ ] Documentation matches implementation
- [ ] Error messages are user-friendly
- [ ] Logging provides adequate debugging information
- [ ] No security vulnerabilities introduced (PAT exposure)

#### Test Data Requirements

**Fake Data Patterns**:
```python
# Valid PAT format (example)
VALID_PAT = "figd_AbCdEfGhIjKlMnOpQrStUvWxYz1234567890"

#### Valid Figma frame URLs
VALID_FRAME_URL = "https://www.figma.com/file/ABC123/DesignFile?node-id=1:2"
VALID_FRAME_URL_2 = "https://www.figma.com/design/DEF456/AnotherFile?node-id=3:4"

#### User IDs with roles
ADMIN_USER_ID = 1
SUPER_ADMIN_USER_ID = 2
REGULAR_USER_ID = 3

#### Project and tech_spec IDs
PROJECT_ID = 100
TECH_SPEC_ID = 200
```

#### Acceptance Criteria

Implementation is complete when:

1. All unit tests pass with >80% coverage
2. All 9 feature groups validated manually
3. Database consistency checks pass
4. Secret Manager operations verified manually
5. API contracts validated with test scripts
6. Documentation reviewed and approved
7. Code review completed with no blocking issues
8. Feature flag tested in both states (enabled/disabled)

## 0.7 Implementation Checklist

#### Phase 1: Foundation and Infrastructure

#### Database and Models Setup
- [ ] Design and review database schemas for all 3 tables (figma_installation, figma_installation_access, figma_attachment)
- [ ] Create SQLAlchemy models in db-common-models package
- [ ] Generate Alembic migration for new tables with proper indexes
- [ ] Review and test migration on development database
- [ ] Verify foreign key constraints and cascading behavior
- [ ] Confirm soft delete mechanism works correctly

#### Dependency and Configuration
- [ ] Add `google-cloud-secret-manager` to requirements.txt or pyproject.toml (version: >=2.0.0)
- [ ] Install dependency in development environment: `pip install google-cloud-secret-manager`
- [ ] Add FIGMA_INTEGRATION_ENABLED flag to configuration files
- [ ] Add GCP_PROJECT_ID configuration for Secret Manager
- [ ] Document required GCP IAM roles in README or deployment docs
- [ ] Verify Secret Manager API enabled in GCP project

#### Repository Layer - Interfaces
- [ ] Create `src/repositories/interfaces/` package structure
- [ ] Define IFigmaRepository interface with all required methods
- [ ] Define ISecretRepository interface for Secret Manager operations
- [ ] Define IFigmaAPIRepository interface for Figma API calls
- [ ] Define IConfigRepository interface for configuration access
- [ ] Add comprehensive docstrings (reST format) to all interface methods
- [ ] Add type hints to all method signatures

#### Phase 2: Core Implementation

#### Repository Layer - Implementations
- [ ] Implement FigmaRepository (database operations)
  - [ ] create_installation with transaction support
  - [ ] get_installation with soft delete filtering
  - [ ] update_installation
  - [ ] soft_delete_installation
  - [ ] list_installations with filters
  - [ ] grant_access, revoke_access, list_access
  - [ ] create_attachment, get_attachment, list_attachments, soft_delete_attachment
- [ ] Implement SecretRepository (Google Secret Manager)
  - [ ] create_secret with retry logic (3 attempts)
  - [ ] get_secret with error handling
  - [ ] update_secret with retry logic
  - [ ] delete_secret with retry logic
  - [ ] Handle SecretManagerError exceptions
- [ ] Implement FigmaAPIRepository (Figma API client)
  - [ ] validate_pat by making test API call
  - [ ] validate_frame_access to check URL and retrieve title
  - [ ] get_frame_metadata
  - [ ] Handle HTTP errors and rate limiting
- [ ] Implement ConfigRepository
  - [ ] get, get_bool, get_int methods
  - [ ] get_project_id for GCP project
  - [ ] Support environment variables and config files

#### Service Layer
- [ ] Create FigmaService class with dependency injection constructor
- [ ] Implement create_installation with transaction pattern
  - [ ] Validate PAT format
  - [ ] Create DB record
  - [ ] Store secret with pattern `figma-secret-<id>`
  - [ ] Rollback on Secret Manager failure
- [ ] Implement get_installation with PAT status computation
  - [ ] Retrieve installation from DB
  - [ ] Compute status by validating PAT
  - [ ] Exclude PAT from response
- [ ] Implement update_pat with transaction pattern
  - [ ] Verify authorization
  - [ ] Update secret in Secret Manager
  - [ ] Update installation timestamp
  - [ ] Rollback on failure
- [ ] Implement delete_installation with transaction pattern
  - [ ] Soft delete DB record
  - [ ] Remove secret from Secret Manager
  - [ ] Rollback on failure
- [ ] Implement share_installation with authorization
  - [ ] Query teams/teammembers for role
  - [ ] Verify ADMIN or SUPER_ADMIN
  - [ ] Create access record
- [ ] Implement revoke_access
- [ ] Implement list_installations with filters
- [ ] Implement validate_frame
  - [ ] Retrieve PAT from Secret Manager
  - [ ] Call Figma API to validate access
  - [ ] Return validation result with frame title
- [ ] Implement attach_frames (additive, idempotent)
  - [ ] Validate each frame URL
  - [ ] Create or update attachments
  - [ ] Handle tech_spec_id association
- [ ] Implement list_attachments and get_attachment
- [ ] Implement delete_attachment (soft delete)
- [ ] Add detailed comments explaining WHY for complex logic

#### Phase 3: API Layer

#### archie-service-admin Routes
- [ ] Create src/routes/figma_routes.py module
- [ ] Implement POST /v1/figma/installations (create)
  - [ ] Validate request body
  - [ ] Call FigmaService.create_installation
  - [ ] Return 201 with created resource
- [ ] Implement GET /v1/figma/installations/{id}
- [ ] Implement PUT /v1/figma/installations/{id}/pat
- [ ] Implement DELETE /v1/figma/installations/{id}
- [ ] Implement GET /v1/figma/installations (list)
- [ ] Implement POST /v1/figma/installations/{id}/share
  - [ ] Extract user context from request
  - [ ] Call service with authorization check
- [ ] Implement DELETE /v1/figma/installations/{id}/share
- [ ] Implement GET /v1/figma/installations/{id}/access
- [ ] Implement POST /v1/figma/frames/validate
- [ ] Implement POST /v1/figma/attachments
- [ ] Implement GET /v1/figma/attachments (with query params)
- [ ] Implement GET /v1/figma/attachments/{id}
- [ ] Implement DELETE /v1/figma/attachments/{id}
- [ ] Implement GET /internal/figma/installations/by-project/{project_id}
  - [ ] Return installation WITH PAT for internal use
  - [ ] Mark as internal-only endpoint
- [ ] Register figma_routes blueprint in src/routes/__init__.py
- [ ] Add error handling and consistent error responses
- [ ] Add request/response logging

#### archie-service-backend Routes
- [ ] Create src/routes/figma_routes.py module
- [ ] Implement feature flag check decorator/middleware
- [ ] Implement authentication verification for all routes
- [ ] Implement authorization checks (project access verification)
- [ ] Implement routing logic to admin service
  - [ ] POST /v1/figma/installations → admin service
  - [ ] GET /v1/figma/installations/{id} → admin service
  - [ ] PUT /v1/figma/installations/{id}/pat → admin service
  - [ ] DELETE /v1/figma/installations/{id} → admin service
  - [ ] POST /v1/figma/installations/{id}/share → admin service
  - [ ] DELETE /v1/figma/installations/{id}/share → admin service
  - [ ] POST /v1/figma/frames/validate → admin service
  - [ ] POST /v1/figma/attachments → admin service
  - [ ] GET /v1/figma/attachments → admin service
  - [ ] GET /v1/figma/attachments/{id} → admin service
  - [ ] DELETE /v1/figma/attachments/{id} → admin service
- [ ] Verify NO business logic duplication
- [ ] Add HTTP client methods for admin service communication
- [ ] Register figma_routes blueprint
- [ ] Add request/response logging

#### Phase 4: Testing

#### Test Infrastructure
- [ ] Create tests/fakes/ package
- [ ] Implement FakeFigmaRepository with in-memory state
- [ ] Implement FakeSecretRepository with in-memory state
- [ ] Implement FakeFigmaAPIRepository with configurable responses
- [ ] Implement FakeConfigRepository with test configuration
- [ ] Create test fixtures in conftest.py
- [ ] Set up test database or use fakes exclusively

#### Unit Tests - Service Layer
- [ ] Create tests/unit/test_figma_service.py
- [ ] Test create_installation success case
- [ ] Test create_installation with Secret Manager failure (rollback)
- [ ] Test get_installation with Active PAT status
- [ ] Test get_installation with Expired PAT status
- [ ] Test get_installation for non-existent ID (404)
- [ ] Test update_pat success case
- [ ] Test update_pat with Secret Manager failure (rollback)
- [ ] Test update_pat with unauthorized user
- [ ] Test delete_installation success case
- [ ] Test delete_installation with Secret Manager failure (rollback)
- [ ] Test share_installation with ADMIN user
- [ ] Test share_installation with SUPER_ADMIN user
- [ ] Test share_installation with regular user (denied)
- [ ] Test revoke_access
- [ ] Test validate_frame with valid URL
- [ ] Test validate_frame with invalid URL
- [ ] Test attach_frames (new attachments)
- [ ] Test attach_frames (overwrite existing)
- [ ] Test attach_frames with tech_spec_id
- [ ] Test list_attachments with filters
- [ ] Test delete_attachment

#### Unit Tests - Route Layer (Admin)
- [ ] Create tests/unit/test_figma_routes.py (admin)
- [ ] Test POST /v1/figma/installations with valid data
- [ ] Test POST with missing required fields
- [ ] Test POST with invalid PAT format
- [ ] Test GET /v1/figma/installations/{id} success
- [ ] Test GET for non-existent ID
- [ ] Test PUT /v1/figma/installations/{id}/pat
- [ ] Test DELETE /v1/figma/installations/{id}
- [ ] Test POST /v1/figma/installations/{id}/share
- [ ] Test DELETE .../share
- [ ] Test POST /v1/figma/frames/validate
- [ ] Test POST /v1/figma/attachments
- [ ] Test GET /v1/figma/attachments with filters
- [ ] Test GET /v1/figma/attachments/{id}
- [ ] Test DELETE /v1/figma/attachments/{id}
- [ ] Test GET /internal/figma/installations/by-project/{id}
- [ ] Verify error responses follow standard format

#### Unit Tests - Route Layer (Backend)
- [ ] Create tests/unit/test_figma_routes.py (backend)
- [ ] Test feature flag enforcement (flag=false rejects requests)
- [ ] Test authentication requirement
- [ ] Test authorization (project access verification)
- [ ] Test routing to admin service
- [ ] Verify no business logic in backend routes

#### Test Execution
- [ ] Run all tests: `pytest tests/unit/ -v`
- [ ] Generate coverage report: `pytest --cov=src --cov-report=html`
- [ ] Verify coverage >80% for new code
- [ ] Fix any failing tests
- [ ] Review coverage report for gaps

#### Phase 5: Documentation

#### Code Documentation
- [ ] Review all docstrings for completeness (reST format)
- [ ] Verify type hints on all functions and methods
- [ ] Add inline comments explaining complex logic
- [ ] Document transaction patterns and rollback behavior
- [ ] Document secret naming convention
- [ ] Document error codes and messages

#### Technical Guide
- [ ] Create docs/figma_technical_guide.md
- [ ] Document architecture overview (DI + Repository pattern)
- [ ] Explain main flows:
  - [ ] Create installation with secret storage
  - [ ] Share installation with authorization
  - [ ] Attach frames with validation
- [ ] Provide code navigation guide
  - [ ] Where to find repositories
  - [ ] Where to find service logic
  - [ ] Where to find API routes
- [ ] Document testing approach with fakes
- [ ] Include example usage snippets
- [ ] Document troubleshooting common issues
- [ ] Keep guide concise and focused

#### API Documentation
- [ ] Document all endpoints in OpenAPI/Swagger format (if used)
- [ ] Provide request/response examples for each endpoint
- [ ] Document error responses and codes
- [ ] Document authentication and authorization requirements
- [ ] Document feature flag behavior

#### Phase 6: Integration and Verification

#### Local Development Testing
- [ ] Test create installation flow end-to-end locally
- [ ] Verify secret created in Secret Manager: `gcloud secrets list`
- [ ] Test share installation with different roles
- [ ] Test attach frames flow
- [ ] Test delete installation and verify secret removed
- [ ] Test feature flag disable/enable
- [ ] Test all error scenarios manually

#### Database Verification
- [ ] Run migration on test database
- [ ] Verify all tables created with correct schema
- [ ] Verify indexes created
- [ ] Verify foreign key constraints work
- [ ] Run consistency check queries (from 0.6)
- [ ] Test soft delete behavior across all tables

#### Cross-Service Integration
- [ ] Test backend → admin routing with authentication
- [ ] Verify authorization checks in backend service
- [ ] Test internal API endpoint from platform-event-listener (if applicable)
- [ ] Verify no logic duplication between services

#### Secret Manager Operations
- [ ] Verify IAM roles configured for service accounts
- [ ] Test secret creation manually
- [ ] Test secret retrieval manually
- [ ] Test secret update (version creation) manually
- [ ] Test secret deletion manually
- [ ] Verify retry logic works on transient failures

#### Phase 7: Final Review and Deployment Preparation

#### Code Review
- [ ] Self-review all code changes
- [ ] Check for code duplication opportunities
- [ ] Verify no existing code refactored (per requirement)
- [ ] Ensure consistent naming conventions
- [ ] Run linting: `flake8 src/` and `pylint src/`
- [ ] Run type checking: `mypy src/ --strict`
- [ ] Fix all linting and type errors

#### Security Review
- [ ] Verify PAT never logged or exposed
- [ ] Verify PAT never in GET responses
- [ ] Verify authorization enforced on all endpoints
- [ ] Verify input validation prevents injection attacks
- [ ] Verify error messages don't leak sensitive information
- [ ] Verify Secret Manager permissions minimal and appropriate

#### Performance Review
- [ ] Check for N+1 query patterns
- [ ] Verify database queries use indexes
- [ ] Review Secret Manager call frequency (consider caching if needed)
- [ ] Review Figma API call frequency (implement rate limiting if needed)

#### Compliance Verification
- [ ] All 9 feature groups (A.1-A.9) implemented: [ ]
- [ ] All technical notes (B.1-B.3) followed: [ ]
- [ ] All other notes (C.1-C.4) addressed: [ ]
- [ ] No pyproject.toml version bump: [ ]
- [ ] Only Alembic migrations, no legacy folder: [ ]
- [ ] Required changes in all services: [ ]

#### Deployment Readiness
- [ ] Update README with setup instructions
- [ ] Document GCP prerequisites (Secret Manager enabled, IAM roles)
- [ ] Document environment variables required
- [ ] Create deployment checklist for ops team
- [ ] Prepare rollback plan
- [ ] Schedule deployment window
- [ ] Notify stakeholders of deployment

#### Success Criteria Final Verification

- [ ] All unit tests pass (100%)
- [ ] Code coverage >80% for new code
- [ ] All 9 feature validation checks pass (from 0.6)
- [ ] Database consistency checks pass
- [ ] Manual end-to-end testing completed
- [ ] Documentation complete and reviewed
- [ ] Code review approved
- [ ] Security review passed
- [ ] No breaking changes to existing functionality
- [ ] Feature flag tested in both states
- [ ] UI team confirms integration works with backend APIs

#### Post-Deployment Verification

- [ ] Monitor application logs for errors
- [ ] Verify Secret Manager operations succeeding
- [ ] Verify database writes succeeding
- [ ] Test feature flag toggle in production
- [ ] Monitor API response times
- [ ] Verify no regression in existing features
- [ ] Collect initial usage metrics
- [ ] Address any immediate issues discovered

