# Estate Sentry Documentation

Welcome to the Estate Sentry documentation. Estate Sentry is an open-source home threat intelligence system that makes home security accessible, transparent, and affordable.

## What is Estate Sentry?

Estate Sentry is a comprehensive threat detection and analysis platform that integrates with various security sensors to monitor and protect your home:

- **Camera Systems** - Video surveillance with planned single-shot recognition
- **Door & Window Contacts** - Intrusion detection for entry points
- **Glass Break Sensors** - Detect forced entry attempts
- **Motion Detectors** - Monitor movement in protected areas
- **Environmental Sensors** - Smoke, CO, water leak detection
- **Custom Sensors** - Extensible framework for any sensor type

## Architecture

Estate Sentry consists of two main components:

- **Django REST API Backend** (`estate-sentry-api`) - Handles sensor data ingestion, threat analysis, user authentication, and data persistence
- **Next.js/React Frontend** (`estate-sentry-hq`) - Real-time dashboard for monitoring sensors, viewing alerts, and managing your security system

## Quick Links

- [Installation Guide](getting-started/installation.md) - Get Estate Sentry up and running
- [Quick Start](getting-started/quickstart.md) - Test the API and create your first sensors
- [Docker Setup](getting-started/docker-setup.md) - Production deployment with Docker
- [Task Reference](guides/task-reference.md) - Development automation commands
- [API Usage Guide](guides/api-usage.md) - Complete API endpoint documentation

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

For development guidelines, see the [Development Guide](contributing/development.md).

## Support

For questions, issues, or feature requests, please open an issue on GitHub.
