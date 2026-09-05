---
description: Backend development standards, best practices, and conventions for Python FastAPI/SQLAlchemy application including Domain-Driven Design, SOLID principles, architecture patterns, API design, and testing practices
globs: ["backend/src/**/*.py", "backend/alembic/**/*.py", "backend/pytest.ini", "backend/pyproject.toml"]
alwaysApply: true
---

# Backend Project Standards and Best Practices (Python)

## Table of Contents

- [Overview](#overview)
- [Technology Stack](#technology-stack)
  - [Core Technologies](#core-technologies)
  - [Database & ORM](#database--orm)
  - [Testing Framework](#testing-framework)
  - [Development Tools](#development-tools)
- [Architecture Overview](#architecture-overview)
  - [Domain-Driven Design (DDD)](#domain-driven-design-ddd)
  - [Layered Architecture](#layered-architecture)
  - [Project Structure](#project-structure)
- [Domain-Driven Design Principles](#domain-driven-design-principles)
  - [Entities](#entities)
  - [Value Objects](#value-objects)
  - [Aggregates](#aggregates)
  - [Repositories](#repositories)
  - [Domain Services](#domain-services)
  - [Additional Recommendations](#additional-recommendations)
- [SOLID and DRY Principles](#solid-and-dry-principles)
  - [Single Responsibility Principle (SRP)](#single-responsibility-principle-srp)
  - [Open/Closed Principle (OCP)](#openclosed-principle-ocp)
  - [Liskov Substitution Principle (LSP)](#liskov-substitution-principle-lsp)
  - [Interface Segregation Principle (ISP)](#interface-segregation-principle-isp)
  - [Dependency Inversion Principle (DIP)](#dependency-inversion-principle-dip)
  - [DRY (Don't Repeat Yourself)](#dry-dont-repeat-yourself)
- [Coding Standards](#coding-standards)
  - [Language and Naming Conventions](#language-and-naming-conventions)
  - [Python Usage](#python-usage)
  - [Error Handling](#error-handling)
  - [Validation Patterns](#validation-patterns)
  - [Logging Standards](#logging-standards)
- [API Design Standards](#api-design-standards)
  - [REST Endpoints](#rest-endpoints)
  - [Request/Response Patterns](#requestresponse-patterns)
  - [Error Response Format](#error-response-format)
  - [CORS Configuration](#cors-configuration)
- [Database Patterns](#database-patterns)
  - [SQLAlchemy Models](#sqlalchemy-models)
  - [Migrations](#migrations)
  - [Repository Pattern](#repository-pattern)
- [Testing Standards](#testing-standards)
  - [Unit Testing](#unit-testing)
  - [Integration Testing](#integration-testing)
  - [Test Coverage Requirements](#test-coverage-requirements)
  - [Mocking Standards](#mocking-standards)
- [Performance Best Practices](#performance-best-practices)
  - [Database Query Optimization](#database-query-optimization)
  - [Async Patterns](#async-patterns)
  - [Error Handling Performance](#error-handling-performance)
- [Security Best Practices](#security-best-practices)
  - [Input Validation](#input-validation)
  - [Environment Variables](#environment-variables)
  - [Dependency Injection](#dependency-injection)
- [Development Workflow](#development-workflow)
  - [Git Workflow](#git-workflow)
  - [Development Scripts](#development-scripts)
  - [Code Quality](#code-quality)
- [Serverless Deployment](#serverless-deployment)
  - [AWS Lambda Configuration](#aws-lambda-configuration)
  - [Serverless Framework](#serverless-framework)

---

## Overview

This document outlines the best practices, conventions, and standards used in the Python backend application. The backend follows Domain-Driven Design (DDD) principles and implements a layered architecture to ensure code consistency, maintainability, and scalability.

## Technology Stack

### Core Technologies
- **Python 3.10+**: Modern Python runtime with type hints support
- **FastAPI**: Modern, fast web framework with automatic API documentation
- **SQLAlchemy 2.0**: Advanced ORM for database access
- **Pydantic**: Data validation and parsing using Python type annotations

### Database & ORM
- **PostgreSQL**: Relational database (Docker container)
- **SQLAlchemy**: Type-safe database client and ORM
- **Alembic**: Database migration tool for SQLAlchemy

### Testing Framework
- **pytest**: Testing framework with powerful fixtures and plugins
- **pytest-cov**: Coverage reporting
- **Coverage Threshold**: 90% for branches, functions, lines, and statements
- **Test Location**: `tests/` directory with structure mirroring `src/`

### Development Tools
- **ruff**: Fast Python linter and formatter
- **mypy**: Static type checker
- **python-dotenv**: Environment variable management
- **Pydantic**: Data validation

## Architecture Overview

### Domain-Driven Design (DDD)

Domain-Driven Design is a methodology that focuses on modeling software according to business logic and domain knowledge. By centering development on a deep understanding of the domain, DDD facilitates the creation of complex systems.

**Benefits:**
- **Improved Communication**: Promotes a common language between developers and domain experts
- **Clear Domain Models**: Helps build models that accurately reflect business rules
- **High Maintainability**: By dividing the system into subdomains, it facilitates maintenance

### Layered Architecture

The backend follows a layered DDD architecture:

**Presentation Layer** (`src/presentation/`)
- Route handlers handle HTTP requests/responses
- API routes define endpoints
- Handlers use services from Application layer

**Application Layer** (`src/application/`)
- Services contain business logic and orchestration
- DTOs (Pydantic models) for validation
- Services use repositories from Domain layer

**Domain Layer** (`src/domain/`)
- Models define core business entities (Candidate, Position, Application, etc.)
- Repository interfaces define data access contracts
- Pure business logic without external dependencies
- Custom exception classes

**Infrastructure Layer** (`src/infrastructure/`)
- Prisma ORM handles database operations
- Repository implementations satisfy domain interfaces
- SQLAlchemy session management
- External service integrations

### Project Structure

```
backend/
├── src/
│   ├── domain/
│   │   ├── models/              # Domain entities
│   │   ├── repositories/        # Repository interfaces (abstract base classes)
│   │   └── exceptions.py        # Domain exceptions
│   ├── application/
│   │   ├── services/            # Business logic services
│   │   ├── dtos/                # Pydantic models for validation
│   │   └── validators.py        # Input validation logic
│   ├── presentation/
│   │   ├── routes/              # FastAPI route definitions
│   │   └── handlers.py          # HTTP request handlers
│   ├── infrastructure/
│   │   ├── database.py          # SQLAlchemy session setup
│   │   ├── repositories/        # Repository implementations
│   │   ├── logger.py            # Logging utilities
│   │   └── config.py            # Configuration management
│   ├── middleware/              # FastAPI middleware
│   ├── dependencies.py          # Dependency injection setup
│   ├── main.py                  # FastAPI application entry point
│   └── lambda_handler.py        # AWS Lambda handler
├── migrations/                  # Alembic migrations
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   ├── application/
│   │   └── presentation/
│   ├── integration/
│   ├── conftest.py             # pytest fixtures
│   └── factories.py            # Test data builders
├── pytest.ini                   # pytest configuration
├── pyproject.toml              # Dependencies and project config
├── alembic.ini                 # Alembic configuration
└── docker-compose.yml          # Docker setup
```

## Domain-Driven Design Principles

### Entities

Entities are objects with a distinct identity that persists over time.

**Before:**
```python
# Previously, candidate data might have been a simple dictionary
candidate = {
    "id": 1,
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com"
}
```

**After:**
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class Candidate:
    id: Optional[int]
    first_name: str
    last_name: str
    email: str
    
    def validate_email(self) -> bool:
        """Encapsulate business logic for email validation"""
        return "@" in self.email
    
    def save(self, session) -> "Candidate":
        """Encapsulate persistence logic"""
        # Database save implementation
        pass
```

**Explanation**: `Candidate` is an entity because it has a unique identifier (`id`) that distinguishes it from other candidates, even if other properties are identical.

**Best Practice**: Entities should encapsulate business logic related to their domain concept and maintain consistency of their internal state.

### Value Objects

Value Objects describe aspects of the domain without conceptual identity. They are defined by their attributes rather than an identifier.

**Before:**
```python
# Education information as a simple dictionary
education = {
    "institution": "University",
    "degree": "Bachelor",
    "start_date": "2010-01-01",
    "end_date": "2014-01-01"
}
```

**After:**
```python
from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass
class Education:
    institution: str
    title: str
    start_date: date
    end_date: Optional[date] = None
    
    def is_valid(self) -> bool:
        """Validate education object invariants"""
        return self.end_date is None or self.end_date > self.start_date
```

**Explanation**: `Education` can be considered a Value Object as it describes a candidate's education without needing a unique identifier. It's immutable and defined purely by its attributes.

### Aggregates

Aggregates are clusters of objects that must be treated as a unit. They have a root entity that enforces invariants.

**Before:**
```python
# Candidate and education data handled separately
candidate = {"id": 1, "name": "John Doe"}
educations = [{"candidate_id": 1, "institution": "University"}]
```

**After:**
```python
from dataclasses import dataclass, field
from typing import List

@dataclass
class Candidate:
    id: Optional[int]
    first_name: str
    last_name: str
    email: str
    educations: List[Education] = field(default_factory=list)
    
    def add_education(self, education: Education) -> None:
        """Add education through aggregate root"""
        if education.is_valid():
            self.educations.append(education)
        else:
            raise ValueError("Invalid education data")
```

**Explanation**: `Candidate` acts as an aggregate root that contains `Education`. Operations affecting `Education` must be handled through the aggregate root to maintain consistency.

### Repositories

Repositories provide interfaces for accessing aggregates and entities, encapsulating data access logic.

**Before:**
```python
# Direct database queries without abstraction
from sqlalchemy import select
from models import CandidateModel

def get_candidate_by_id(session, candidate_id: int):
    return session.execute(
        select(CandidateModel).where(CandidateModel.id == candidate_id)
    ).scalar_one_or_none()
```

**After:**
```python
from abc import ABC, abstractmethod
from typing import Optional, List
from domain.models import Candidate

class ICandidateRepository(ABC):
    """Repository interface in domain layer"""
    
    @abstractmethod
    async def find_by_id(self, candidate_id: int) -> Optional[Candidate]:
        pass
    
    @abstractmethod
    async def save(self, candidate: Candidate) -> Candidate:
        pass
    
    @abstractmethod
    async def find_all(self) -> List[Candidate]:
        pass

class CandidateRepository(ICandidateRepository):
    """Repository implementation in infrastructure layer"""
    
    def __init__(self, session):
        self.session = session
    
    async def find_by_id(self, candidate_id: int) -> Optional[Candidate]:
        """Implementation using SQLAlchemy"""
        result = await self.session.execute(
            select(CandidateModel).where(CandidateModel.id == candidate_id)
        )
        data = result.scalar_one_or_none()
        return Candidate(**data) if data else None
    
    async def save(self, candidate: Candidate) -> Candidate:
        """Save candidate to database"""
        # Implementation with SQLAlchemy
        pass
```

**Explanation**: `ICandidateRepository` defines a clear interface for accessing candidate data, while `CandidateRepository` encapsulates database logic.

### Domain Services

Domain Services contain business logic that doesn't naturally belong to an entity or value object.

**Before:**
```python
# Loose functions for business logic
def calculate_age(birth_date: date) -> int:
    from datetime import date
    today = date.today()
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age
```

**After:**
```python
from datetime import date

class CandidateService:
    """Encapsulate candidate-related business logic"""
    
    @staticmethod
    def calculate_age(birth_date: date) -> int:
        """Calculate age from birth date"""
        today = date.today()
        age = today.year - birth_date.year
        if (today.month, today.day) < (birth_date.month, birth_date.day):
            age -= 1
        return age
    
    @staticmethod
    def is_eligible_for_position(candidate: Candidate, position: Position) -> bool:
        """Check if candidate meets position requirements"""
        # Business logic here
        pass
```

**Explanation**: `CandidateService` encapsulates business logic related to candidates, providing a centralized point for these operations.

### Additional Recommendations

**Use of Factories**

Factories encapsulate the logic of creating complex objects.

```python
class CandidateFactory:
    @staticmethod
    def create(data: dict) -> Candidate:
        """Create candidate from validated data"""
        return Candidate(
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data["email"],
            educations=[Education(**edu) for edu in data.get("educations", [])]
        )
```

**Domain Events**

Domain events handle side effects without tight coupling.

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class CandidateCreatedEvent:
    candidate_id: int
    email: str
    created_at: datetime
```

## SOLID and DRY Principles

### Single Responsibility Principle (SRP)

Each class should have a single responsibility.

**Before:**
```python
# Class handling both validation and persistence
class CandidateManager:
    def process_candidate(self, data: dict):
        if "@" not in data["email"]:
            raise ValueError("Invalid email")
        
        # Save to database
        db.save(data)
        
        # Send email
        send_email(data["email"])
```

**After:**
```python
# Separated responsibilities
class Candidate:
    def validate_email(self) -> bool:
        """Candidate handles its own validation"""
        return "@" in self.email

class CandidateRepository:
    async def save(self, candidate: Candidate) -> Candidate:
        """Repository handles persistence"""
        pass

class CandidateService:
    async def create_candidate(self, data: dict) -> Candidate:
        """Service orchestrates the flow"""
        candidate = Candidate(**data)
        candidate.validate_email()
        return await self.repository.save(candidate)
```

### Open/Closed Principle (OCP)

Software should be open for extension but closed for modification.

**Before:**
```python
# Direct modification for new functionality
class Candidate:
    def save_to_database(self):
        pass
    
    def send_email(self):
        pass
```

**After:**
```python
# Extend through composition, not modification
class Candidate:
    def save_to_database(self):
        pass

class CandidateWithNotifications(Candidate):
    def __init__(self, candidate: Candidate, notifier):
        self.candidate = candidate
        self.notifier = notifier
    
    def send_email(self):
        self.notifier.send(self.candidate.email)
```

### Liskov Substitution Principle (LSP)

Derived classes must be substitutable for their base classes.

**Before:**
```python
class Repository(ABC):
    async def save(self, entity):
        pass

class ReadOnlyRepository(Repository):
    async def save(self, entity):
        raise NotImplementedError("Read-only repository")
```

**After:**
```python
class Repository(ABC):
    async def save(self, entity):
        pass

class ReadOnlyRepository(ABC):
    """Separate interface for read-only operations"""
    async def find_by_id(self, id: int):
        pass

class CandidateRepository(Repository, ReadOnlyRepository):
    async def save(self, entity):
        pass
```

### Interface Segregation Principle (ISP)

Many specific interfaces are better than one general interface.

**Before:**
```python
class CandidateOperations(ABC):
    @abstractmethod
    def save(self): pass
    
    @abstractmethod
    def validate(self): pass
    
    @abstractmethod
    def send_email(self): pass
    
    @abstractmethod
    def generate_report(self): pass
```

**After:**
```python
class Saveable(ABC):
    @abstractmethod
    def save(self): pass

class Validatable(ABC):
    @abstractmethod
    def validate(self): pass

class Notifiable(ABC):
    @abstractmethod
    def send_email(self): pass

class Candidate(Saveable, Validatable):
    pass
```

### Dependency Inversion Principle (DIP)

Depend on abstractions, not concretions.

**Before:**
```python
# Direct dependency on concrete SQLAlchemy
class CandidateService:
    def __init__(self):
        self.session = SessionLocal()
    
    async def create(self, data: dict):
        # Uses self.session directly
        pass
```

**After:**
```python
from abc import ABC, abstractmethod

class ICandidateRepository(ABC):
    @abstractmethod
    async def save(self, candidate: Candidate):
        pass

class CandidateService:
    def __init__(self, repository: ICandidateRepository):
        self.repository = repository
    
    async def create(self, data: dict) -> Candidate:
        candidate = Candidate(**data)
        return await self.repository.save(candidate)
```

### DRY (Don't Repeat Yourself)

Reduce duplication in code.

**Before:**
```python
# Repeated validation logic
async def save_candidate(data: dict):
    if not data.get("email") or "@" not in data["email"]:
        raise ValueError("Invalid email")
    # save logic

async def update_candidate(data: dict):
    if not data.get("email") or "@" not in data["email"]:
        raise ValueError("Invalid email")
    # update logic
```

**After:**
```python
class Candidate:
    @property
    def email(self) -> str:
        return self._email
    
    @email.setter
    def email(self, value: str):
        if not value or "@" not in value:
            raise ValueError("Invalid email")
        self._email = value

async def save_candidate(data: dict):
    candidate = Candidate(**data)
    # save logic

async def update_candidate(data: dict):
    candidate = Candidate(**data)
    # update logic
```

## Coding Standards

### Language and Naming Conventions

- **Variable Naming**: Use snake_case for variables and functions (e.g., `candidate_id`, `find_candidate_by_id`)
- **Class Naming**: Use PascalCase for classes (e.g., `Candidate`, `CandidateRepository`)
- **Constants Naming**: Use UPPER_SNAKE_CASE for constants (e.g., `MAX_CANDIDATES_PER_PAGE`)
- **Type Naming**: Use PascalCase for type annotations and aliases (e.g., `CandidateData`)
- **File Naming**: Use snake_case for file names (e.g., `candidate_service.py`, `candidate_handler.py`)
- **Module Organization**: Use snake_case for module names

**Examples:**

```python
# Good: All in English with proper naming
from abc import ABC, abstractmethod

class ICandidateRepository(ABC):
    @abstractmethod
    async def find_by_id(self, candidate_id: int) -> Optional[Candidate]:
        """Find candidate by ID"""
        pass

# Avoid: Non-English or inconsistent naming
class IRepositorioCandidato(ABC):
    @abstractmethod
    async def buscar_por_id(self, id_candidato: int) -> Optional[Candidato]:
        """Buscar candidato por ID"""
        pass
```

### Python Usage

- **Type Hints**: Always use type hints (PEP 484 compliant)
- **PEP 8 Compliance**: Follow PEP 8 style guide
- **Dataclasses or Pydantic**: Use for data structures (prefer Pydantic for API models)
- **Context Managers**: Use `with` statements for resource management
- **F-Strings**: Use f-strings for string formatting

```python
# Good: Type hints and proper formatting
async def find_candidate_by_id(candidate_id: int) -> Optional[Candidate]:
    """Find a candidate by their ID."""
    candidate = await session.get(Candidate, candidate_id)
    return candidate

# Avoid: No type hints or unclear code
def find_candidate(id):
    candidate = session.get(Candidate, id)
    return candidate
```

### Error Handling

- **Custom Exceptions**: Create domain-specific exception classes
- **Proper Inheritance**: Inherit from appropriate base exceptions
- **Meaningful Messages**: Provide clear error messages

```python
class DomainException(Exception):
    """Base exception for domain errors"""
    pass

class CandidateNotFoundError(DomainException):
    """Raised when a candidate is not found"""
    pass

class InvalidCandidateDataError(DomainException):
    """Raised when candidate data is invalid"""
    pass

# Usage
try:
    candidate = await candidate_repository.find_by_id(candidate_id)
    if not candidate:
        raise CandidateNotFoundError(f"Candidate with ID {candidate_id} not found")
except CandidateNotFoundError as e:
    logger.error(f"Candidate lookup failed: {str(e)}")
    raise
```

### Validation Patterns

- **Input Validation**: Use Pydantic models for validation
- **Validator Functions**: Use Pydantic validators for complex validation
- **Early Validation**: Validate before processing

```python
from pydantic import BaseModel, EmailStr, validator

class CandidateCreateDTO(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    birth_date: date
    
    @validator("first_name", "last_name")
    def names_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()
    
    @validator("birth_date")
    def valid_birth_date(cls, v):
        if v > date.today():
            raise ValueError("Birth date cannot be in the future")
        return v

# Usage in service
async def create_candidate(data: CandidateCreateDTO) -> Candidate:
    """Create new candidate with validated data"""
    candidate = Candidate(
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email
    )
    return await candidate_repository.save(candidate)
```

### Logging Standards

- **Use Logger**: Use Python's `logging` module
- **Log Levels**: Use appropriate levels (debug, info, warning, error, critical)
- **Structured Logging**: Include relevant context

```python
import logging

logger = logging.getLogger(__name__)

logger.info(f"Candidate created: {candidate.id}")
logger.error(f"Failed to create candidate: {str(error)}", exc_info=True)
logger.warning(f"Candidate email not verified: {candidate.email}")
```

## API Design Standards

### REST Endpoints

- **RESTful Naming**: Use resource-based URLs
- **HTTP Methods**: Use appropriate methods (GET, POST, PUT, DELETE, PATCH)
- **Consistent Structure**: Follow consistent patterns

```python
from fastapi import APIRouter

router = APIRouter(prefix="/candidates", tags=["candidates"])

@router.get("")
async def list_candidates() -> List[CandidateResponse]:
    """List all candidates"""
    pass

@router.get("/{candidate_id}")
async def get_candidate(candidate_id: int) -> CandidateResponse:
    """Get candidate by ID"""
    pass

@router.post("")
async def create_candidate(data: CandidateCreateDTO) -> CandidateResponse:
    """Create new candidate"""
    pass

@router.put("/{candidate_id}")
async def update_candidate(candidate_id: int, data: CandidateUpdateDTO) -> CandidateResponse:
    """Update candidate"""
    pass

@router.delete("/{candidate_id}")
async def delete_candidate(candidate_id: int) -> None:
    """Delete candidate"""
    pass
```

### Request/Response Patterns

- **JSON Format**: Use JSON for bodies
- **Consistent Structure**: Maintain consistent response format
- **Status Codes**: Use appropriate HTTP status codes

```python
from pydantic import BaseModel

class CandidateResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    
    class Config:
        from_attributes = True

class SuccessResponse(BaseModel):
    success: bool = True
    data: CandidateResponse
    message: str = "Operation completed successfully"

class ErrorResponse(BaseModel):
    success: bool = False
    error: dict
```

### Error Response Format

- **Consistent Format**: All errors follow the same structure
- **Error Codes**: Use meaningful error codes
- **HTTP Status Codes**: Map errors appropriately

```python
from fastapi import HTTPException, status

@router.get("/{candidate_id}")
async def get_candidate(candidate_id: int) -> CandidateResponse:
    try:
        candidate = await candidate_repository.find_by_id(candidate_id)
        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": "Candidate not found",
                    "code": "CANDIDATE_NOT_FOUND"
                }
            )
        return CandidateResponse.from_orm(candidate)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": str(e),
                "code": "VALIDATION_ERROR"
            }
        )
```

### CORS Configuration

- **Enable CORS**: Configure for frontend origin
- **Secure Configuration**: Allow specific origins in production
- **Credentials**: Handle credentials appropriately

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Development
        "https://example.com"      # Production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Database Patterns

### SQLAlchemy Models

- **Declarative Models**: Use SQLAlchemy's declarative base
- **Type Annotations**: Use Python type hints
- **Relationships**: Define relationships clearly

```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class CandidateModel(Base):
    __tablename__ = "candidates"
    
    id: int = Column(Integer, primary_key=True)
    first_name: str = Column(String(100), nullable=False)
    last_name: str = Column(String(100), nullable=False)
    email: str = Column(String(100), unique=True, nullable=False)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    
    educations = relationship("EducationModel", back_populates="candidate")
    applications = relationship("ApplicationModel", back_populates="candidate")
```

### Migrations

- **Version Control**: Use Alembic for migrations
- **Descriptive Names**: Name migrations descriptively
- **Review Before Applying**: Always review migration files

```bash
# Create migration
alembic revision --autogenerate -m "add_candidate_table"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Repository Pattern

- **Repository Interfaces**: Define as abstract base classes
- **SQLAlchemy Implementation**: Implement in infrastructure layer
- **Dependency Injection**: Inject session or connection pool

```python
from abc import ABC, abstractmethod
from typing import Optional, List
from sqlalchemy.orm import Session

class ICandidateRepository(ABC):
    @abstractmethod
    async def find_by_id(self, candidate_id: int) -> Optional[Candidate]:
        pass
    
    @abstractmethod
    async def save(self, candidate: Candidate) -> Candidate:
        pass

class CandidateRepository(ICandidateRepository):
    def __init__(self, session: Session):
        self.session = session
    
    async def find_by_id(self, candidate_id: int) -> Optional[Candidate]:
        result = self.session.query(CandidateModel).filter(
            CandidateModel.id == candidate_id
        ).first()
        return Candidate(**result) if result else None
    
    async def save(self, candidate: Candidate) -> Candidate:
        model = CandidateModel(**candidate.dict())
        self.session.add(model)
        self.session.commit()
        return Candidate(**model)
```

## Testing Standards

### Test File Structure

- **Naming Convention**: `test_[module_name].py`
- **Test Location**: `tests/` directory mirroring `src/` structure
- **Test Framework**: pytest
- **Coverage Threshold**: 90% for all metrics

### Test Organization Pattern

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

class TestCandidateService:
    """Test suite for CandidateService"""
    
    @pytest.fixture
    def mock_repository(self):
        return AsyncMock()
    
    @pytest.fixture
    def service(self, mock_repository):
        return CandidateService(repository=mock_repository)
    
    class TestFindById:
        """Tests for find_by_id method"""
        
        @pytest.mark.asyncio
        async def test_should_return_candidate_when_found(
            self, service, mock_repository
        ):
            # Arrange
            candidate_id = 1
            expected_candidate = Candidate(
                id=1, first_name="John", last_name="Doe", email="john@example.com"
            )
            mock_repository.find_by_id.return_value = expected_candidate
            
            # Act
            result = await service.find_by_id(candidate_id)
            
            # Assert
            assert result == expected_candidate
            mock_repository.find_by_id.assert_called_once_with(candidate_id)
```

### Test Case Naming Convention

- **Descriptive Names**: Use `test_should_[behavior]_when_[condition]`
- **Group Related Tests**: Use nested classes or describe blocks
- **Behavior-Driven**: Focus on behavior, not implementation

```python
class TestCandidateService:
    class TestCreateCandidate:
        @pytest.mark.asyncio
        async def test_should_create_candidate_when_valid_data_provided(self):
            pass
        
        @pytest.mark.asyncio
        async def test_should_raise_error_when_email_invalid(self):
            pass
        
        @pytest.mark.asyncio
        async def test_should_raise_error_when_duplicate_email(self):
            pass
```

### Test Structure (AAA Pattern)

Always follow Arrange-Act-Assert pattern:

```python
@pytest.mark.asyncio
async def test_should_update_candidate_stage_when_valid_data_provided(self):
    # Arrange - Setup test data and mocks
    candidate_id = 1
    application_id = 1
    new_interview_step = 2
    mock_candidate = Candidate(id=candidate_id)
    
    # Act - Execute the function under test
    result = await service.update_candidate_stage(
        candidate_id, application_id, new_interview_step
    )
    
    # Assert - Verify expected behavior
    assert result.interview_step == new_interview_step
```

### Mocking Standards

- **Mock All External Dependencies**: Services, repositories, database
- **Use AsyncMock**: For async operations
- **Clear Mock Setup**: Use fixtures for common mocks
- **Verify Interactions**: Check mock calls and arguments

```python
@pytest.fixture
def mock_repository():
    return AsyncMock(spec=ICandidateRepository)

@pytest.fixture
def mock_email_service():
    return MagicMock(spec=EmailService)

@pytest.mark.asyncio
async def test_create_and_notify(mock_repository, mock_email_service):
    mock_repository.save.return_value = expected_candidate
    
    service = CandidateService(
        repository=mock_repository,
        email_service=mock_email_service
    )
    
    result = await service.create_and_notify(data)
    
    mock_repository.save.assert_called_once()
    mock_email_service.send.assert_called_once_with(
        expected_candidate.email
    )
```

### Test Coverage Requirements

- **Happy Path**: Valid inputs producing expected outputs
- **Error Handling**: Invalid inputs and error scenarios
- **Edge Cases**: Boundary values, null/undefined inputs
- **Validation**: Input validation, business rule enforcement
- **Integration Points**: External service interactions

```python
class TestCandidateService:
    # Happy path
    async def test_should_return_candidate_when_exists(self):
        pass
    
    # Error handling
    async def test_should_raise_not_found_error_when_not_exists(self):
        pass
    
    # Edge cases
    async def test_should_handle_empty_first_name(self):
        pass
    
    # Validation
    async def test_should_reject_invalid_email_format(self):
        pass
    
    # Integration
    async def test_should_call_repository_save_exactly_once(self):
        pass
```

### Integration Testing

- **Database Testing**: Test with real or test database
- **Service Integration**: Test service layer with mocked repositories
- **API Testing**: Test FastAPI endpoints with test client

```python
@pytest.mark.asyncio
async def test_create_candidate_integration(async_client, db_session):
    """Integration test for candidate creation endpoint"""
    # Arrange
    data = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com"
    }
    
    # Act
    response = await async_client.post("/candidates", json=data)
    
    # Assert
    assert response.status_code == 201
    assert response.json()["data"]["email"] == data["email"]
    
    # Verify in database
    db_candidate = db_session.query(CandidateModel).filter_by(
        email=data["email"]
    ).first()
    assert db_candidate is not None
```

## Performance Best Practices

### Database Query Optimization

- **Eager Loading**: Use `joinedload` or `selectinload` to avoid N+1 queries
- **Specific Columns**: Select only needed columns
- **Indexes**: Ensure proper database indexes

```python
# Good: Eager loading relationships
from sqlalchemy.orm import joinedload

candidates = session.query(CandidateModel).options(
    joinedload(CandidateModel.educations),
    joinedload(CandidateModel.applications)
).all()

# Avoid: N+1 queries
candidates = session.query(CandidateModel).all()
for candidate in candidates:
    educations = session.query(EducationModel).filter_by(
        candidate_id=candidate.id
    ).all()
```

### Async Patterns

- **Use async/await**: Use async for I/O operations
- **Concurrent Operations**: Use `asyncio.gather()` for parallel operations
- **Connection Pooling**: Use connection pools for database

```python
# Good: Async operations
async def get_candidates_and_positions():
    candidates, positions = await asyncio.gather(
        candidate_service.find_all(),
        position_service.find_all()
    )
    return candidates, positions

# Good: Connection pooling
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    "postgresql+asyncpg://...",
    poolclass=AsyncPool,
    pool_size=20,
    max_overflow=0
)
```

### Error Handling Performance

- **Early Returns**: Return early to avoid unnecessary processing
- **Error Propagation**: Let exceptions propagate naturally
- **Caching**: Cache expensive operations when appropriate

## Security Best Practices

### Input Validation

- **Validate All Inputs**: Use Pydantic for automatic validation
- **Sanitize Data**: Clean data before processing
- **Type Safety**: Leverage Python type hints

```python
from pydantic import BaseModel, validator

class CandidateCreateDTO(BaseModel):
    first_name: str
    email: EmailStr
    
    @validator("first_name")
    def validate_first_name(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("First name too short")
        return v.strip()
```

### Environment Variables

- **Never Commit Secrets**: Use `.env` files (not committed)
- **Validate at Startup**: Check required variables exist
- **Type Safety**: Use Pydantic settings for configuration

```python
from pydantic import BaseSettings

class Settings(BaseSettings):
    database_url: str
    secret_key: str
    debug: bool = False
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### Dependency Injection

- **Inject Dependencies**: Pass dependencies through constructors
- **Avoid Global State**: Don't use global variables
- **Testability**: Improves testing and modularity

```python
# Good: Dependency injection
class CandidateService:
    def __init__(self, repository: ICandidateRepository):
        self.repository = repository

# Usage
repository = CandidateRepository(session)
service = CandidateService(repository)
```

## Development Workflow

### Git Workflow

- **Feature Branches**: Use descriptive branch names
- **Descriptive Commits**: Write clear commit messages in English
- **Code Review**: Review before merging
- **Small Branches**: Keep focused and manageable

### Development Scripts

```bash
python -m venv venv          # Create virtual environment
source venv/bin/activate     # Activate (Linux/macOS)
pip install -r requirements.txt  # Install dependencies

uvicorn src.main:app --reload  # Run dev server
pytest                        # Run tests
pytest --cov=src            # Run tests with coverage
ruff check src/              # Lint code
mypy src/                    # Type checking
```

### Code Quality

- **Type Checking**: Run mypy to catch type errors
- **Linting**: Use ruff for code style
- **Testing**: Ensure 90% coverage
- **Pre-commit Hooks**: Automate checks before commits

## Serverless Deployment

### AWS Lambda Configuration

- **Lambda Handler**: Entry point in `src/lambda_handler.py`
- **FastAPI Wrapper**: Use `mangum` to wrap FastAPI app
- **Environment Variables**: Configure in serverless.yml

```python
from mangum import Mangum
from src.main import app

handler = Mangum(app)
```

### Serverless Framework

- **Configuration**: `serverless.yml` defines Lambda setup
- **Build Process**: Package application for Lambda
- **Deployment**: Deploy using Serverless CLI

```yaml
service: candidate-api

provider:
  name: aws
  runtime: python3.10
  environment:
    DATABASE_URL: ${ssm:database_url}

functions:
  api:
    handler: src/lambda_handler.handler
    events:
      - http:
          path: /{proxy+}
          method: ANY
```

---

This document provides the foundation for maintaining code quality and consistency across the Python backend application. All team members should follow these practices to ensure a maintainable, scalable, and testable codebase.