# Estate Sentry

**Open-source automated intelligence for personal and public safety.**

Estate Sentry is a prototype threat intelligence platform that combines real-time sensor monitoring, zone-based perception, and AI-powered analysis to make security accessible, transparent, and affordable.

> **Prototype Notice** &mdash; This software is a demonstrational prototype under active development. It is not licensed for public intelligence gathering. See the [Specification](Specification.md) for the full system design.

---

## Start Here

### I want to understand the system

- **[Specification](Specification.md)** &mdash; The complete intelligence architecture: perception layers, zone model, identity pipeline, and threat assessment.
- **[Architecture Overview](architecture/overview.md)** &mdash; How the API, Switchboard, databases, and dashboard fit together.
- **[Database Architecture](architecture/database.md)** &mdash; PostgreSQL, Neo4j, ChromaDB, and MinIO roles.
- **[Roadmap](Todo.md)** &mdash; What's built, what's next.

### I want to run it locally

- **[Installation](getting-started/installation.md)** &mdash; Three setup paths: Docker, Task runner, or manual.
- **[Quick Start](getting-started/quickstart.md)** &mdash; Register a user, create a sensor, trigger your first alert.
- **[Docker Setup](getting-started/docker-setup.md)** &mdash; Full stack with PostgreSQL, Neo4j, NATS, MinIO, and ChromaDB.

### I want to build on it

- **[Plugin Development](guides/plugin-development.md)** &mdash; Create a sensor handler in under 50 lines.
- **[API Usage](guides/api-usage.md)** &mdash; Every endpoint with request/response examples.
- **[MCP Integration](guides/mcp-integration.md)** &mdash; Connect Claude for AI-powered threat analysis.
- **[Development Guide](contributing/development.md)** &mdash; Tooling, testing, and contribution workflow.

### I want to deploy and operate it

- **[Node Deployment](guides/node-deployment.md)** &mdash; Single-node and multi-node configurations.
- **[Monitoring](operations/monitoring.md)** &mdash; Prometheus metrics, Grafana dashboards, alerting rules.
- **[Task Reference](guides/task-reference.md)** &mdash; Every `task` command for setup, dev, Docker, and database ops.

---

## Quick Start

```bash
# Clone and setup
git clone https://github.com/QR-Madness/estate-sentry.git
cd estate-sentry
task setup

# Create admin user and start dev servers
task api:superuser
task dev
```

API at **localhost:8000** &middot; Dashboard at **localhost:3000** &middot; Docs at **localhost:8001** (`task docs:serve`)
