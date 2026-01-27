# Estate Sentry

**Open-source automated intelligence for personal and public safety.**

Estate Sentry is a prototype threat intelligence platform that amplifies personal and public safety through automated sensor monitoring, zone-based perception, and AI-powered threat analysis. It is designed to be transparent, extensible, and self-hosted.

> **This is a demonstrational prototype** under active development. It is not licensed for public intelligence gathering.

## How it works

Cameras and sensors feed into a layered perception pipeline that detects objects, identifies people, recognizes actions, and correlates events across zones. Threat scores are computed in real time and high-severity events are analyzed by an LLM for natural-language reasoning.

```
Cameras & Sensors --> Switchboard (NATS) --> Perception Pipeline --> Threat Assessment
                                                  |                        |
                                            Zone Events              AI Analysis
                                            Identity Store           Alert System
                                                  |                        |
                                                  +-----> HQ Dashboard <---+
```

## Stack

| Layer | Technology |
|-------|-----------|
| API | Django 5 + Django REST Framework |
| Dashboard | Next.js 15 + React 18 + Tailwind |
| Message Bus | NATS 2.10 (JetStream) |
| Relational DB | PostgreSQL (TimescaleDB) |
| Graph DB | Neo4j 5 |
| Vector DB | ChromaDB |
| Object Storage | MinIO |
| AI Analysis | Claude via MCP |
| Tooling | uv (Python), bun (TypeScript), Task runner |

## Quick Start

```bash
git clone https://github.com/QR-Madness/estate-sentry.git
cd estate-sentry
task setup
task api:superuser
task dev
```

API at `localhost:8000` &middot; Dashboard at `localhost:3000`

For Docker deployment: `task docker:up` (starts PostgreSQL, Neo4j, NATS, MinIO, ChromaDB, API, and HQ).

## Documentation

Full documentation is published at **[QR-Madness.github.io/estate-sentry](https://QR-Madness.github.io/estate-sentry)** or serve locally with `task docs:serve`.

Key docs:

- [Specification](https://QR-Madness.github.io/estate-sentry/Specification/) &mdash; Perception layers, zone model, identity pipeline, threat scoring
- [Architecture](https://QR-Madness.github.io/estate-sentry/architecture/overview/) &mdash; System design and database roles
- [Roadmap](https://QR-Madness.github.io/estate-sentry/Todo/) &mdash; Implementation plan and milestones

## Contributing

See the [Development Guide](https://QR-Madness.github.io/estate-sentry/contributing/development/) for tooling, testing, and contribution workflow.

## License

See [LICENSE](LICENSE) for details.
