# Architecture Overview

Estate Sentry is built with a modern, extensible, and decentralized architecture designed for scalability, redundancy, and intelligent threat analysis. The system can scale from a single home deployment to a large estate with multiple nodes providing full redundancy.

## System Architecture Diagram

```
+------------------------------------------------------------------+
|                         ESTATE SENTRY                             |
|                                                                   |
|  +------------------+    +------------------+    +--------------+ |
|  |   Zone Nodes     |    |   Switchboard    |    |   Sentry     | |
|  |   (Distributed)  |<-->|   (Data Router)  |<-->|  (AI Intel)  | |
|  +--------+---------+    +--------+---------+    +------+-------+ |
|           |                       |                     |         |
|  +--------v---------+    +--------v---------+    +------v-------+ |
|  | Django REST API  |    |  NATS + MinIO    |    | MCP + Vector | |
|  | PostgreSQL       |    |  (Messages/Media)|    | ChromaDB     | |
|  | Neo4j            |    |                  |    | Neo4j        | |
|  +------------------+    +------------------+    +--------------+ |
+------------------------------------------------------------------+
         |                         |                      |
+--------v--------+     +----------v----------+    +------v-------+
|  HQ Dashboard   |     |  Sensors/Devices    |    |  Claude/AI   |
|  (Next.js)      |     |  (MQTT/REST/etc)    |    |  (Analysis)  |
+-----------------+     +---------------------+    +--------------+
```

## Core Components

### 1. Django REST API Backend (`estate-sentry-api`)

The backend is built with Django and Django REST Framework, following a modular app-based architecture.

**Key Features:**
- Token-based authentication with multiple methods
- RESTful API design
- Extensible sensor handler framework with auto-discovery
- Real-time threat detection
- Time-series data storage with TimescaleDB
- Multi-node synchronization

**Django Apps:**

- **authentication** - User management with multiple auth methods (password, PIN, device certificates)
- **sensors** - Sensor registration, data ingestion, handler framework with plugin support
- **alerts** - Threat detection, alert generation, notification system
- **nodes** - Multi-node coordination, discovery, and synchronization
- **audit** - Security audit logging

### 2. Next.js Frontend (`estate-sentry-hq`)

The frontend is a modern React application built with Next.js.

**Key Features:**
- Real-time dashboard with WebSocket streaming
- Sensor monitoring and management
- Alert management and acknowledgment
- Node status monitoring (multi-node)
- Case report viewing
- Dark mode support
- Responsive design

**Technologies:**
- Next.js 15
- React 18
- TypeScript
- Tailwind CSS
- SWR for data fetching

### 3. Switchboard (Data Router)

The Switchboard is the central data routing backbone for all sensor data.

**Key Features:**
- NATS JetStream for message routing
- MinIO for media/frame storage
- Edge agents for embedded cameras
- Multi-node federation
- High-bandwidth video stream handling

**See:** [Switchboard Architecture](switchboard.md)

### 4. Sentry Intelligence

The Sentry Intelligence system provides AI-powered threat analysis.

**Key Features:**
- MCP server for Claude integration
- ChromaDB vector store for pattern matching
- Neo4j for behavioral analysis
- Threat scoring algorithms
- Automated case report generation

**See:** [Sentry Intelligence Architecture](sentry-intelligence.md)

## Decentralization

Estate Sentry supports deployment across multiple nodes for redundancy and scalability.

### Node Topology

```
+-------------------+     +-------------------+     +-------------------+
|   Zone: Main      |     |   Zone: Guest     |     |   Federation Hub  |
|   Primary Node    |<--->|   Primary Node    |<--->|   (Optional)      |
|   + Secondaries   |     |                   |     |   Sentry Intel    |
+-------------------+     +-------------------+     +-------------------+
```

**Features:**
- Automatic node discovery via mDNS
- Manual registration for WAN nodes
- gRPC with mTLS for inter-node communication
- Event sourcing for synchronization
- Automatic failover and leader election

**See:** [Decentralization Architecture](decentralization.md)

## Database Architecture

Estate Sentry uses a multi-database approach optimized for different workloads:

### PostgreSQL (Primary Database)

Stores relational data:
- User accounts
- Sensor configurations
- Sensor readings (time-series via TimescaleDB)
- Security alerts
- Audit logs
- Node registry

**Deployment Options:**
- SQLite for local development
- PostgreSQL with TimescaleDB for production

### Neo4j (Graph Database)

Stores relationship data for threat intelligence:
- Sensor networks and spatial relationships
- Threat patterns and correlations
- Behavioral analysis graphs
- Alert relationship mapping

**Features:**
- APOC plugins
- Graph Data Science algorithms
- Pattern detection queries
- Real-time synchronization from PostgreSQL

### ChromaDB (Vector Database)

Stores embeddings for AI analysis:
- Alert embeddings for similarity search
- Known threat pattern vectors
- Historical incident embeddings

**See:** [Database Architecture](database.md)

## Device Abstraction Layer

Estate Sentry uses a plugin-based device abstraction layer that supports sensors, actuators, and controllers.

### Device Types

| Type | Direction | Examples |
|------|-----------|----------|
| Sensor | Read-only | Cameras, contacts, motion, environmental |
| Actuator | Write/Control | Lights, locks, sirens |
| Controller | Bidirectional | PLCs, hubs, gateways |

### Handler Framework

Each device type has a dedicated handler with auto-discovery:

```python
class BaseSensorHandler:
    SENSOR_TYPES = ['MY_SENSOR']  # Auto-registration
    PROTOCOLS = ['mqtt', 'rest']  # Supported protocols

    def validate_reading(self, data):
        """Validate incoming sensor data"""
        pass

    def process_reading(self, data):
        """Process data into standard format"""
        pass

    def detect_threats(self, reading):
        """Analyze for threats and generate alerts"""
        pass

    @classmethod
    def get_reading_schema(cls):
        """JSON Schema for automatic validation"""
        pass
```

**Built-in Handlers:**
- `CameraHandler` - Camera systems with Switchboard integration
- `ContactHandler` - Door/window sensors
- `GlassBreakHandler` - Glass break detection
- `MotionHandler` - Motion detection
- `EnvironmentalHandler` - Smoke, CO, water leak, temperature

### Protocol Adapters

Communication protocol abstraction:
- MQTT - IoT sensors, home automation
- REST - IP cameras, web services
- Modbus - PLCs, industrial devices
- WebSocket - Real-time streams
- Zigbee/Z-Wave - Consumer sensors

**See:** [Device Abstraction](device-abstraction.md) | [Plugin Development Guide](../guides/plugin-development.md)

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

## Security Architecture

Estate Sentry implements defense-in-depth security:

**Authentication:**
- Token-based API authentication
- PIN authentication (hashed)
- Device certificate binding
- Multi-factor support

**Authorization:**
- Ownership-based access control
- Role-based permissions (future)

**Data Protection:**
- mTLS for inter-node communication
- Encryption at rest (configurable)
- JSON Schema input validation
- Rate limiting

**Audit:**
- Comprehensive audit logging
- 7-year retention (compliance)

**See:** [Security Architecture](security.md)

## Scalability

The architecture supports scaling from single home to large estate:

- **Multi-node deployment** - Distributed across zones
- **Automatic failover** - Leader election, data replication
- **Message queue** - NATS JetStream for async processing
- **Time-series optimization** - TimescaleDB for sensor data
- **Media handling** - MinIO for distributed storage

## Roadmap

See [Development Roadmap](../Todo.md) for the complete implementation plan.

**Current Focus:**
- Security hardening
- Handler registry implementation
- Switchboard foundation
- Node architecture

**Future:**
- Single-shot recognition for cameras
- Mobile applications
- Cloud deployment options
- Advanced ML threat detection

## Development Philosophy

1. **Framework first** - Build robust structure before features
2. **Extensibility** - Easy to add new sensor types
3. **Testing** - Comprehensive test coverage
4. **Documentation** - Clear, accessible documentation
5. **Simplicity** - Clean, maintainable code
6. **Open source** - Transparent, community-driven

## Related Documentation

**Architecture:**
- [Database Architecture](database.md)
- [Decentralization](decentralization.md)
- [Switchboard](switchboard.md)
- [Security](security.md)
- [Device Abstraction](device-abstraction.md)
- [Sentry Intelligence](sentry-intelligence.md)

**Guides:**
- [API Usage Guide](../guides/api-usage.md)
- [Plugin Development](../guides/plugin-development.md)
- [Node Deployment](../guides/node-deployment.md)
- [MCP Integration](../guides/mcp-integration.md)

**Operations:**
- [Monitoring](../operations/monitoring.md)
- [Development Guide](../contributing/development.md)
