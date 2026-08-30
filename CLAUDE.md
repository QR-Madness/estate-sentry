# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Estate Sentry is a prototype open-source threat intelligence platform for personal and public safety. It combines real-time sensor monitoring, zone-based perception, and AI-powered threat analysis.

**Components:**

- **estate-sentry-api/** — Django 5 + DRF backend (Python, managed with uv)
- **HQ dashboard** — being rebuilt as Django templates + htmx served by the API itself; no build step, no separate service. The previous Next.js app was removed (recoverable from git history).
- **Switchboard** — NATS JetStream + MinIO data routing (infrastructure deployed, integration planned)
- **Sentry Intelligence** — MCP server for Claude-powered threat analysis (planned)
- **estate-sentry-perception** — Async perception pipeline for camera feeds (planned, see `docs/Specification.md`)

The `docs/Specification.md` is the authoritative design document for the intelligence layer: perception pipeline, zone model, identity management, and threat assessment.

## Development Commands

Uses [Task](https://taskfile.dev/) with **uv** (Python):

```bash
task                    # List all tasks
task setup             # Full setup (dirs, deps, migrations)
task dev               # Start the API (8000)

# API
task api:dev           # Django dev server
task api:test          # Run tests
task api:test:verbose  # Verbose output
task api:test:coverage # With coverage report
task api:lint          # Lint with ruff
task api:lint:fix      # Auto-fix lint errors
task api:format        # Format with ruff
task api:migrate       # Apply migrations
task api:makemigrations # Create migrations
task api:shell         # Django shell
task api:superuser     # Create admin user
task api:add -- pkg    # Add Python package

# Docker
task docker:up         # Start all services
task docker:down       # Stop services
task docker:logs       # Follow all logs
task db:migrate:docker # Run migrations in container

# Docs
task docs:serve        # Serve mkdocs at localhost:8001
task docs:build        # Build static site
```

### Running tests manually (from estate-sentry-api/)

```bash
uv run python manage.py test                                          # All tests
uv run python manage.py test sensors                                  # Single app
uv run python manage.py test sensors.tests.SensorTestCase             # Single class
uv run python manage.py test sensors.tests.SensorTestCase.test_create # Single method
```

Tests use in-memory SQLite. Each Django app has `tests.py`.

### Manual commands without Task

```bash
# API (from estate-sentry-api/)
uv sync                            # Install deps
uv run python manage.py runserver  # Dev server
uv run ruff check .                # Lint
uv run ruff format .               # Format
```

## Architecture

### Sensor Data Flow

This is the core runtime path through the existing codebase:

1. Client POSTs to `/api/sensors/{id}/readings/` with `{value: {...}, reading_type: "..."}`
2. `SensorReadingCreateSerializer` looks up the sensor's type and instantiates the matching handler
3. Handler's `validate_reading(data)` checks data shape, returns `(bool, error_msg)`
4. Handler's `process_reading(data)` normalizes the raw data into a canonical dict
5. `SensorReading` is created in PostgreSQL with the processed value
6. `SensorViewSet._process_reading_for_threats()` calls handler's `detect_threats(reading)`
7. Any returned threat dicts are saved as `Alert` objects with severity, type, and metadata
8. Reading is marked `processed=True`

### Handler Framework

Handlers in `estate-sentry-api/sensors/handlers/` process sensor-specific data:

```python
class BaseSensorHandler(ABC):
    def __init__(self, sensor): ...
    def validate_reading(self, data) -> tuple[bool, str | None]: ...  # Required
    def process_reading(self, data) -> dict: ...                       # Required
    def detect_threats(self, reading) -> list[dict]: ...               # Optional
```

Handler-to-type mapping is in `SensorReadingCreateSerializer.validate()` and `SensorViewSet._process_reading_for_threats()`. Both contain a dict mapping sensor type strings to handler classes.

**Implemented handlers:**

- `ContactHandler` — DOOR_CONTACT, WINDOW_CONTACT (validates open/closed state, generates MEDIUM intrusion alerts on open)
- `CameraHandler` — CAMERA (validates image_url/motion_detected, generates LOW motion alerts; ML analysis is a TODO)

**Sensor types:** CAMERA, DOOR_CONTACT, WINDOW_CONTACT, GLASS_BREAK, MOTION, SMOKE, CO, WATER_LEAK, TEMPERATURE, CUSTOM

### Django Apps

- **authentication** — Custom `User` model (extends AbstractUser) with three auth methods: username-only, PIN, password. Token-based auth via DRF `authtoken`.
- **sensors** — `Sensor` and `SensorReading` models. `SensorViewSet` with custom `readings` (POST) and `reading_history` (GET) actions. Handler framework dispatches to type-specific processors.
- **alerts** — `Alert` model with severity levels (INFO→CRITICAL) and acknowledgment flow. Read-only viewset with `acknowledge` (PATCH) and `statistics` (GET) actions.

### Key Models and Relationships

```
User (AbstractUser + auth_method, pin, phone_number)
├── Sensor (name, sensor_type, location, status, handler_class, connection_config JSON, metadata JSON)
│   ├── SensorReading (timestamp, value JSON, reading_type, processed)
│   └── Alert (alert_type, severity, title, description, acknowledged, metadata JSON)
└── Alert (user FK, acknowledged_by FK)
```

All models use `JSONField` for flexible data: `Sensor.connection_config`, `Sensor.metadata`, `SensorReading.value`, `Alert.metadata`.

### Frontend

The Next.js dashboard was removed: it had never built (a leftover `@prisma/client`
import, Tailwind configured but never installed, and a `SensorRelay.start()` that was
an empty TODO, so its SSE stream could never emit). It is recoverable from git history.

The replacement is a Django app serving templates + htmx from the API itself — no build
step and no second service. Live video is an `<img>` pointing at an MJPEG endpoint;
the alert feed is htmx `sse-connect` / `sse-swap`.

### Database Configuration

```bash
DATABASE_ENGINE=sqlite      # Local dev default
DATABASE_ENGINE=postgresql  # Docker/production
```

| Database | Port | Purpose |
|----------|------|---------|
| PostgreSQL (TimescaleDB 16) | 5432 | Relational data, sensor readings, alerts |
| Neo4j 5 | 7474/7687 | Graph relationships, threat patterns (configured, not yet integrated) |
| NATS 2.10 | 4222/8222 | Message bus with JetStream (configured, not yet integrated) |
| MinIO | 9000/9001 | Object storage for frames/media (configured, not yet integrated) |
| ChromaDB | 8001 | Vector embeddings (configured, not yet integrated) |

### API Routes

```
POST        /api/auth/register/
POST        /api/auth/login/
POST        /api/auth/logout/
GET/PUT     /api/auth/user/

GET/POST    /api/sensors/
GET/PUT/PATCH/DELETE  /api/sensors/{id}/
POST        /api/sensors/{id}/readings/
GET         /api/sensors/{id}/reading_history/
GET         /api/readings/
GET         /api/readings/{id}/

GET         /api/alerts/
GET         /api/alerts/{id}/
PATCH       /api/alerts/{id}/acknowledge/
GET         /api/alerts/statistics/
```

## Docker Services

```bash
task docker:up       # Start all services
task docker:down     # Stop services
task docker:logs     # Follow logs
task docker:shell:postgres  # psql shell
task docker:shell:neo4j     # Cypher shell
```

All persistent data writes to `./data/` subdirectories.

## Documentation

Published to GitHub Pages on push to master (`.github/workflows/docs.yml`). Serve locally:

```bash
task docs:serve   # http://localhost:8001
```

Key docs:

- `docs/Specification.md` — Intelligence layer design (perception pipeline, zones, identity, threat scoring)
- `docs/Todo.md` — Implementation roadmap
- `docs/architecture/overview.md` — System architecture
- `docs/guides/plugin-development.md` — Creating sensor handlers

## CI/CD

**`.github/workflows/api-tests.yml`** — Runs on push/PR to master. Uses `uv sync`, then `ruff check`, `manage.py check` and `manage.py test` against `estate-sentry-api/` — the same tooling as local dev.

**`.github/workflows/docs.yml`** — Deploys mkdocs to GitHub Pages on push to master.
