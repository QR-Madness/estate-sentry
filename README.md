# Estate Sentry

## Open-Source Home Threat Intelligence System

Why wouldn't you want the world to be safer? Yet, commercial home security systems still gouge us with costs for things we didn't even ask for. Let's change that.

**Estate Sentry** is an intuitive, intelligent, and best of all, **transparent** open-source home security and threat intelligence system. Built on the principle that everyone deserves affordable, customizable home security.

## What is Estate Sentry?

Estate Sentry is a comprehensive threat detection and analysis platform that integrates with various security sensors:

- **Camera Systems** - Video surveillance with planned single-shot recognition capabilities
- **Door & Window Contacts** - Intrusion detection for entry points
- **Glass Break Sensors** - Detect forced entry attempts
- **Motion Detectors** - Monitor movement in protected areas
- **Environmental Sensors** - Smoke, CO, water leak detection
- **Custom Sensor Support** - Extensible framework for any sensor type

The system processes sensor data in real-time, analyzes threats, and provides intelligent alerts through the Estate Sentry HQ dashboard.

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

### For Users (Non-Developers)

**View the full documentation:**

```bash
# Install mkdocs (one-time setup)
pip install mkdocs mkdocs-material pymdown-extensions
# OR; if you are using the new version manager from Python:
python -m pip install mkdocs mkdocs-material pymdown-extensions

# View documentation locally
mkdocs serve
```

Then open your browser to **http://localhost:8001** to access the complete documentation with:

- Installation guides
- Quick start tutorials
- API usage examples
- Architecture explanations

### For Developers

See [CLAUDE.md](CLAUDE.md) for detailed development guidelines and architecture documentation.

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

Estate Sentry consists of two main components:

- **Django REST API Backend** (`estate-sentry-api`) - Handles sensor data ingestion, threat analysis, user authentication, and data persistence
- **Next.js/React Frontend** (`estate-sentry-hq`) - Real-time dashboard for monitoring sensors, viewing alerts, and managing your security system

### Databases

- **PostgreSQL** - Relational data (users, sensors, readings, alerts)
- **Neo4j** - Graph database for threat intelligence and relationships

## Project Status

Estate Sentry is currently in active development with a focus on building robust sensor integration frameworks and core architecture.

- ✅ Core sensor framework and API
- ✅ Real-time sensor data processing
- ✅ Docker support with PostgreSQL and Neo4j
- 🚧 Single-shot recognition for camera systems
- 🚧 Advanced threat analysis algorithms
- 🚧 Mobile applications for iOS and Android

## Contributing

We welcome contributors! Estate Sentry is an open-source project dedicated to making home security accessible to everyone.

See the documentation's [Development Guide](docs/contributing/development.md) for detailed contribution guidelines.

## License

See [LICENSE](LICENSE) for details.

## Support

For questions, issues, or feature requests, please open an issue on GitHub.
