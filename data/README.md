# Estate Sentry Data Directory

This directory contains persistent data for Estate Sentry's databases and backups.

## Directory Structure

```
data/
├── neo4j/              # Neo4j graph database data
│   ├── data/          # Neo4j database files (auto-generated)
│   ├── logs/          # Neo4j logs (auto-generated)
│   ├── plugins/       # Neo4j plugins (auto-generated)
│   ├── import/        # Place CSV/JSON files here for Neo4j import
│   └── export/        # Neo4j database exports
└── backups/           # Database backups
    ├── postgres_*.sql # PostgreSQL backups
    └── neo4j_*.cypher # Neo4j backups
```

## Neo4j Database

The Neo4j database is automatically synchronized between Docker containers and this directory through volume mounting.

### Key Directories:

- **`neo4j/data/`** - Contains the actual graph database files. This is automatically managed by Neo4j.
- **`neo4j/logs/`** - Contains Neo4j server logs for debugging.
- **`neo4j/import/`** - Place files here that you want to import into Neo4j using `LOAD CSV` or similar commands.
- **`neo4j/export/`** - Database exports are saved here when you run `task db:neo4j:export`.

### Accessing Neo4j:

- **Browser Interface**: http://localhost:7474
- **Bolt Protocol**: bolt://localhost:7687
- **Default Credentials**: neo4j / changeme (change via .env)

## Database Synchronization

All Neo4j data is synchronized in real-time between your local filesystem and the Docker container. This means:

1. Data persists even when containers are stopped
2. You can inspect database files directly on your filesystem
3. Backups can be easily copied/moved
4. Version control of exports is possible

## Task Commands

### Neo4j Database Tasks:

```bash
# View synchronized data
task db:neo4j:sync

# Export database to export/ directory
task db:neo4j:export

# Import database from latest export
task db:neo4j:import

# Clear all graph data
task db:neo4j:clear
```

### PostgreSQL Database Tasks:

```bash
# Backup PostgreSQL to backups/ directory
task db:postgres:backup

# Restore from latest backup
task db:postgres:restore
```

### Docker Shell Access:

```bash
# Open Neo4j Cypher shell
task docker:shell:neo4j

# Open PostgreSQL shell
task docker:shell:postgres
```

## Important Notes

- **Do not manually edit** files in `neo4j/data/` or `neo4j/logs/` - these are managed by Neo4j
- **Place import files** in `neo4j/import/` for safe importing
- **Backups** are created with timestamps for versioning
- **Git ignores** database files but keeps directory structure

## Security

The `data/` directory contains sensitive database information. The `.gitignore` file is configured to:

- Ignore actual database files (`data/`, `logs/`, `plugins/`)
- Ignore backup files (`*.sql`, `*.dump`)
- Keep directory structure with `.gitkeep` files
- Allow tracking of import/export scripts if needed

**Never commit** actual database files or backups to version control.
