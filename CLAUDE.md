# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Estate Sentry is an open-source home threat intelligence system that integrates with various security sensors to provide real-time monitoring and threat analysis. The project aims to make home security accessible, transparent, and affordable.

### Sensor Types Supported
- Camera systems (with planned single-shot recognition)
- Door and window contacts
- Glass break sensors
- Motion detectors
- Environmental sensors (smoke, CO, water leak)
- Extensible framework for custom sensors

### System Components

1. **estate-sentry-api** - Django REST Framework API backend
2. **estate-sentry-hq** - Next.js/React TypeScript frontend dashboard

### Development Philosophy
- Focus on building robust sensor integration frameworks
- Skeleton/framework first, advanced ML features (like single-shot recognition) later
- Clean, maintainable architecture for long-term development

## Documentation

For comprehensive documentation, use mkdocs:

```bash
# Serve documentation locally
mkdocs serve
```

Access at http://localhost:8001 for complete guides on:
- Installation and setup
- Quick start tutorials
- Task reference
- API usage
- Architecture overview
- Database documentation
- Docker setup
- Development guidelines

## Development Commands

### Using Task (Recommended)

Estate Sentry uses [Task](https://taskfile.dev/) for development automation. All tasks are defined in `Taskfile.yaml`.

**Common tasks:**
```bash
task                    # List all available tasks
task setup             # Complete project setup
task dev               # Start both API and HQ servers
task api:dev           # Start API server
task hq:dev            # Start HQ server
task api:test          # Run API tests
task api:migrate       # Run database migrations
task clean             # Clean build artifacts
task check             # Run linting and checks
```

**All available task categories:**
- `setup:*` - Initial setup and installation
- `api:*` - Django API tasks
- `hq:*` - Next.js HQ tasks
- `test:*` - Testing tasks
- `docker:*` - Docker tasks (build, run, logs, shell access)
- `db:*` - Database management (PostgreSQL, Neo4j, backups)

Run `task --list` to see all available tasks. For detailed task documentation, see `docs/guides/task-reference.md`.

### Docker Development

Estate Sentry provides full Docker support with PostgreSQL and Neo4j databases.

**Quick start with Docker:**
```bash
# Build and start all services
task docker:build
task docker:up

# Run migrations
task db:migrate:docker

# View logs
task docker:logs

# Access shells
task docker:shell:api
task docker:shell:neo4j
```

**Docker task categories:**
- `docker:build:*` - Build Docker images
- `docker:up` / `docker:down` - Start/stop services
- `docker:logs:*` - View service logs
- `docker:shell:*` - Access container shells
- `db:postgres:*` - PostgreSQL backup/restore
- `db:neo4j:*` - Neo4j export/import/sync

See `docs/getting-started/docker-setup.md` for complete Docker documentation.

### Manual Commands (Django API)

If not using Task, you can run commands directly:

**Run the development server:**
```bash
cd estate-sentry-api
python manage.py runserver
```
The API runs on port 8000 by default.

**Database operations:**
```bash
# Create migrations after model changes
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser for admin access
python manage.py createsuperuser

# Open Django shell
python manage.py shell
```

**Run tests:**
```bash
# Run all tests
python manage.py test

# Run tests for specific app
python manage.py test authentication
python manage.py test sensors

# Run with verbose output
python manage.py test --verbosity=2

# Run specific test case
python manage.py test authentication.tests.AuthenticationTestCase
```

**Lint Python code:**
```bash
# Check for syntax errors and undefined names
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

# Full linting with warnings
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
```

**Install dependencies:**
```bash
cd estate-sentry-api
pip install -r requirements.txt
```

**Virtual environment:**
The Python virtual environment is located at `estate-sentry-api/.venv/`

### Next.js HQ Client (estate-sentry-hq)

**Run development server:**
```bash
cd estate-sentry-hq
npm run dev
```
The client runs on port 10842 by default.

**Build for production:**
```bash
cd estate-sentry-hq
npm run build
```

**Run production server:**
```bash
cd estate-sentry-hq
npm run start
```

**Lint:**
```bash
cd estate-sentry-hq
npm run lint
```

**Install dependencies:**
```bash
cd estate-sentry-hq
npm install
```

## Architecture

### Django API Structure

The API follows Django's app-based architecture with Django REST Framework:

**Project Structure:**
```
estate-sentry-api/
├── estate_sentry/          # Main Django project
│   ├── settings.py         # Django settings
│   ├── urls.py            # Root URL configuration
│   └── wsgi.py            # WSGI application
├── authentication/         # Authentication app
│   ├── models.py          # User model
│   ├── serializers.py     # DRF serializers
│   ├── views.py           # API views
│   └── tests.py           # Authentication tests
├── sensors/               # Sensor management app
│   ├── models.py          # Sensor, SensorReading models
│   ├── serializers.py     # DRF serializers
│   ├── views.py           # Sensor API views
│   ├── handlers/          # Sensor-specific handlers
│   └── tests.py           # Sensor tests
├── alerts/                # Alert/threat detection app
│   ├── models.py          # Alert models
│   ├── services.py        # Threat analysis logic
│   └── tests.py           # Alert tests
└── manage.py              # Django management script
```

**Key Django Apps:**
- **authentication** - User management, token-based auth, multiple auth methods
- **sensors** - Sensor registration, data ingestion, sensor type handlers
- **alerts** - Threat detection, alert generation, notification system

### Database Architecture

Estate Sentry uses a dual-database architecture:

**PostgreSQL (Primary Database)**:
- Stores relational data: users, sensors, readings, alerts
- Production-ready with Docker, or SQLite for local development
- Configured via `DATABASE_ENGINE` environment variable

**Neo4j (Graph Database)**:
- Stores relationship data and threat intelligence graphs
- Sensor networks, threat patterns, and behavioral analysis
- Accessible at http://localhost:7474 (browser) and bolt://localhost:7687 (API)
- Data synchronized to `./data/neo4j/` for persistence

### Database Models

**User Model** (Django's AbstractUser):
- Extends Django's built-in User model
- Fields: `auth_method` (username/pin/password), `pin`, additional profile fields
- Uses Django's authentication system with custom backends

**Sensor Model:**
- Fields: `name`, `sensor_type`, `location`, `status`, `handler_class`, `connection_config` (JSONField), `metadata` (JSONField)
- Sensor types: `CAMERA`, `DOOR_CONTACT`, `WINDOW_CONTACT`, `GLASS_BREAK`, `MOTION`, `SMOKE`, `CO`, `WATER_LEAK`, `CUSTOM`

**SensorReading Model:**
- Fields: `sensor` (FK), `timestamp`, `value` (JSONField), `reading_type`, `processed`
- Stores time-series data from sensors in PostgreSQL

**Alert Model:**
- Fields: `alert_type`, `severity`, `sensor` (FK), `timestamp`, `description`, `acknowledged`, `metadata` (JSONField)
- Severity levels: `INFO`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`

### Database Configuration

The Django settings support both development (SQLite) and production (PostgreSQL) databases:

```python
# Local development (default)
DATABASE_ENGINE=sqlite

# Docker/Production
DATABASE_ENGINE=postgresql
POSTGRES_DB=estate_sentry
POSTGRES_USER=estate_sentry
POSTGRES_PASSWORD=your-password
POSTGRES_HOST=postgres  # or localhost
POSTGRES_PORT=5432
```

Neo4j configuration:
```python
NEO4J_URI=bolt://localhost:7687  # or bolt://neo4j:7687 in Docker
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
```

### Authentication System

Django REST Framework token-based authentication with custom backends supporting:
- Standard username/password authentication
- PIN-based authentication (4-digit)
- Username-only authentication (for trusted devices)

Auth method is stored per-user in the User model's `auth_method` field.

### Next.js Frontend Structure

- **`pages/_app.tsx`** - App wrapper with `ClientProviders` for contexts
- **`pages/index.tsx`** - Main dashboard page
- **`pages/api/`** - Next.js API routes (proxy to Python backend)
- **`components/`** - React components:
  - `Layout.tsx` - Main layout wrapper
  - `Header.tsx` - Top navigation bar
  - `Sidebar.tsx` - Side navigation
  - `SensorGrid.tsx` - Display grid for sensors
  - `AlertDisplay.tsx` - Security alerts display
  - `ClientProviders.tsx` - Client-side context providers wrapper
- **`contexts/`** - React contexts:
  - `AuthContext.tsx` - Authentication state management
  - `AlertContext.tsx` - Alert notifications using reducer pattern
- **`lib/`** - Utility libraries:
  - `sensorRelay.ts` - EventEmitter-based sensor data relay (WIP)
  - `streamHandler.ts` - Stream handling utilities

The frontend uses SWR for data fetching, next-themes for dark mode, and React Icons for UI elements.

### Database Models

**User Model** (`db/models/user.py`):
- Fields: `id`, `name`, `username` (unique), `auth_method`, `pin`, `password`, `token`, `additional_data_json`
- Methods: `generate_token()` - Creates secure random token

**Sensor Model** (`db/models/sensor.py`):
- Fields: `id`, `name`, `handler`, `public_key`, `connection_type`, `connection_details` (JSON), `metadata` (JSON)

### API Endpoints

**Authentication (`/api/auth/`):**
- `POST /api/auth/register/` - Create new user account
- `POST /api/auth/login/` - Login and receive auth token
- `POST /api/auth/logout/` - Invalidate auth token
- `GET /api/auth/user/` - Get current user info
- `PATCH /api/auth/user/` - Update user profile

**Sensors (`/api/sensors/`):**
- `GET /api/sensors/` - List all sensors
- `POST /api/sensors/` - Register new sensor
- `GET /api/sensors/{id}/` - Get sensor details
- `PATCH /api/sensors/{id}/` - Update sensor configuration
- `DELETE /api/sensors/{id}/` - Remove sensor
- `POST /api/sensors/{id}/readings/` - Submit sensor reading
- `GET /api/sensors/{id}/readings/` - Get sensor reading history
- `GET /api/sensors/{id}/stream/` - WebSocket for real-time data

**Alerts (`/api/alerts/`):**
- `GET /api/alerts/` - List alerts (filterable by severity, acknowledged status)
- `GET /api/alerts/{id}/` - Get alert details
- `PATCH /api/alerts/{id}/acknowledge/` - Mark alert as acknowledged
- `GET /api/alerts/statistics/` - Get alert statistics and trends

### Sensor Handler Framework

Each sensor type has a corresponding handler class in `sensors/handlers/`:

```python
# Base handler interface
class BaseSensorHandler:
    def validate_reading(self, data): pass
    def process_reading(self, sensor, data): pass
    def detect_threats(self, reading): pass
```

**Handler Types:**
- `CameraHandler` - Process image/video data, placeholder for future ML integration
- `ContactHandler` - Door/window contact sensors
- `GlassBreakHandler` - Glass break detection
- `MotionHandler` - Motion detection sensors
- `EnvironmentalHandler` - Smoke, CO, water leak sensors

Handlers are extensible - new sensor types can be added by creating new handler classes.

### Test Configuration

**Django Tests:**
- Framework: Django's built-in test framework (based on unittest)
- Each app has its own `tests.py` or `tests/` directory
- Uses in-memory SQLite database for tests
- Run with: `python manage.py test`

**Frontend Tests:**
- No test framework currently configured

### CI/CD

GitHub Actions workflow (`.github/workflows/api-tests.yml`):
- Runs on: push/PR to master branch
- Python 3.10
- Lints with flake8
- Runs Django tests

## Development Notes

- Uses Django's ORM for all database operations
- API authentication via DRF's TokenAuthentication
- Real-time sensor data will use Django Channels (WebSockets) in future
- The frontend uses dynamic imports with `ssr: false` for client-side only components
- Sensor readings are stored as time-series data for future analysis
- Alert detection runs asynchronously via sensor handlers
