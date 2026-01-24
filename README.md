# Estate Sentry

## Open-Source Home Threat Intelligence System

Why wouldn't you want the world to be safer? Yet, commercial home security systems still gouge us with costs for things we didn't even ask for. Let's change that.

**Estate Sentry** is an intuitive, intelligent, and best of all, **transparent** open-source home security and threat intelligence system. Built on the principle that everyone deserves affordable, customizable home security.

## What is Estate Sentry?

Estate Sentry is a comprehensive, decentralized threat detection and analysis platform designed to scale from a single home to large estates with full redundancy.

### Supported Devices

**Sensors (Read-only):**
- Camera Systems - Video surveillance with AI-powered analysis
- Door & Window Contacts - Intrusion detection for entry points
- Glass Break Sensors - Detect forced entry attempts
- Motion Detectors - Monitor movement in protected areas
- Environmental Sensors - Smoke, CO, water leak, temperature

**Actuators (Control):**
- Lighting Systems - Visible, infrared, security lighting
- Smart Locks - Entry point control
- Sirens/Alarms - Alert systems

**Controllers (Bidirectional):**
- PLCs - Industrial and custom automation
- Hubs/Gateways - Protocol bridges
- Custom Devices - Extensible framework for any device type

### Key Features

- **Decentralized Architecture** - Deploy across multiple nodes for redundancy
- **AI-Powered Intelligence** - MCP integration with Claude for threat analysis
- **Plugin System** - Easy extension for new device types
- **Protocol Flexibility** - MQTT, REST, Modbus, Zigbee, and more
- **Real-time Processing** - Immediate threat detection and alerts
- **Case Reports** - Automated security investigation reports

## Quick Start

### Using Task (Recommended)

```bash
# Complete setup
task setup

# Start both servers
task dev

# Create admin user
task api:superuser
```

### Using Docker (Production)

```bash
# Setup and start services
cp .env.example .env
task docker:build
task docker:up
task db:migrate:docker
```

Your services will be available at:
- **API**: http://localhost:8000
- **Dashboard**: http://localhost:3000
- **Neo4j Browser**: http://localhost:7474

## Documentation

### View Documentation

```bash
# Install mkdocs (one-time setup)
pip install mkdocs mkdocs-material pymdown-extensions

# Serve documentation locally
mkdocs serve
```

Open **http://localhost:8001** to access the complete documentation:

**Getting Started:**
- Installation guides (Docker, Task, Manual)
- Quick start tutorials
- Docker setup

**Architecture:**
- [System Overview](docs/architecture/overview.md)
- [Decentralization](docs/architecture/decentralization.md)
- [Switchboard](docs/architecture/switchboard.md)
- [Security](docs/architecture/security.md)
- [Sentry Intelligence](docs/architecture/sentry-intelligence.md)

**Guides:**
- [API Usage](docs/guides/api-usage.md)
- [Plugin Development](docs/guides/plugin-development.md)
- [Node Deployment](docs/guides/node-deployment.md)
- [MCP Integration](docs/guides/mcp-integration.md)

**Operations:**
- [Monitoring](docs/operations/monitoring.md)

### For Developers

See [CLAUDE.md](CLAUDE.md) for detailed development guidelines.

## Available Commands

Run `task --list` to see all available commands:

```bash
task setup              # Complete project setup
task dev                # Start both API and HQ servers
task api:dev            # Start API server only
task hq:dev             # Start HQ server only
task test               # Run all tests
task docker:build       # Build Docker images
task docker:up          # Start Docker services
```

## Architecture

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

### Core Components

| Component | Description |
|-----------|-------------|
| **Estate Sentry API** | Django REST backend for data and authentication |
| **Estate Sentry HQ** | Next.js dashboard for monitoring and control |
| **Switchboard** | NATS + MinIO data routing backbone |
| **Sentry Intelligence** | AI-powered threat analysis with MCP |
| **Zone Nodes** | Distributed compute units with auto-failover |

### Databases

| Database | Purpose |
|----------|---------|
| **PostgreSQL + TimescaleDB** | Relational data and time-series readings |
| **Neo4j** | Graph relationships for threat intelligence |
| **ChromaDB** | Vector embeddings for AI pattern matching |
| **MinIO** | Object storage for media files |

## Project Status

Estate Sentry is in active architectural development, building the foundation for a production-ready system.

**Completed:**
- ✅ Core sensor framework and API
- ✅ Real-time sensor data processing
- ✅ Docker support with PostgreSQL and Neo4j
- ✅ Comprehensive architecture documentation
- ✅ Plugin-based handler system design

**In Progress:**
- 🚧 Security hardening (PIN hashing, rate limiting)
- 🚧 Handler registry with auto-discovery
- 🚧 Switchboard data routing

**Planned:**
- 📋 Multi-node decentralization
- 📋 Sentry Intelligence with MCP
- 📋 Camera AI analysis
- 📋 Mobile applications

See the [Development Roadmap](docs/Todo.md) for the complete implementation plan.

## Contributing

We welcome contributors! Estate Sentry is an open-source project dedicated to making home security accessible to everyone.

See the documentation's [Development Guide](docs/contributing/development.md) for detailed contribution guidelines.

## License

See [LICENSE](LICENSE) for details.

## Support

For questions, issues, or feature requests, please open an issue on GitHub.
