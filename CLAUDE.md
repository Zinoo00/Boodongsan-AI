# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BODA (BOoDongSan AI) is a Korean Real Estate RAG (Retrieval Augmented Generation) AI Chatbot that provides property recommendations and government policy matching. The system uses LightRAG as the primary knowledge graph-based RAG system with FastAPI backend, dual AI providers (AWS Bedrock + Cloudflare Workers AI), ChromaDB for vector search, and Supabase as the sole database.

## Essential Commands

### Development Setup

```bash
# Install uv package manager (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup environment and install dependencies
cd backend
cp .env.example .env
# Edit .env with required API keys
uv sync

# Start external services only (Redis, ChromaDB)
docker-compose up -d redis chroma

# Run development server with hot reload
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker Operations

```bash
# Start all services (production-like)
docker-compose up -d

# View logs
docker-compose logs -f backend

# Restart specific service
docker-compose restart backend

# Clean restart
docker-compose down -v && docker-compose up -d
```

### Code Quality & Testing

```bash
# Lint and format code
uv run ruff check .
uv run ruff format .

# Type checking
uv run mypy .

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=backend --cov-report=html

# Run specific test file
uv run pytest tests/test_api.py
```

### Dependency Management

```bash
# Add new package
uv add package-name

# Add dev dependency
uv add --group dev package-name

# Update all dependencies
uv sync --upgrade

# Generate requirements.txt for compatibility
uv pip compile pyproject.toml -o requirements.txt
```

## Architecture Overview

### Architecture Principles

**Simplified Stack**: This project has been refactored to remove over-engineering and focus on:

- **Single Database**: Supabase only (no SQLAlchemy ORM, no dual database)
- **Knowledge Graph RAG**: LightRAG as primary system (no hybrid vector abstraction)
- **Direct Integrations**: Services use Supabase and AWS OpenSearch directly (no unnecessary abstraction layers)
- **Unified Data Service**: DataService handles both properties and policies (replaces 2 broken services)
- **6 Core Services**: Down from 10 services, 53% code reduction (12,651 → ~6,000 lines)

**What Was Removed**:
- ❌ SQLAlchemy ORM layer (1,161 lines unused code)
- ❌ `database/` folder (connection.py, models.py, repositories.py)
- ❌ PropertyService and PolicyService (broken, returning dummy data)
- ❌ HybridVectorService abstraction (300 lines)
- ❌ Qdrant vector database support (optional, unused)
- ❌ VectorService abstraction layer (250 lines)

**What Remains** (6 services):
- ✅ AIService - Dual provider support with circuit breaker
- ✅ LightRAGService - Primary knowledge graph RAG
- ✅ RAGService - Orchestration with LightRAG + AWS OpenSearch fallback
- ✅ OpenSearchVectorService - Direct vector operations
- ✅ DataService - Unified properties + policies (NEW)
- ✅ UserService - User profiles and conversation history

### System Components

**Entry Point**: `backend/api/main.py` - FastAPI application with lifespan management

- Initializes all services on startup
- Services stored in `app.state` for dependency injection
- Graceful shutdown and cleanup on app termination

**Configuration**: `backend/core/config.py` - Pydantic Settings with comprehensive validation

- Environment-based configuration (development/staging/production)
- Validates all settings at startup with clear error messages
- Uses `.env` file for sensitive credentials

**Database Layer**: `backend/core/database.py` - Supabase client with connection management

- Sole database: Supabase PostgreSQL (no SQLAlchemy, no ORM layer)
- Direct Supabase client usage for all database operations
- Connection pooling and retry logic built-in
- Health checks and automatic reconnection
- Async operations via `execute_supabase_operation` helper

### Service Architecture Pattern

All services follow a consistent initialization pattern:

```python
# Services are singletons initialized during app startup in api/main.py
ai_service = AIService()
await ai_service.initialize()

# AWS OpenSearch for vector search (direct, no abstraction layer)
vector_service = OpenSearchVectorService()
await vector_service.initialize()

# LightRAG as primary RAG system
lightrag_service = LightRAGService()
await lightrag_service.initialize()

# Unified data service for properties and policies
data_service = DataService()

# Services composed together
rag_service = RAGService(
    vector_service=vector_service,
    lightrag_service=lightrag_service,
    ai_service=ai_service,
    data_service=data_service,
    user_service=user_service,
)
```

### Key Services

**AIService** (`services/ai_service.py`):

- Dual provider support: AWS Bedrock (complex reasoning) + Cloudflare Workers AI (simple chat)
- Circuit breaker pattern with automatic failover between providers
- Strategy-based model selection (simple_chat → Cloudflare, complex_analysis → Bedrock)
- Exponential backoff retry logic for transient failures

**LightRAGService** (`services/lightrag_service.py`):

- Primary RAG system using knowledge graph-based approach
- Entity extraction: 매물 (properties), 정책 (policies), 지역 (locations), 가격대 (price ranges), 조건 (conditions)
- Relationship mapping between entities for context-aware recommendations
- Bedrock integration via custom LLM and Embedding adapters
- Hybrid search: Naive (simple keyword), Local (entity-focused), Global (comprehensive), Mixed (balanced)
- Automatic knowledge graph updates from new property and policy data
- Enabled by default (USE_LIGHTRAG=true)

**RAGService** (`services/rag_service.py`):

- Orchestrates RAG pipeline: query → LightRAG search → context enrichment → AI response
- Fallback to legacy vector search if LightRAG unavailable
- Multi-layer caching (RAG response, entity extraction, embeddings)
- Performance metrics tracking (cache hit rate, processing time, success rate)
- Query validation and sanitization with Pydantic models

**OpenSearchVectorService** (`services/opensearch_service.py`):

- Direct AWS OpenSearch client for Titan-derived vector embeddings
- k-NN similarity search with circuit breaker and retry safeguards
- Embedding generation via AWS Bedrock Titan model (async adapter)
- Basic indexing helpers for document upserts and deletions

**DataService** (`services/data_service.py`):

- Unified service for properties and policies data (replaces PropertyService + PolicyService)
- Property operations: create, search, update, delete (soft delete)
- Policy operations: create, search, match_user, get_all
- Direct Supabase integration via execute_supabase_operation helper
- Eligibility scoring algorithm for policy matching
- Statistics and analytics methods

### API Router Structure

Routers are mounted in `api/main.py` with versioned prefix `/api/v1/`:

- **chat.py**: Chatbot conversations, message history
- **health.py**: Health checks, system info, service status
- **policies.py**: Policy matching, eligibility checks
- **properties.py**: Property search and recommendations
- **users.py**: User profiles, preferences, history

### Middleware Chain

Applied in order (from `api/main.py`):

1. TrustedHostMiddleware (production only)
2. CORSMiddleware (configurable origins)
3. AuthMiddleware (JWT validation)
4. CacheMiddleware (Redis-based response caching)

## Critical Patterns

### Error Handling

**Structured Exceptions** (`core/exceptions.py`):

- Base: `BoodongsanException` with error codes and HTTP status
- Specialized: `DatabaseException`, `AIServiceException`, `ValidationException`, etc.
- Always include context for debugging: `raise AIServiceException(f"Bedrock failed: {error}", details={...})`

### Circuit Breaker Pattern (AI Service)

```python
# In ai_service.py
if self._circuit_breaker_open(provider):
    logger.warning(f"{provider} circuit breaker open, using fallback")
    return await self._generate_with_fallback(...)

try:
    response = await self._call_provider(provider, ...)
    self._record_success(provider)
    return response
except Exception as e:
    self._record_failure(provider)
    if failures > threshold:
        self._open_circuit_breaker(provider)
    raise
```

### Caching Strategy

**Multi-layer approach** (from `rag_service.py`):

- L1: RAG response cache (30min TTL) - full query → response
- L2: Entity extraction cache (15min TTL) - parsed user intent
- L3: Embedding cache (2hr TTL) - vectorized queries
- L4: Property search cache (15min TTL) - search results

Cache keys are deterministic: `hash(query + user_context + filters)`

### Async/Await Patterns

All I/O operations are async:

```python
# Database
async with supabase.table("properties").select("*").execute() as result:
    properties = result.data

# AI calls with timeout
response = await asyncio.wait_for(
    ai_service.generate_response(...),
    timeout=RAG_MAX_PROCESSING_TIME
)

# Parallel operations
results = await asyncio.gather(
    vector_service.search(...),
    property_service.get_nearby(...),
    policy_service.match_user(...),
)
```

## Environment Configuration

### Required Environment Variables

```bash
# AWS Bedrock (primary AI provider)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v1

# Supabase (sole database)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

# Cloudflare Workers AI (secondary AI provider)
CLOUDFLARE_ACCOUNT_ID=
CLOUDFLARE_API_TOKEN=
CLOUDFLARE_MODEL_NAME=@cf/meta/llama-2-7b-chat-int8

# Redis (caching)
REDIS_URL=redis://localhost:6379/0

# ChromaDB (vector search)
CHROMADB_HOST=localhost
CHROMADB_PORT=8001

# LightRAG configuration
USE_LIGHTRAG=true  # Enable LightRAG as primary RAG system
LIGHTRAG_WORKING_DIR=./data/lightrag  # Knowledge graph storage directory

# Korean Real Estate API
MOLIT_API_KEY=  # 국토교통부 API key
```

### Configuration Hierarchy

1. `.env` file (development, git-ignored)
2. Environment variables (production, Kubernetes secrets)
3. Default values in `core/config.py`

## Database Schema

### Supabase Tables

**properties**: Real estate listings (migration: `002_properties_schema.sql`)

- Core fields: id (uuid), address, district (구), dong (동), detail_address
- Property info: property_type, transaction_type, price, deposit, monthly_rent, maintenance_fee
- Area info: area_exclusive (전용면적), area_supply (공급면적), area_pyeong (평수, auto-calculated)
- Building info: room_count, bathroom_count, floor, total_floors, building_year
- Location: latitude, longitude for geospatial queries
- Features: amenities (text[]), nearby_facilities (jsonb), parking_available
- Metadata: listing_status (active/sold/expired/pending/hidden), view_count, favorite_count
- Timestamps: created_at, updated_at, expires_at
- Indexes: location-based, type-based, price-range, area-range, JSONB for nearby facilities
- Triggers: Auto-update updated_at, auto-calculate pyeong from area_exclusive

**government_policies**: Korean housing support policies (migration: `003_policies_schema.sql`)

- Core fields: id (uuid), policy_name, policy_code (unique), policy_type, category
- Description: description, summary, benefits, support_details (jsonb)
- Target audience: target_demographic, target_description
- Eligibility: age_min/max, income_min/max/percentile, asset_max, vehicle_value_max
- Regional: available_regions (text[]), region_restriction_type (whitelist/blacklist)
- Housing criteria: property_types, transaction_types, property_price_max, property_area_max
- Special requirements: requires_first_time_buyer, requires_newlywed, requires_children, requires_no_house
- Flexible criteria: additional_requirements (jsonb), restrictions (jsonb)
- Application: application_period_start/end, is_ongoing, application_method, application_url
- Organization: administering_organization, department, contact_info (jsonb)
- Support scale: support_amount_min/max, support_duration_months, interest_rate
- Metadata: is_active, priority (for sorting), view_count, tags (text[])
- Indexes: type, demographic, age range, income range, active status, JSONB fields
- Triggers: Auto-update updated_at
- View: active_policies (active + not expired)

**lightrag_entities**: LightRAG knowledge graph entities

- id (uuid), entity_type, entity_name, content (text), metadata (jsonb)
- created_at, updated_at

**lightrag_relationships**: LightRAG knowledge graph relationships

- id (uuid), source_entity_id, target_entity_id, relationship_type
- strength (float), metadata (jsonb), created_at

**user_profiles**: User profiles

- id (uuid), user_id (text unique), profile (jsonb), preferences (jsonb)
- search_history (jsonb), saved_properties (jsonb[])
- created_at, updated_at

**conversation_history**: Chat message history

- id (uuid), user_id (text), session_id, messages (jsonb[])
- created_at, updated_at

## Testing Patterns

### Test Structure

```
backend/tests/
├── unit/           # Isolated service tests
├── integration/    # Multi-service tests
└── api/           # Endpoint tests
```

### Common Test Patterns

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_chat_endpoint(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/chat/send",
        json={
            "message": "강남구 아파트 추천해줘",
            "user_id": "test_user"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "properties" in data
```

### Mock External Services

```python
from unittest.mock import AsyncMock

@pytest.fixture
def mock_ai_service(mocker):
    mock = AsyncMock()
    mock.generate_response.return_value = {
        "response": "Test response",
        "confidence": 0.9
    }
    return mock
```

## Common Development Scenarios

### Adding a New API Endpoint

1. Create Pydantic models in `backend/models/`
2. Add route handler in `backend/api/routers/`
3. Update router imports in `backend/api/main.py` if new router
4. Add tests in `backend/tests/api/`
5. Update API documentation in docstrings

### Adding a New Service

1. Create service file in `backend/services/`
2. Implement `__init__` and `async def initialize()` methods
3. Register in `api/main.py` lifespan function
4. Store in `app.state` for dependency injection
5. Add comprehensive error handling with custom exceptions

### Modifying Database Schema

1. Create SQL migration file in `backend/migrations/`
2. Apply migration via Supabase dashboard or CLI
3. Update DataService methods if needed (`backend/services/data_service.py`)
4. Update Pydantic models in `backend/models/` for request/response validation
5. Test with integration tests

### Working with LightRAG

1. **Index new data**: Call `lightrag_service.insert_data(text)` to add knowledge
2. **Query knowledge graph**: Use `lightrag_service.query(query, mode)` with modes:
   - `naive`: Simple keyword matching
   - `local`: Entity-focused search
   - `global`: Comprehensive graph traversal
   - `hybrid`: Balanced approach (recommended)
3. **Update entities**: LightRAG auto-updates graph from new property/policy data
4. **Monitor graph**: Check `./data/lightrag/` directory for knowledge graph files

### Using DataService

DataService unifies property and policy operations with direct Supabase integration:

```python
from services.data_service import DataService

data_service = DataService()

# Property operations
property_data = {
    "address": "서울특별시 강남구 역삼동 123",
    "district": "강남구",
    "dong": "역삼동",
    "property_type": "아파트",
    "transaction_type": "전세",
    "price": 500000000,
    "area_exclusive": 84.32,
    "room_count": 3,
}
property = await data_service.create_property(property_data)

# Search with filters
filters = {
    "district": "강남구",
    "property_type": "아파트",
    "price_min": 300000000,
    "price_max": 700000000,
    "room_count": 3,
}
properties = await data_service.search_properties(filters, limit=20)

# Policy operations
policy_data = {
    "policy_name": "청년전세임대주택",
    "policy_type": "임대지원",
    "target_demographic": "청년",
    "summary": "청년층 주거 안정을 위한 전세임대 지원",
    "age_min": 19,
    "age_max": 39,
    "income_max": 20000000,
}
policy = await data_service.create_policy(policy_data)

# Match policies to user profile
user_profile = {
    "age": 28,
    "income": 18000000,
    "region": "서울특별시",
    "is_first_time_buyer": True,
}
eligible_policies = await data_service.match_policies_for_user(user_profile)

# Get statistics
stats = await data_service.get_property_statistics({"district": "강남구"})
# Returns: {"total_count": 150, "average_price": 550000000, "average_area": 85.5}
```

### Adding AI Provider

1. Extend `AIProvider` enum in `services/ai_service.py`
2. Add provider configuration to `provider_config`
3. Implement `_generate_with_[provider]` method
4. Add to failover chain in `_generate_with_fallback`
5. Update circuit breaker logic

## Performance Considerations

### Query Optimization

- **LightRAG First**: Use knowledge graph queries for most requests (faster, context-aware)
- **Vector Fallback**: Use ChromaDB only when LightRAG cannot answer
- **Batch Operations**: Batch embeddings for multiple queries
- **Supabase Indexing**: Use database indexes for fast property/policy lookups
- **Redis Caching**: Cache frequently accessed data for sub-second lookups
- **Filtering**: Apply filters at database level before vector search

### Memory Management

- **LightRAG Graph**: Knowledge graph stored on disk, minimal memory footprint
- **Vector Results**: Limit ChromaDB search results to top 10-20
- **Streaming**: Stream large AI responses to reduce memory usage
- **Connection Pooling**: Supabase built-in pooling handles connections efficiently
- **Cache Cleanup**: Clear Redis cache periodically to prevent memory bloat
- **Graph Pruning**: Periodically remove stale entities from LightRAG knowledge graph

### AI Provider Selection

- Simple queries (intent classification, keyword extraction) → Cloudflare (faster, cheaper)
- Complex reasoning (property recommendations, policy matching) → Bedrock (higher quality)
- Always provide fallback path in case primary provider fails

## Security Notes

- Never commit `.env` files or credentials
- Use Supabase RLS (Row Level Security) for multi-tenant isolation
- JWT tokens stored securely with configurable expiration
- Input validation on all user inputs via Pydantic models
- Rate limiting via middleware (configured in production)

## Deployment

### Docker Multi-Stage Build

The Dockerfile uses uv for fast, reproducible builds:

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.11-bookworm
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .
CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Health Checks

Endpoint: `GET /api/v1/health`

Returns status of:

- Supabase connection
- Redis cache
- ChromaDB vector store
- LightRAG service
- AI service providers (Bedrock, Cloudflare)

Use for Kubernetes liveness/readiness probes.

## Monitoring & Observability

### Structured Logging

```python
logger.info(
    "RAG query processed",
    extra={
        "user_id": user_id,
        "processing_time_ms": elapsed,
        "cache_hit": cache_hit,
        "properties_found": len(properties)
    }
)
```

### Metrics Tracked

- Request latency (p50, p95, p99)
- Cache hit rates (per layer: L1-L4)
- AI provider success/failure rates
- Circuit breaker trips
- LightRAG query performance (graph traversal time)
- Knowledge graph size (entities, relationships)
- Vector search performance (ChromaDB fallback cases)
- Database query performance (Supabase operation times)

## Korean Real Estate Domain

### Key Terminology

- **부동산 (boodongsan)**: Real estate
- **아파트 (apartment)**: Apartment complex (most common)
- **전세 (jeonse)**: Key money deposit lease (unique to Korea)
- **월세 (wolse)**: Monthly rent
- **실거래가 (silgeoraega)**: Actual transaction price
- **국토교통부 (MOLIT)**: Ministry of Land, Infrastructure and Transport

### Government Policies Supported

- 청년전세임대주택 (Youth Jeonse Rental Housing)
- 신혼부부 특별공급 (Newlywed Special Supply)
- 생애최초 특별공급 (First-time Buyer Special Supply)
- HUG 전세보증보험 (Jeonse Guarantee Insurance)
- 버팀목 전세자금 (Stepping Stone Jeonse Loan)

### Data Sources

- 국토교통부 실거래가 API: Real transaction data
- HUG/HF APIs: Housing finance and guarantee info
- 공공데이터포털: Public data portal

## Troubleshooting

### Service Won't Start

```bash
# Check logs for specific error
docker-compose logs backend | grep ERROR

# Verify environment variables
python -c "from core.config import settings; print('✅ Config loaded')"

# Check port conflicts
lsof -i :8000
```

### AI Service Failures

- Check AWS credentials: `aws sts get-caller-identity`
- Verify Bedrock model access in AWS console
- Check circuit breaker status in logs
- Fallback to Cloudflare should be automatic

### LightRAG Issues

- Check LightRAG is enabled: `USE_LIGHTRAG=true` in `.env`
- Verify knowledge graph directory exists: `ls -la ./data/lightrag/`
- Check entity extraction: Review logs for entity/relationship creation
- Rebuild knowledge graph: Delete `./data/lightrag/` and re-index data
- Monitor graph size: Large graphs (>10K entities) may need optimization

### Vector Search Issues

- Verify ChromaDB is running: `curl http://localhost:8001/api/v1/heartbeat`
- Check collection exists and has embeddings
- Verify embedding dimensions match (Titan: 1536 dimensions)
- LightRAG should handle most queries; ChromaDB is fallback only

### Database Connection Issues

- Check Supabase URL and keys in `.env`
- Test connection: `curl -H "apikey: $SUPABASE_ANON_KEY" "$SUPABASE_URL/rest/v1/"`
- Review connection pool settings in logs
- Check for connection leaks (should auto-cleanup)

## Migration & Implementation

### Post-Refactoring State

This codebase has been prepared for a major refactoring to Supabase + LightRAG architecture. **The refactoring has NOT been executed yet**. Current state:

**Preparation Files Created**:
- ✅ `REFACTORING_PLAN.md` - Complete strategic plan with decision rationale
- ✅ `IMPLEMENTATION_GUIDE.md` - Step-by-step execution guide (8 phases, 4-6 hours)
- ✅ `migrations/002_properties_schema.sql` - Properties table migration
- ✅ `migrations/003_policies_schema.sql` - Government policies table migration
- ✅ `services/data_service.py` - Unified data service (570 lines)

**Next Steps** (when ready to execute):
1. Review `REFACTORING_PLAN.md` for architectural decisions and trade-offs
2. Follow `IMPLEMENTATION_GUIDE.md` phase by phase with verification checkpoints
3. Apply Supabase migrations via dashboard or CLI
4. Update service initialization in `api/main.py`
5. Remove deprecated services and database layer
6. Test thoroughly before deploying

**⚠️ Warning**: Do not execute refactoring during active development. Choose a maintenance window.

## Development Workflow

1. **Create feature branch**: `git checkout -b feature/your-feature`
2. **Write code with tests**: Follow TDD when possible
3. **Run quality checks**: `uv run ruff check . && uv run ruff format .`
4. **Run tests**: `uv run pytest --cov`
5. **Test locally**: `docker-compose up` and manual testing
6. **Comment in Korean**: All comments should be in Korean as well as any documentations you create
7. **Don't Push or COMMIT**: Don't push or commit or conduct any git operations unless specifically specified
