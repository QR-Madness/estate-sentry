# Docker Setup Guide

Estate Sentry provides full Docker support with PostgreSQL and Neo4j databases for production-ready deployments.

## Quick Start

```bash
# 1. Copy environment file and configure
cp .env.example .env
# Edit .env with your settings

# 2. Build Docker images
task docker:build

# 3. Start all services
task docker:up

# 4. Run migrations
task db:migrate:docker

# 5. Create admin user
docker-compose exec api python manage.py createsuperuser
```

Your services will be available at:

- **API**: http://localhost:8000
- **HQ Dashboard**: http://localhost:3000
- **Neo4j Browser**: http://localhost:7474
- **PostgreSQL**: localhost:5432

## Services

### 1. PostgreSQL Database
- **Container**: estate-sentry-postgres
- **Image**: postgres:16-alpine
- **Port**: 5432
- **Database**: estate_sentry
- **User**: estate_sentry (configurable via .env)

### 2. Neo4j Graph Database
- **Container**: estate-sentry-neo4j
- **Image**: neo4j:5.15-community
- **HTTP Port**: 7474 (Browser UI)
- **Bolt Port**: 7687 (Database connection)
- **Plugins**: APOC, Graph Data Science
- **Data Location**: `./data/neo4j/`

### 3. Django API
- **Container**: estate-sentry-api
- **Image**: estate-sentry-api:latest
- **Port**: 8000
- **Runtime**: Python 3.11 with Gunicorn

### 4. Next.js HQ Frontend
- **Container**: estate-sentry-hq
- **Image**: estate-sentry-hq:latest
- **Port**: 3000
- **Runtime**: Node.js 18

## Environment Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

### Key Environment Variables

```bash
# Django
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,api

# PostgreSQL
POSTGRES_DB=estate_sentry
POSTGRES_USER=estate_sentry
POSTGRES_PASSWORD=your-secure-password

# Neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-secure-password

# Ports (optional, defaults shown)
API_PORT=8000
HQ_PORT=3000
NEO4J_HTTP_PORT=7474
NEO4J_BOLT_PORT=7687
POSTGRES_PORT=5432
```

## Docker Tasks Reference

### Building

```bash
task docker:build              # Build all images
task docker:build:api          # Build API image only
task docker:build:hq           # Build HQ image only
```

### Starting/Stopping

```bash
task docker:up                 # Start all services (detached)
task docker:up:logs            # Start and follow logs
task docker:down               # Stop and remove containers
task docker:down:volumes       # Stop and remove volumes (⚠️ deletes data)
task docker:restart            # Restart all services
task docker:restart:api        # Restart API only
task docker:restart:hq         # Restart HQ only
```

### Viewing Logs

```bash
task docker:logs               # View all logs
task docker:logs:api           # View API logs
task docker:logs:hq            # View HQ logs
task docker:logs:postgres      # View PostgreSQL logs
task docker:logs:neo4j         # View Neo4j logs
```

### Shell Access

```bash
task docker:shell:api          # Bash shell in API container
task docker:shell:postgres     # PostgreSQL psql shell
task docker:shell:neo4j        # Neo4j Cypher shell
task docker:ps                 # Show running containers
```

### Database Management

```bash
# Migrations
task db:migrate:docker         # Run Django migrations in Docker

# PostgreSQL Backup/Restore
task db:postgres:backup        # Backup to data/backups/
task db:postgres:restore       # Restore from latest backup
task db:reset:docker           # Reset database (⚠️ deletes data)

# Neo4j Export/Import
task db:neo4j:export           # Export to data/neo4j/export/
task db:neo4j:import           # Import from latest export
task db:neo4j:sync             # Show sync status
task db:neo4j:clear            # Clear all graph data (⚠️)
```

### Cleanup

```bash
task docker:clean              # Remove stopped containers and unused images
```

## Data Persistence

### Neo4j Data Synchronization

Neo4j data is automatically synchronized to `./data/neo4j/`:

- **data/** - Database files
- **logs/** - Server logs
- **import/** - Place files here for importing
- **export/** - Database exports
- **plugins/** - Installed plugins

### PostgreSQL Data

PostgreSQL data is stored in a Docker volume:

- **Volume**: `postgres_data`
- **Backups**: Stored in `./data/backups/`

### API Static/Media Files

- **Static files**: Docker volume `api_static`
- **Media files**: Docker volume `api_media`

## Development Workflow

### Initial Setup

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with your settings

# 2. Build images
task docker:build

# 3. Start services
task docker:up

# 4. Run migrations
task db:migrate:docker

# 5. Create admin user
docker-compose exec api python manage.py createsuperuser
```

### Daily Development

```bash
# Start services
task docker:up

# View logs
task docker:logs:api

# Access shells
task docker:shell:api
task docker:shell:neo4j

# Restart after code changes
task docker:restart:api
```

### Making Database Changes

```bash
# 1. Create migrations
docker-compose exec api python manage.py makemigrations

# 2. Apply migrations
task db:migrate:docker

# 3. Backup if needed
task db:postgres:backup
```

## Production Deployment

### Security Checklist

Before deploying to production:

1. **Change all default passwords** in `.env`
2. **Generate new Django secret key**:
   ```bash
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```
3. **Set `DJANGO_DEBUG=False`**
4. **Configure `DJANGO_ALLOWED_HOSTS`** with your domain
5. **Use HTTPS** (add reverse proxy like Nginx)
6. **Set up regular backups**:
   ```bash
   # Add to crontab
   0 2 * * * cd /path/to/estate-sentry && task db:postgres:backup
   0 2 * * * cd /path/to/estate-sentry && task db:neo4j:export
   ```

## Troubleshooting

### Containers won't start

```bash
# Check container status
task docker:ps

# View logs for errors
task docker:logs

# Check specific service
task docker:logs:api
task docker:logs:postgres
task docker:logs:neo4j
```

### Database connection errors

1. Ensure databases are healthy:
   ```bash
   docker-compose ps
   ```
   All services should show "healthy" status

2. Check environment variables in `.env`

3. Verify network connectivity:
   ```bash
   docker network inspect estate-sentry-source_estate-sentry-network
   ```

### Port conflicts

If ports are already in use, change them in `.env`:

```bash
API_PORT=8001
HQ_PORT=3001
NEO4J_HTTP_PORT=7475
NEO4J_BOLT_PORT=7688
POSTGRES_PORT=5433
```

### Rebuild after changes

```bash
# Rebuild specific service
task docker:build:api

# Rebuild and restart
task docker:build:api && task docker:restart:api

# Complete rebuild
task docker:down
task docker:build
task docker:up
```

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Neo4j Docker Documentation](https://neo4j.com/docs/operations-manual/current/docker/)
- [PostgreSQL Docker Documentation](https://hub.docker.com/_/postgres)
- Task commands: `task --list`
