# Installation

There are three ways to get started with Estate Sentry:

1. **Docker Setup** (Recommended for production)
2. **Task Setup** (Recommended for development)
3. **Manual Setup** (For those who prefer full control)

## Prerequisites

- **Python 3.10 or higher**
- **Node.js 18 or higher**
- **Task** (optional, for easier development)
  - Install: `npm install -g @go-task/cli`
  - See: [taskfile.dev/installation](https://taskfile.dev/installation/)

## Option 1: Docker Setup (Recommended for Production)

The fastest way to get Estate Sentry running with production databases (PostgreSQL + Neo4j):

```bash
# 1. Copy and configure environment
cp .env.example .env

# 2. Build and start all services
task docker:build
task docker:up

# 3. Run migrations
task db:migrate:docker

# 4. Create admin user
docker-compose exec api python manage.py createsuperuser
```

Your services will be available at:

- **API**: http://localhost:8000
- **Dashboard**: http://localhost:3000
- **Neo4j Browser**: http://localhost:7474

See [Docker Setup](docker-setup.md) for complete Docker documentation.

## Option 2: Task Setup (Recommended for Development)

Using Task provides the easiest development experience:

```bash
# Clone the repository
git clone https://github.com/yourusername/estate-sentry.git
cd estate-sentry

# Complete setup (API + Frontend)
task setup

# Create admin user
task api:superuser

# Start both servers
task dev
```

The API will be available at `http://localhost:8000` and the HQ dashboard at `http://localhost:3000`.

## Option 3: Manual Setup

### Backend (Django API)

1. **Navigate to API directory**
   ```bash
   cd estate-sentry-api
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv .venv
   source .venv/Scripts/activate  # On Windows Git Bash
   # or: .venv\Scripts\activate  # On Windows CMD
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run migrations**
   ```bash
   python manage.py migrate
   ```

5. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

6. **Start development server**
   ```bash
   python manage.py runserver
   ```

The API will be available at `http://localhost:8000`.

### Frontend (Estate Sentry HQ)

1. **Navigate to HQ directory**
   ```bash
   cd estate-sentry-hq
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Start development server**
   ```bash
   npm run dev
   ```

The dashboard will be available at `http://localhost:3000`.

## Verify Installation

1. **Access the API**
   - Visit http://localhost:8000/admin/
   - Login with your superuser credentials

2. **Access the Dashboard**
   - Visit http://localhost:3000
   - The HQ dashboard should load

3. **Run tests**
   ```bash
   task test
   # or manually:
   cd estate-sentry-api
   python manage.py test
   ```

## Next Steps

- Follow the [Quick Start Guide](quickstart.md) to test the API
- Check the [Task Reference](../guides/task-reference.md) for available commands
- Read the [API Usage Guide](../guides/api-usage.md) for endpoint documentation
