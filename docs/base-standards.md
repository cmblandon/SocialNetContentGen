---
description: This document contains all development rules and guidelines for this Python project, applicable to all AI agents (Claude, OpenCode, Cursor, etc.).
alwaysApply: true
---

## 1. Core Principles

- **Small tasks, one at a time**: Always work in baby steps, one at a time. Never go forward more than one step.
- **Test-Driven Development**: Start with failing tests for any new functionality (TDD), according to the task details.
- **Type Safety**: All code must be fully typed with Python type hints (PEP 484).
- **Clear Naming**: Use clear, descriptive names for all variables and functions (snake_case for functions/vars, PascalCase for classes).
- **Incremental Changes**: Prefer incremental, focused changes over large, complex modifications.
- **Question Assumptions**: Always question assumptions and inferences.
- **Pattern Detection**: Detect and highlight repeated code patterns.
- **Domain-Driven Design**: Follow DDD principles across all layers (Domain, Application, Infrastructure, Presentation).

## 2. Language Standards
- **English Only**: All technical artifacts must always use English, including:
    - Code (variables, functions, classes, comments, error messages, log messages)
    - Docstrings (follow PEP 257)
    - Documentation (README, guides, API docs)
    - Task tickets (titles, descriptions, comments)
    - Data schemas and database names
    - Configuration files and scripts
    - Git commit messages
    - Test names and descriptions
    - SQLAlchemy model definitions and relationship names
    - FastAPI route paths and operation IDs
    - Pydantic model field descriptions

**Examples:**

```python
# Good
async def find_candidate_by_email(email: str) -> Optional[Candidate]:
    """Find a candidate by their email address."""
    pass

class CandidateNotFoundError(Exception):
    """Raised when a candidate cannot be found in the database."""
    pass

# Avoid
async def encontrar_candidato_por_email(email: str) -> Optional[Candidato]:
    """Encontrar un candidato por su correo electrónico."""
    pass
```

## 3. Specific Standards

For detailed standards and guidelines specific to different areas of the project, refer to:

- [Backend Standards (Python)](./backend-standards-python.md) - FastAPI routes, SQLAlchemy patterns, async/await, testing with pytest, security and backend best practices
- [Frontend Standards](./frontend-standards.md) - React components, UI/UX guidelines, and frontend architecture
- [Documentation Standards](./documentation-standards.md) - Technical documentation structure, formatting, and maintenance guidelines
- [OpenCode Tasks Mandatory Steps](./opencode-tasks-mandatory-steps.md) - Required checklist and execution rules when creating or updating OpenCode `tasks.md` files

## 4. Project Skills and Agents

- **Skills Location**: Skills live in `.opencode/`
- **When Skills Apply**: When a request matches a skill description, load and follow the corresponding agent configuration automatically before continuing
- **Referenced Files**: Load any referenced files in the agent folder when the skill/agent requires them
- **Agent Configuration**: All agents are defined in YAML format with their tools, models, and descriptions

**Loading Priority:**
1. Check `.opencode/agents/` for relevant agent
2. Load the agent's complete YAML definition
3. Review tools available to the agent
4. Review model assignment (make sure it's appropriate for the task)
5. Follow the agent's guidance before executing

**Example Agent Structure:**
```yaml
---
name: backend-developer
description: Use for Python backend development with DDD patterns
tools:
  - Bash
  - Read
  - Edit
  - Write
model: ollama/qwen3.5:0.8b-mlx
color: error
---
```

## 5. Agent Configuration and Model Assignment

- **Model Selection**: Choose appropriate models based on task complexity:
  - Simple tasks (formatting, small fixes): Local models (qwen, codestral)
  - Complex reasoning (architecture, planning): Larger models (claude-sonnet, claude-opus)
- **Verify Model Format**: Ensure model names follow OpenCode conventions:
  - Local Ollama models: `modelname:version`
  - Remote models: Use full provider path if needed
- **Session Consistency**: Keep model choice consistent for related tasks in the same session
- **Update Agents**: When updating agent definitions in `.opencode/agents/`, test them with `ollama launch opencode` before committing

## 6. Python-Specific Development Rules

### Code Organization
- **Layered Architecture**: Respect the four-layer architecture:
  - `src/domain/` - Business logic, entities, repository interfaces
  - `src/application/` - Services, DTOs, use cases
  - `src/infrastructure/` - Database, external services, repositories
  - `src/presentation/` - Routes, handlers, middleware

- **Module Structure**: Follow PEP 420 implicit namespace packages or explicit packages with `__init__.py`
- **Imports**: Use absolute imports, organize with isort or ruff

### Type Hints
- **Mandatory Type Hints**: All function signatures must include type hints
- **Return Types**: Always specify return types (use `-> None` for void functions)
- **Optional Types**: Use `Optional[T]` from `typing` for nullable values
- **Generic Types**: Use generic types for collections (`List[T]`, `Dict[K, V]`, etc.)
- **Type Annotations in Classes**: Use class variables with type hints

```python
# Good
from typing import Optional, List

async def create_candidate(
    data: CandidateCreateDTO,
    repository: ICandidateRepository
) -> Candidate:
    """Create a new candidate with validated data."""
    candidate = Candidate(**data.dict())
    return await repository.save(candidate)

# Avoid
async def create_candidate(data, repository):
    candidate = Candidate(**data)
    return repository.save(candidate)
```

### Testing Requirements
- **Test Framework**: Use pytest exclusively
- **Test Location**: `tests/` directory mirroring `src/` structure
- **Test Files**: Name files as `test_[module_name].py`
- **Coverage Requirement**: Maintain 90% coverage threshold
- **Async Tests**: Use `@pytest.mark.asyncio` for async test functions
- **Fixtures**: Create reusable fixtures in `conftest.py`
- **Mocking**: Use `unittest.mock` or `pytest-mock` for dependencies

```python
# Good structure
tests/
├── conftest.py
├── unit/
│   ├── test_candidate_service.py
│   ├── test_candidate_repository.py
│   └── test_validators.py
├── integration/
│   └── test_api_candidates.py
└── factories.py
```

### Async/Await Patterns
- **Async Functions**: Use `async def` for I/O operations
- **Await Calls**: Always `await` async functions
- **Concurrent Operations**: Use `asyncio.gather()` for parallel operations
- **Connection Pooling**: Use connection pools for database access
- **Error Handling**: Properly handle exceptions in async contexts

```python
# Good
async def get_candidates_with_apps():
    """Get candidates and their applications concurrently."""
    candidates, applications = await asyncio.gather(
        candidate_service.find_all(),
        application_service.find_all()
    )
    return candidates, applications

# Avoid
async def get_candidates_with_apps():
    candidates = await candidate_service.find_all()
    applications = await application_service.find_all()
    return candidates, applications
```

### Database Operations
- **SQLAlchemy 2.0**: Use SQLAlchemy 2.0+ style (select statements)
- **ORM Models**: Define in `infrastructure/models.py` or `infrastructure/database/models/`
- **Migrations**: Use Alembic for all schema changes
- **Transactions**: Use session transactions for data consistency
- **Lazy Loading**: Avoid N+1 queries with eager loading (joinedload, selectinload)

```python
# Good: Using SQLAlchemy 2.0 select syntax
from sqlalchemy import select

stmt = select(CandidateModel).where(
    CandidateModel.email == email
).options(joinedload(CandidateModel.applications))
result = await session.execute(stmt)
candidate = result.scalar_one_or_none()
```

### FastAPI Route Design
- **Path Operations**: Use FastAPI decorators (`@router.get`, `@router.post`, etc.)
- **Status Codes**: Explicitly set status codes (201 for creation, 200 for success, etc.)
- **Request Validation**: Use Pydantic models for request bodies
- **Response Models**: Define response schemas with Pydantic
- **Error Handling**: Use HTTPException with proper status codes and details
- **Documentation**: Include docstrings and operation descriptions

```python
# Good
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/candidates", tags=["candidates"])

@router.post("", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
async def create_candidate(data: CandidateCreateDTO) -> CandidateResponse:
    """Create a new candidate with the provided data."""
    try:
        candidate = await candidate_service.create(data)
        return CandidateResponse.from_orm(candidate)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
```

### Error Handling
- **Custom Exceptions**: Create domain-specific exception classes
- **Exception Hierarchy**: Inherit from appropriate base exceptions
- **Error Messages**: Provide descriptive, actionable error messages
- **Logging**: Log errors with full context and stack traces

```python
# Good
class DomainException(Exception):
    """Base exception for domain errors."""
    pass

class CandidateNotFoundError(DomainException):
    """Raised when a candidate cannot be found."""
    pass

# Usage
try:
    candidate = await repository.find_by_id(candidate_id)
    if not candidate:
        raise CandidateNotFoundError(
            f"Candidate with ID {candidate_id} not found"
        )
except CandidateNotFoundError as e:
    logger.error(f"Lookup failed: {str(e)}")
    raise HTTPException(status_code=404, detail=str(e))
```

### Validation
- **Input Validation**: Use Pydantic models for all inputs
- **Custom Validators**: Implement Pydantic validators for complex rules
- **Business Logic Validation**: Keep business rules in domain models or services
- **Error Messages**: Provide clear validation error messages

```python
from pydantic import BaseModel, EmailStr, validator

class CandidateCreateDTO(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    
    @validator("first_name", "last_name")
    def validate_names(cls, v):
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()
```

## 7. Symlink Integrity and Multi-Agent Portability

- **Canonical Source**: Keep reusable artifacts in `.opencode` as the canonical source
- **Agent-Specific References**: Reference through symlinks when possible
- **Update Safety**: When files are renamed, moved, or suffixes change, verify and update all symlinks
- **New Artifact Linking**: Create corresponding symlinks when adding new agents or skills
- **External Customization Review**: Evaluate whether customizations should be moved to `.opencode` with symlinks
- **Completion Gate**: A change is incomplete if it leaves broken symlinks or stale targets

## 8. Mandatory OpenCode Artifact Updates for Post-Launch Changes

When a new fix/change request appears after agent launch and before the session completes, treat it as a spec update first, not as an informal "fix this quickly".

**Required Order:**

1. **Update OpenCode agent artifacts** if affected:
   - Agent configuration in `.opencode/agents/`
   - Task definitions if using task-based agents
   - Documented behavior and tools

2. **Regenerate if needed**: Re-run agent configuration validation

3. **Implement code only after** artifacts reflect the new request

4. **Verify implementation** against updated artifacts before completion

**Do not apply direct code-only fixes without updating agent/task definitions.**

## 9. Git and Commit Standards

- **Commit Messages**: Write clear, descriptive messages in English (imperative mood)
- **Atomic Commits**: Keep commits small and focused
- **Branch Naming**: Use kebab-case with prefixes: `feature/`, `fix/`, `docs/`
- **PR Descriptions**: Reference what changed and why

```bash
# Good
git commit -m "refactor: extract email validation to separate method"
git commit -m "test: add unit tests for candidate service"
git commit -m "feat: add SQLAlchemy relationship eager loading"

# Avoid
git commit -m "updates"
git commit -m "fixed stuff"
git commit -m "cambios al candidato"
```

## 10. Documentation Requirements

- **Docstrings**: Follow PEP 257 style (Google or NumPy style)
- **Module Documentation**: Include at the top of each module
- **Function Documentation**: Document purpose, parameters, return value, and exceptions
- **Class Documentation**: Document class purpose and key attributes
- **Inline Comments**: Use sparingly for non-obvious logic

```python
# Good
def calculate_candidate_score(
    years_experience: int,
    education_level: str,
    test_score: float
) -> float:
    """
    Calculate a candidate's overall qualification score.
    
    Args:
        years_experience: Number of years of relevant experience.
        education_level: Educational attainment level.
        test_score: Score from qualification test (0-100).
    
    Returns:
        A normalized score between 0 and 100.
    
    Raises:
        ValueError: If inputs are invalid or out of range.
    """
    pass
```

## 11. Development Environment

- **Python Version**: Use Python 3.10 or higher
- **Virtual Environment**: Always use venv or poetry for dependency isolation
- **Package Manager**: Use pip with requirements.txt or pyproject.toml with poetry
- **Environment Variables**: Use .env files with python-dotenv (never commit .env)
- **Local Development**: Use FastAPI `uvicorn` with `--reload` flag

```bash
# Setup
python -m venv venv
source venv/bin/activate  # Linux/macOS
pip install -r requirements.txt

# Development
uvicorn src.main:app --reload

# Testing
pytest --cov=src tests/

# Type checking
mypy src/

# Linting
ruff check src/
```

## 12. Code Review Checklist

Before considering code complete, verify:

- [ ] All functions have type hints
- [ ] 90% test coverage achieved
- [ ] No hardcoded secrets or credentials
- [ ] Follows DDD layered architecture
- [ ] Error handling is proper and logged
- [ ] Database queries are optimized (no N+1 queries)
- [ ] Async/await patterns are correct
- [ ] Pydantic validation is comprehensive
- [ ] All docstrings follow PEP 257
- [ ] Git history is clean and descriptive
- [ ] No broken symlinks or stale references
- [ ] All agents/skills in .opencode are properly configured