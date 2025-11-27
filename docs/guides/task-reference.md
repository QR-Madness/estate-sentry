# Task Reference

Estate Sentry uses [Task](https://taskfile.dev/) for development automation. All tasks are defined in `Taskfile.yaml`.

## Installation

```bash
# Install Task globally
npm install -g @go-task/cli

# Or see: https://taskfile.dev/installation/
```

## Quick Start

```bash
task                # List all available tasks
task setup         # Complete project setup (API + HQ)
task dev           # Start both servers
task info          # Show project information
```

## Setup & Installation

```bash
task setup              # Complete project setup (API + HQ)
task setup:venv         # Create Python virtual environment
task install            # Install all dependencies
```

## Development

```bash
task dev                # Start both API and HQ servers
task api:dev            # Start Django API server (port 8000)
task hq:dev             # Start Next.js HQ server (port 3000)
```

## API Tasks

```bash
task api:install        # Install API dependencies
task api:migrate        # Run database migrations
task api:makemigrations # Create new migrations
task api:superuser      # Create Django superuser
task api:shell          # Open Django shell
task api:test           # Run API tests
task api:test:verbose   # Run tests with verbose output
task api:test:coverage  # Run tests with coverage report
task api:lint           # Lint with flake8
task api:check          # Run Django system checks
task api:clean          # Remove build artifacts
task api:reset-db       # Reset database (⚠️ deletes data)
```

## HQ (Frontend) Tasks

```bash
task hq:install         # Install HQ dependencies
task hq:dev             # Start development server
task hq:build           # Build for production
task hq:start           # Start production server
task hq:lint            # Lint TypeScript/React code
task hq:test            # Run HQ tests
task hq:clean           # Remove build artifacts
```

## Testing

```bash
task test               # Run all tests (API + HQ)
task api:test           # Run API tests only
task hq:test            # Run HQ tests only
task api:test:verbose   # Verbose API tests
task api:test:coverage  # API tests with coverage
```

## Docker Tasks

```bash
task docker:build       # Build all Docker images
task docker:build:api   # Build API image only
task docker:build:hq    # Build HQ image only
task docker:up          # Start all services (detached)
task docker:up:logs     # Start and follow logs
task docker:down        # Stop and remove containers
task docker:restart     # Restart all services
task docker:logs        # View all logs
task docker:logs:api    # View API logs
task docker:shell:api   # Bash shell in API container
task docker:ps          # Show running containers
```

## Database Management

```bash
# SQLite (Local Development)
task db:backup          # Backup SQLite database
task db:restore         # Restore latest backup

# Docker (PostgreSQL)
task db:migrate:docker  # Run migrations in Docker
task db:postgres:backup # Backup PostgreSQL
task db:postgres:restore # Restore PostgreSQL
task db:reset:docker    # Reset database (⚠️ deletes data)

# Neo4j
task db:neo4j:export    # Export Neo4j database
task db:neo4j:import    # Import Neo4j database
task db:neo4j:sync      # Show sync status
task db:neo4j:clear     # Clear all graph data (⚠️)
```

## Utilities

```bash
task clean              # Clean all build artifacts
task check              # Run all checks (lint + test)
task format             # Format code (black/prettier)
task info               # Show project information
task version            # Show tool versions
```

## CI/CD

```bash
task ci:test            # Run CI checks locally
```

## Common Workflows

### First Time Setup

```bash
task setup
task api:superuser
task dev
```

### Daily Development

```bash
# Start servers
task dev

# In another terminal, run tests
task test

# Make database changes
task api:makemigrations
task api:migrate
```

### Before Committing

```bash
task check              # Run linting
task test               # Run tests
task clean              # Clean artifacts
```

### Docker Development

```bash
# Start Docker services
task docker:build
task docker:up

# View logs
task docker:logs:api

# Access shell
task docker:shell:api

# Restart after changes
task docker:restart:api
```

## Tips

- Run `task` or `task --list` to see all available tasks
- Tasks use relative paths, so run from project root
- Most tasks provide helpful feedback with ✅ emoji
- Some tasks (like `api:reset-db`) have confirmation prompts
- Tasks marked with ⚠️ are destructive and should be used carefully

## Environment Setup

Tasks automatically use the correct environment:

- API tasks use `.venv` Python environment
- HQ tasks use local `node_modules`
- No need to manually activate environments

## Customization

To add your own tasks, edit `Taskfile.yaml`. Task uses simple YAML syntax:

```yaml
tasks:
  mytask:
    desc: My custom task
    dir: estate-sentry-api
    cmds:
      - echo "Running my task"
      - python manage.py custom_command
```

## Resources

- [Task Documentation](https://taskfile.dev/)
- [Installation Guide](../getting-started/installation.md)
- [Quick Start Guide](../getting-started/quickstart.md)
