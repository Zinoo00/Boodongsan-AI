# 🏠 Boodongsan Backend

## 📦 uv Package Management

This project uses [uv](https://docs.astral.sh/uv/) for fast, modern Python package management. 

### ⚡ Quick Start with uv

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the project and navigate to backend
cd backend/

# Create virtual environment and install dependencies
uv sync

# Activate the virtual environment  
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows

# Install with optional dependency groups
uv sync --group dev --group ml --group data-collection
```

## 🎯 Dependency Groups

The project organizes dependencies into logical groups for flexible installation:

### Core Dependencies (default)
Always installed - web framework, database, AI services, security, etc.

### Optional Groups
```bash
# Development tools
uv sync --group dev

# Machine learning features  
uv sync --group ml

# Data collection capabilities
uv sync --group data-collection

# Natural language processing (Korean)
uv sync --group nlp

# Image processing
uv sync --group image-processing

# Background task processing
uv sync --group async-tasks

# Data validation tools
uv sync --group validation

# Visualization tools
uv sync --group visualization

# Enhanced caching
uv sync --group caching

# Advanced configuration
uv sync --group config

# XML processing
uv sync --group xml

# Install multiple groups
uv sync --group dev --group ml --group data-collection
```

## 🚀 Development Workflow

### Environment Setup
```bash
# Full development environment
uv sync --group dev --group ml

# Run development server
uv run uvicorn api.main:app --reload

# Or use the high-performance server
uv run granian --interface asgi api.main:app --host 0.0.0.0 --port 8000
```

### Code Quality Tools
```bash
# Linting and formatting (using ruff)
uv run ruff check .           # Check for issues
uv run ruff format .          # Format code
uv run ruff check --fix .     # Auto-fix issues

# Type checking
uv run mypy .

# Run tests
uv run pytest                 # Basic test run
uv run pytest --cov=backend   # With coverage
```

### Dependency Management
```bash
# Add new dependency to core
uv add fastapi

# Add to specific group
uv add --group dev pytest-asyncio

# Remove dependency
uv remove package-name

# Update all dependencies
uv sync --upgrade

# Lock dependencies without sync
uv lock

# Export requirements (compatibility)
uv export --format requirements-txt > requirements.txt
```

## 🏗️ Architecture

```
backend/
├── 📁 ai/               # AI services (Bedrock, LangChain)
├── 📁 api/              # FastAPI application
│   ├── 📁 middleware/   # Custom middleware
│   └── 📁 routers/      # API endpoints
├── 📁 core/             # Core configuration
├── 📁 data/             # Data collection services
├── 📁 database/         # Database models and connections
├── 📁 models/           # Pydantic/SQLAlchemy models
├── 📁 services/         # Business logic services
├── 📄 pyproject.toml    # uv configuration
└── 📄 uv.lock          # Locked dependencies
```

## 🔧 Configuration

### Environment Variables
Copy `.env.example` to `.env` and configure:

```bash
# Database - Supabase (required)
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_key
SUPABASE_DB_PASSWORD=your_supabase_db_password  # from Supabase Project Settings → Database

# Redis Cache
REDIS_URL=redis://localhost:6379/0

# Vector Database
CHROMADB_HOST=localhost
CHROMADB_PORT=8000
QDRANT_URL=your_qdrant_url  # Optional - legacy support
QDRANT_API_KEY=your_qdrant_key

# AI Services
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
CLOUDFLARE_ACCOUNT_ID=your_cf_account
CLOUDFLARE_API_TOKEN=your_cf_token

# Korean Real Estate APIs
MOLIT_API_KEY=your_molit_key
```

## 🗄️ Database Setup

### Supabase Integration

The application now uses the Supabase Python client library for enhanced database connectivity:

- **Primary Database**: Supabase PostgreSQL via Python client
- **Connection Management**: Automatic retry logic and health monitoring
- **Authentication**: Service role key for server-side operations
- **Real-time capabilities**: Ready for Supabase real-time subscriptions

### uv Configuration Features

The `pyproject.toml` includes comprehensive tool configuration:

- **Ruff**: Fast linting and formatting with Python 3.11+ rules
- **MyPy**: Strict type checking configuration  
- **Pytest**: Async testing setup with coverage
- **Dependency Groups**: Modular installation options

## 🎯 uv Advantages for This Project

1. **⚡ Speed**: 10-100x faster than pip for installation and resolution
2. **🔒 Security**: Built-in lock file ensures reproducible builds  
3. **📦 Modularity**: Dependency groups for feature-based installation
4. **🐍 Python Management**: Built-in Python version management
5. **🔄 Compatibility**: Drop-in replacement for pip/poetry/pipenv
6. **🛠️ Tooling**: Integrated project management commands

## 📊 Performance Optimization

### uv Performance Tips
```bash
# Pre-compiled wheels cache
uv cache clean       # Clear cache if needed
uv cache dir         # Check cache location

# Parallel installations
uv sync --no-cache   # Skip cache for fresh install

# Minimal installs for production
uv sync --no-dev     # Skip development dependencies
```

### Production Deployment
```bash
# Multi-stage Docker builds with uv
FROM python:3.11-slim as builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache

# Runtime stage
FROM python:3.11-slim
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
```

## 🧪 Testing

```bash
# Run all tests
uv run pytest

# With coverage reporting
uv run pytest --cov=backend --cov-report=html

# Run specific test files
uv run pytest tests/test_api.py

# Async test debugging
uv run pytest -v --log-level=DEBUG
```

## 📈 Monitoring

The application includes:
- **Health checks**: `/api/v1/health` with Supabase and Redis status
- **Metrics**: Prometheus metrics on port 9090 (if enabled)
- **Logging**: Structured logging with configurable levels
- **Database monitoring**: Supabase connection health and cache statistics

### Health Check Response
```json
{
  "supabase": {
    "status": true,
    "latency_ms": 45.2
  },
  "redis": {
    "status": true,
    "latency_ms": 12.3,
    "memory_usage": {
      "used_memory": "2.5MB",
      "used_memory_peak": "5.1MB"
    }
  },
  "cache_stats": {
    "hits": 1250,
    "misses": 89,
    "hit_rate_percent": 93.35
  }
}
```

## 📋 Recent Changes

### v1.1.0 - Supabase Integration (Latest)
- **✅ Migration to Supabase Client**: Replaced SQLAlchemy/asyncpg with Supabase Python client
- **✅ Enhanced Connection Management**: Improved error handling and retry logic
- **✅ Service Layer Updates**: All services now use Supabase client operations
- **✅ LangChain Compatibility**: Fixed deprecated import warnings
- **✅ Performance Improvements**: Streamlined database operations and connection pooling

## 🤝 Contributing

1. Install development environment: `uv sync --group dev`
2. Set up pre-commit: `uv run pre-commit install` (if using)
3. Run tests: `uv run pytest`
4. Check code quality: `uv run ruff check .`
5. Format code: `uv run ruff format .`

## 📝 Migration from pip/poetry

If migrating from existing tools:

```bash
# From requirements.txt
uv add $(cat requirements.txt)

# From poetry
# Export pyproject.toml deps, then import to uv

# From pipenv  
# Export Pipfile deps, then import to uv
```

## 🔗 Useful Links

- [uv Documentation](https://docs.astral.sh/uv/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic V2 Migration](https://docs.pydantic.dev/2.0/migration/)
- [Ruff Configuration](https://docs.astral.sh/ruff/configuration/)

---

**Korean Real Estate RAG AI Backend** - Powered by uv for optimal Python package management