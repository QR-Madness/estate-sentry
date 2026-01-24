# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Estate Sentry is an open-source home threat intelligence system with real-time monitoring, AI-powered threat analysis, and support for decentralized multi-node deployments.

**Core Components:**
- **estate-sentry-api** - Django REST Framework backend (Python with uv)
- **estate-sentry-hq** - Next.js dashboard (TypeScript with bun)
- **Switchboard** - NATS + MinIO data routing backbone (planned)
- **Sentry Intelligence** - MCP server for AI threat analysis (planned)

## Development Commands

### Task Runner (Primary Method)

Uses [Task](https://taskfile.dev/) with **uv** for Python and **bun** for TypeScript:

```bash
task                    # List all tasks
task setup             # Complete setup (installs deps, runs migrations)
task dev               # Start API (8000) + HQ (3000) servers

# API (uv)
task api:dev           # Django dev server
task api:test          # Run tests
task api:test:verbose  # Tests with verbose output
task api:lint          # Lint with ruff
task api:format        # Format with ruff
task api:migrate       # Apply migrations
task api:makemigrations # Create migrations
task api:shell         # Django shell

# HQ (bun)
task hq:dev            # Next.js dev server
task hq:build          # Production build
task hq:lint           # ESLint

# Docker
task docker:up         # Start all services
task docker:down       # Stop services
task docker:logs       # Follow all logs
task db:migrate:docker # Run migrations in container
```

### Manual Commands

**API (estate-sentry-api/):**
```bash
uv sync                           # Install dependencies
uv run python manage.py runserver # Dev server
uv run python manage.py test      # All tests
uv run python manage.py test sensors.tests.SensorTestCase  # Single test
uv run ruff check .               # Lint
uv run ruff format .              # Format
```

**HQ (estate-sentry-hq/):**
```bash
bun install          # Install dependencies
bun run dev          # Dev server (port 3000)
bun run build        # Production build
bun run lint         # Lint
bun test             # Run tests
```

## Architecture

### System Overview

```
+------------------------------------------------------------------+
|                         ESTATE SENTRY                             |
|  +------------------+    +------------------+    +--------------+ |
|  |   Zone Nodes     |    |   Switchboard    |    |   Sentry     | |
|  |   (Distributed)  |<-->|   (Data Router)  |<-->|  (AI Intel)  | |
|  +------------------+    +------------------+    +--------------+ |
+------------------------------------------------------------------+
         |                         |                      |
+--------v--------+     +----------v----------+    +------v-------+
|  HQ Dashboard   |     |  Sensors/Devices    |    |  Claude/AI   |
|  (Next.js)      |     |  (MQTT/REST/etc)    |    |  (Analysis)  |
+-----------------+     +---------------------+    +--------------+
```

### Database Architecture

| Database | Purpose |
|----------|---------|
| PostgreSQL + TimescaleDB | Relational data, time-series sensor readings |
| Neo4j | Graph relationships, threat intelligence patterns |
| ChromaDB | Vector embeddings for AI pattern matching |
| MinIO | Object storage for camera frames/recordings |

**Configuration:**
```bash
DATABASE_ENGINE=sqlite    # Local dev (default)
DATABASE_ENGINE=postgresql # Docker/production
```

### Django Apps

- **authentication** - User management, token auth, multiple auth methods (password/PIN/username)
- **sensors** - Sensor registration, data ingestion, handler framework
- **alerts** - Threat detection, alert generation, severity levels (INFO→CRITICAL)

### Sensor Handler Framework

Handlers in `sensors/handlers/` process sensor-specific data:

```python
class BaseSensorHandler:
    SENSOR_TYPES = ['MY_SENSOR']  # Auto-registration

    def validate_reading(self, data): pass
    def process_reading(self, sensor, data): pass
    def detect_threats(self, reading): pass
```

**Types:** CAMERA, DOOR_CONTACT, WINDOW_CONTACT, GLASS_BREAK, MOTION, SMOKE, CO, WATER_LEAK, CUSTOM

### Key Models

**Sensor:** `name`, `sensor_type`, `location`, `status`, `handler_class`, `connection_config` (JSON), `metadata` (JSON)

**SensorReading:** `sensor` (FK), `timestamp`, `value` (JSON), `reading_type`, `processed`

**Alert:** `alert_type`, `severity`, `sensor` (FK), `timestamp`, `description`, `acknowledged`, `metadata` (JSON)

### API Endpoints

| Endpoint | Methods | Purpose |
|----------|---------|---------|
| `/api/auth/register/` | POST | Create account |
| `/api/auth/login/` | POST | Get auth token |
| `/api/sensors/` | GET, POST | List/create sensors |
| `/api/sensors/{id}/readings/` | GET, POST | Sensor data |
| `/api/alerts/` | GET | List alerts |
| `/api/alerts/{id}/acknowledge/` | PATCH | Acknowledge alert |

### Frontend Structure

- **pages/** - Next.js pages (dashboard at index.tsx)
- **components/** - Layout, Header, Sidebar, SensorGrid, AlertDisplay
- **contexts/** - AuthContext, AlertContext (reducer pattern)
- **lib/** - sensorRelay.ts (EventEmitter), streamHandler.ts

Uses SWR for data fetching, next-themes for dark mode.

## Docker Services

```bash
task docker:up  # Starts all services:
```

| Service | Port | Purpose |
|---------|------|---------|
| api | 8000 | Django API |
| hq | 3000 | Next.js dashboard |
| postgres | 5432 | PostgreSQL + TimescaleDB |
| neo4j | 7474/7687 | Graph database |
| nats | 4222/8222 | Message queue |
| minio | 9000/9001 | Object storage |
| chromadb | 8001 | Vector database |

## Documentation

```bash
task docs:serve  # Serve at http://localhost:8001
```

Key docs:
- `docs/architecture/overview.md` - Full system architecture
- `docs/architecture/database.md` - Database schemas
- `docs/guides/plugin-development.md` - Creating sensor handlers
- `docs/Todo.md` - Implementation roadmap

## Testing

```bash
# API tests
task api:test                                    # All tests
uv run python manage.py test sensors            # Single app
uv run python manage.py test sensors.tests.SensorTestCase.test_create  # Single test

# With coverage
task api:test:coverage
```

Tests use in-memory SQLite. Each Django app has `tests.py`.

## CI/CD

GitHub Actions (`.github/workflows/api-tests.yml`):
- Triggers on push/PR to master
- Runs ruff lint + Django tests
