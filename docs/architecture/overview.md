# Architecture Overview

Estate Sentry is built with a modern, extensible architecture designed for scalability and flexibility.

## System Components

### 1. Django REST API Backend (`estate-sentry-api`)

The backend is built with Django and Django REST Framework, following a modular app-based architecture.

**Key Features:**
- Token-based authentication
- RESTful API design
- Extensible sensor handler framework
- Real-time threat detection
- Time-series data storage

**Django Apps:**

- **authentication** - User management with multiple auth methods
- **sensors** - Sensor registration, data ingestion, handler framework
- **alerts** - Threat detection, alert generation, notification system

### 2. Next.js Frontend (`estate-sentry-hq`)

The frontend is a modern React application built with Next.js.

**Key Features:**
- Real-time dashboard
- Sensor monitoring
- Alert management
- Dark mode support
- Responsive design

**Technologies:**
- Next.js 14
- React 18
- TypeScript
- Tailwind CSS
- SWR for data fetching

## Database Architecture

Estate Sentry uses a dual-database approach:

### PostgreSQL (Primary Database)

Stores relational data:
- User accounts
- Sensor configurations
- Sensor readings (time-series)
- Security alerts

**Deployment Options:**
- SQLite for local development
- PostgreSQL for Docker/production

### Neo4j (Graph Database)

Stores relationship data:
- Sensor networks
- Threat patterns
- Behavioral analysis
- Relationship intelligence

**Features:**
- APOC plugins
- Graph Data Science
- Real-time synchronization to `./data/neo4j/`

## Sensor Handler Framework

Each sensor type has a dedicated handler that implements three core methods:

```python
class BaseSensorHandler:
    def validate_reading(self, data):
        """Validate incoming sensor data"""
        pass

    def process_reading(self, sensor, data):
        """Process data into standard format"""
        pass

    def detect_threats(self, reading):
        """Analyze for threats and generate alerts"""
        pass
```

**Built-in Handlers:**
- `CameraHandler` - Camera systems (placeholder for ML)
- `ContactHandler` - Door/window sensors
- `GlassBreakHandler` - Glass break detection
- `MotionHandler` - Motion detection
- `EnvironmentalHandler` - Smoke, CO, water leak

**Extensibility:**
New sensor types can be added by creating new handler classes.

## Authentication System

Multi-method authentication supporting:
- **Password** - Standard username/password
- **PIN** - 4-digit PIN authentication
- **Username** - Username-only for trusted devices

Token-based API authentication using Django REST Framework's TokenAuthentication.

## Data Flow

### Sensor Reading Ingestion

1. Sensor submits reading via API
2. Handler validates the data
3. Reading is stored in PostgreSQL
4. Handler processes and analyzes data
5. Threats are detected
6. Alerts are generated if needed
7. Frontend receives real-time updates

### Alert Generation

1. Sensor reading triggers threat detection
2. Handler analyzes data against rules
3. Alert is created with severity level
4. User is notified (email/push planned)
5. Alert appears in dashboard
6. User can acknowledge/dismiss

## API Design

RESTful API following best practices:
- Resource-based URLs
- HTTP methods (GET, POST, PATCH, DELETE)
- JSON request/response format
- Token authentication
- Proper status codes
- Error handling

## Project Structure

```
estate-sentry-source/
├── estate-sentry-api/          # Django API Backend
│   ├── .venv/                  # Python virtual environment
│   ├── estate_sentry/          # Main Django project
│   │   ├── settings.py         # Configuration
│   │   └── urls.py             # URL routing
│   ├── authentication/         # Auth app
│   │   ├── models.py           # User model
│   │   ├── serializers.py      # API serializers
│   │   ├── views.py            # API endpoints
│   │   └── tests.py            # Tests
│   ├── sensors/                # Sensors app
│   │   ├── models.py           # Sensor, SensorReading
│   │   ├── handlers/           # Handler framework
│   │   │   ├── base.py
│   │   │   ├── camera.py
│   │   │   ├── contact.py
│   │   │   └── ...
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── tests.py
│   ├── alerts/                 # Alerts app
│   │   ├── models.py           # Alert model
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── tests.py
│   ├── manage.py               # Django CLI
│   └── requirements.txt        # Python dependencies
│
├── estate-sentry-hq/           # Next.js Frontend
│   ├── pages/                  # Next.js pages
│   │   ├── _app.tsx            # App wrapper
│   │   ├── index.tsx           # Dashboard
│   │   └── api/                # API routes
│   ├── components/             # React components
│   │   ├── Layout.tsx
│   │   ├── Header.tsx
│   │   ├── Sidebar.tsx
│   │   └── ...
│   ├── contexts/               # React contexts
│   │   ├── AuthContext.tsx
│   │   └── AlertContext.tsx
│   └── lib/                    # Utilities
│
├── data/                       # Data persistence
│   ├── neo4j/                  # Neo4j volumes
│   └── backups/                # Database backups
│
├── docs/                       # Documentation
├── Taskfile.yaml               # Task automation
├── docker-compose.yml          # Docker orchestration
└── .env.example                # Environment template
```

## Security Considerations

- Token-based authentication
- CORS configuration
- Environment variable secrets
- SQL injection prevention (Django ORM)
- XSS prevention (React)
- Input validation (handlers)
- HTTPS in production (planned)

## Scalability

The architecture supports future scaling:

- **Horizontal scaling** - Multiple API instances
- **Database replication** - PostgreSQL/Neo4j clusters
- **Caching layer** - Redis (planned)
- **Message queue** - Celery for async tasks (planned)
- **WebSockets** - Django Channels (planned)

## Future Enhancements

- **Single-shot recognition** - ML integration for cameras
- **Real-time streaming** - WebSockets via Django Channels
- **Advanced analytics** - Neo4j graph analysis
- **Notification system** - Email, SMS, push notifications
- **Mobile apps** - iOS and Android applications
- **Cloud deployment** - Kubernetes, AWS/GCP/Azure

## Development Philosophy

1. **Framework first** - Build robust structure before features
2. **Extensibility** - Easy to add new sensor types
3. **Testing** - Comprehensive test coverage
4. **Documentation** - Clear, accessible documentation
5. **Simplicity** - Clean, maintainable code
6. **Open source** - Transparent, community-driven

## Resources

- [Database Documentation](database.md)
- [API Usage Guide](../guides/api-usage.md)
- [Development Guide](../contributing/development.md)
