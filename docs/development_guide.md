# Development Guide

This guide provides step-by-step instructions for setting up the development environment and running tests for the LTI ATS system (Python Backend + React Frontend).

## 🚀 Setup Instructions

### Prerequisites

Ensure you have the following installed:
- **Python** (v3.10 or higher)
- **Node.js** (v16 or higher)
- **npm** (v8 or higher)
- **Docker** and **Docker Compose**
- **Git**
- **pip** (Python package manager, usually included with Python)

Verify installations:
```bash
python --version
node --version
npm --version
docker --version
docker-compose --version
```

### 1. Clone the Repository

```bash
git clone git@github.com:LIDR-academy/AI4Devs-LTI-extended.git
cd AI4Devs-LTI-extended
```

### 2. Environment Configuration

Create environment files for both backend and frontend:

**Backend Environment** (`backend/.env`):
```env
# Database Configuration
DATABASE_URL=postgresql://LTIdbUser:D1ymf8wyQEGthFR1E9xhCq@localhost:5432/LTIdb

# Application Configuration
APP_PORT=8000
APP_HOST=0.0.0.0
DEBUG=true
ENV=development

# Logging
LOG_LEVEL=INFO

# Optional: External Services
# SMTP_SERVER=
# SMTP_PORT=
# SMTP_USER=
# SMTP_PASSWORD=
```

**Frontend Environment** (`frontend/.env`):
```env
REACT_APP_API_URL=http://localhost:8000
```

### 3. Database Setup (PostgreSQL with Docker)

Start the PostgreSQL database using Docker Compose:

```bash
# From project root, start PostgreSQL container
docker-compose up -d

# Verify the database is running
docker-compose ps

# Check logs if needed
docker-compose logs db
```

The PostgreSQL database will be available at:
- **Host**: `localhost`
- **Port**: `5432`
- **Database**: `LTIdb`
- **Username**: `LTIdbUser`
- **Password**: `D1ymf8wyQEGthFR1E9xhCq`

**Verify Connection:**
```bash
# Using psql (if installed)
psql -h localhost -U LTIdbUser -d LTIdb -c "SELECT 1;"

# Or test through backend (after setup)
curl http://localhost:8000/health
```

### 4. Backend Setup

Navigate to the backend directory and set up the Python environment:

```bash
# Navigate to backend directory
cd backend

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate

# On Windows:
# venv\Scripts\activate

# Verify virtual environment is active (should show (venv) prefix)
which python  # Linux/macOS
where python  # Windows

# Install dependencies
pip install -r requirements.txt

# Generate SQLAlchemy models (if using auto-generation)
# This step depends on your project setup

# Run database migrations (Alembic)
alembic upgrade head

# (Optional) Seed the database with sample data
python -m alembic stamp head
python scripts/seed_db.py

# Start the development server
uvicorn src.main:app --reload
```

The backend API will be available at `http://localhost:8000`

**API Documentation:**
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

**Verify Backend is Running:**
```bash
curl http://localhost:8000/health
# or
curl -X GET http://localhost:8000/docs
```

### 5. Frontend Setup

Navigate to the frontend directory and set up Node.js dependencies:

```bash
# Navigate to frontend directory (from project root)
cd frontend

# Install dependencies
npm install

# Verify dependencies installed
npm list

# Start the development server
npm start
```

The frontend application will be available at `http://localhost:3000`

**Note**: The frontend will automatically proxy requests to `http://localhost:8000` based on `.env` configuration.

### 6. Testing Setup

#### Backend Testing with pytest

```bash
# From backend directory
cd backend

# Ensure virtual environment is activated
source venv/bin/activate

# Run all tests
pytest

# Run tests in watch mode (requires pytest-watch)
ptw

# Run tests with coverage report
pytest --cov=src tests/

# Run specific test file
pytest tests/unit/test_candidate_service.py

# Run tests matching a pattern
pytest -k "test_create" -v

# Run tests with detailed output
pytest -v --tb=short

# Generate coverage report in HTML
pytest --cov=src --cov-report=html tests/
# Open coverage report
open htmlcov/index.html  # macOS
# or
xdg-open htmlcov/index.html  # Linux
```

#### Frontend Testing

```bash
# From frontend directory
cd frontend

# Run unit tests
npm test

# Run tests in watch mode
npm test -- --watch

# Run tests with coverage
npm test -- --coverage

# Run E2E tests with Playwright (headed mode - see browser)
npm run playwright:headed

# Run E2E tests headlessly
npm run playwright:run

# Run specific Playwright test
npm run playwright:run -- tests/e2e/candidates.spec.ts

# Open Playwright Inspector for debugging
npm run playwright:debug
```

## 🧪 Testing

### Backend Testing

**Test Structure:**
```
backend/
├── tests/
│   ├── conftest.py              # pytest fixtures
│   ├── unit/
│   │   ├── test_candidate_service.py
│   │   ├── test_validators.py
│   │   └── ...
│   ├── integration/
│   │   ├── test_api_candidates.py
│   │   └── ...
│   └── factories.py             # Test data builders
```

**Running Tests:**
```bash
cd backend

# Run all tests with coverage
pytest --cov=src --cov-report=html tests/

# Run only unit tests
pytest tests/unit/ -v

# Run only integration tests
pytest tests/integration/ -v

# Run with minimal output
pytest -q

# Run with detailed output including print statements
pytest -s -v

# Stop at first failure
pytest -x

# Run last N failed tests
pytest --lf

# Run N times to check flakiness
pytest --count=5
```

**Coverage Requirements:**
- Minimum 90% coverage for branches, functions, lines, and statements
- View HTML coverage report: `pytest --cov=src --cov-report=html`

### Frontend Testing

**Test Structure:**
```
frontend/
├── src/
│   ├── __tests__/
│   │   ├── unit/
│   │   │   ├── components/
│   │   │   └── utils/
│   │   └── integration/
├── tests/
│   ├── e2e/
│   │   ├── candidates.spec.ts
│   │   ├── applications.spec.ts
│   │   └── positions.spec.ts
│   ├── fixtures/
│   └── helpers/
├── playwright.config.ts
└── package.json
```

**Running Tests:**
```bash
cd frontend

# Run all Jest unit tests
npm test

# Run tests matching a pattern
npm test -- candidates

# Run tests with coverage
npm test -- --coverage

# Update snapshots
npm test -- -u

# Playwright: Run all E2E tests
npm run playwright:run

# Playwright: Run tests in headed mode (see browser)
npm run playwright:headed

# Playwright: Run tests in debug mode (interactive)
npm run playwright:debug

# Playwright: Run specific test file
npm run playwright:run -- tests/e2e/candidates.spec.ts

# Playwright: Run tests matching pattern
npm run playwright:run -- --grep "candidate"

# Playwright: Run tests in specific browser
npm run playwright:run -- --project=chromium
npm run playwright:run -- --project=firefox
npm run playwright:run -- --project=webkit

# Playwright: Generate HTML report
npm run playwright:run
# Then open: npx playwright show-report
```

## 📝 Development Workflow

### Making Changes

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/candidate-filtering
   ```

2. **Make your changes following TDD:**
   - Write failing tests first
   - Implement the feature
   - Ensure all tests pass

3. **Run tests and linters (Backend):**
   ```bash
   cd backend
   pytest --cov=src
   mypy src/
   ruff check src/
   ```

4. **Commit with clear messages:**
   ```bash
   git commit -m "feat: add candidate filtering by position"
   ```

5. **Push and create Pull Request:**
   ```bash
   git push origin feature/candidate-filtering
   ```

### Common Development Commands

**Backend:**
```bash
# Start dev server with hot reload
uvicorn src.main:app --reload

# Run migrations
alembic upgrade head
alembic downgrade -1

# Create new migration
alembic revision --autogenerate -m "add candidate status field"

# Check code style
ruff check src/
ruff format src/

# Type checking
mypy src/

# Run specific tests
pytest tests/unit/application/test_candidate_service.py -v
```

**Frontend:**
```bash
# Start dev server
npm start

# Build for production
npm run build

# Run linter
npm run lint

# Format code
npm run format

# Run unit tests with coverage
npm test -- --coverage

# Run E2E tests with Playwright
npm run playwright:run

# Run E2E tests in headed mode (see browser)
npm run playwright:headed

# Run E2E tests in debug mode (interactive)
npm run playwright:debug

# Install/update Playwright browsers
npx playwright install

# View test report
npx playwright show-report
```

### Database Management

```bash
# Start database
docker-compose up -d

# Stop database
docker-compose down

# View database logs
docker-compose logs -f db

# Access PostgreSQL directly
docker-compose exec db psql -U LTIdbUser -d LTIdb

# Run migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1

# Create migration from model changes
alembic revision --autogenerate -m "migration description"
```

## 🐛 Troubleshooting

### Backend Issues

**Virtual environment not activating:**
```bash
# Ensure you're in backend directory
cd backend

# Recreate virtual environment
rm -rf venv
python -m venv venv
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

**Database connection errors:**
```bash
# Check if Docker container is running
docker-compose ps

# Check database logs
docker-compose logs db

# Restart database
docker-compose down
docker-compose up -d

# Verify .env DATABASE_URL is correct
cat .env | grep DATABASE_URL
```

**Port 8000 already in use:**
```bash
# Find process using port
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill process
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows

# Or use different port
uvicorn src.main:app --reload --port 8001
```

**Import errors in tests:**
```bash
# Ensure backend is in PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or run pytest from backend directory
cd backend
pytest tests/
```

### Frontend Issues

**npm install fails:**
```bash
# Clear npm cache
npm cache clean --force

# Remove node_modules and lock file
rm -rf node_modules package-lock.json

# Reinstall
npm install
```

**Port 3000 already in use:**
```bash
# Use different port
PORT=3001 npm start

# Or kill existing process
lsof -i :3000  # macOS/Linux
kill -9 <PID>

netstat -ano | findstr :3000  # Windows
taskkill /PID <PID> /F
```

**Playwright tests failing or elements not found:**
```bash
# Run tests in headed mode to see browser
npm run playwright:headed

# Run tests in debug mode (interactive)
npm run playwright:debug

# Use slow motion to see actions step by step
npm run playwright:run -- --headed --project=chromium --slowmo=1000

# Run with trace for debugging
npm run playwright:run -- --trace on

# View test report
npx playwright show-report

# Check specific browser
npm run playwright:run -- --project=chromium -v

# Run with timestamps
npm run playwright:run -- -v --output
```

**Playwright browser not installed:**
```bash
# Install/update browsers
npx playwright install

# Install specific browser
npx playwright install chromium

# Reinstall all
npx playwright install --with-deps
```

**Playwright connection timeout:**
```bash
# Increase timeout in playwright.config.ts
timeout: 30000,  // 30 seconds

# Or run with increased timeout
npm run playwright:run -- --timeout 30000
```

### Database Issues

**Migrations fail:**
```bash
# Check migration status
alembic current

# View migration history
alembic history

# Create new migration
alembic revision --autogenerate -m "fix: correct column type"

# Run migration
alembic upgrade head
```

**Data inconsistency:**
```bash
# Drop and recreate database (CAREFUL!)
docker-compose down -v
docker-compose up -d

# Run migrations
alembic upgrade head

# Seed if available
python scripts/seed_db.py
```

## 📚 Useful Resources

- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **SQLAlchemy Documentation**: https://docs.sqlalchemy.org/
- **Alembic Documentation**: https://alembic.sqlalchemy.org/
- **pytest Documentation**: https://docs.pytest.org/
- **React Documentation**: https://react.dev/
- **Cypress Documentation**: https://docs.cypress.io/

## 🔗 Project Structure

```
.
├── backend/                    # Python FastAPI backend
│   ├── src/
│   │   ├── domain/            # Domain entities and interfaces
│   │   ├── application/       # Services and DTOs
│   │   ├── infrastructure/    # Database and external services
│   │   ├── presentation/      # Routes and handlers
│   │   └── main.py           # FastAPI app entry point
│   ├── tests/                 # Test suite
│   ├── migrations/            # Alembic migrations
│   ├── requirements.txt       # Python dependencies
│   ├── pytest.ini             # pytest configuration
│   └── .env                   # Environment variables
│
├── frontend/                  # React frontend
│   ├── src/
│   │   ├── components/        # React components
│   │   ├── pages/            # Page components
│   │   ├── utils/            # Utility functions
│   │   ├── __tests__/        # Unit tests
│   │   └── App.js            # Main app component
│   ├── cypress/              # E2E tests
│   ├── package.json          # npm dependencies
│   ├── .env                  # Environment variables
│   └── public/               # Static files
│
├── docker-compose.yml        # Docker services configuration
├── .gitignore               # Git ignore rules
└── README.md                # Project overview
```

## 💡 Best Practices

1. **Always use virtual environment** for backend development
2. **Keep `.env` files out of version control** (use `.env.example`)
3. **Run tests before committing** code
4. **Use feature branches** for all development
5. **Follow the project's coding standards** (see CLAUDE.md)
6. **Document your changes** with clear commit messages
7. **Maintain 90% test coverage** for backend code
8. **Use type hints** in all Python code
9. **Follow DDD principles** for backend architecture
10. **Reload frontend after `.env` changes** to pick up new API URL

---

For more information about coding standards and guidelines, see:
- [Backend Standards (Python)](./backend-standards-python.md)
- [OpenCode Guidelines](./opencode-guidelines.md)
- [Development Rules (CLAUDE.md)](./CLAUDE.md)