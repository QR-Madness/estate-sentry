# Estate Sentry

## Open-Source Home Threat Intelligence System

Why wouldn't you want the world to be safer? Yet, commercial home security systems still gouge us with costs for things we didn't even ask for. Let's change that.

**Estate Sentry** is an intuitive, intelligent, and best of all, **transparent** open-source home security and threat intelligence system. Built on the principle that everyone deserves affordable, customizable home security.

## What is Estate Sentry?

Estate Sentry is a comprehensive threat detection and analysis platform that integrates with various security sensors to monitor and protect your home:

- **Camera Systems** - Video surveillance with planned single-shot recognition capabilities
- **Door & Window Contacts** - Intrusion detection for entry points
- **Glass Break Sensors** - Detect forced entry attempts
- **Motion Detectors** - Monitor movement in protected areas
- **Environmental Sensors** - Smoke, CO, water leak detection
- **Custom Sensor Support** - Extensible framework for any sensor type

The system processes sensor data in real-time, analyzes threats, and provides intelligent alerts through the Estate Sentry HQ dashboard.

## Project Status

Estate Sentry is currently in active development with a focus on building robust sensor integration frameworks and core architecture. Future roadmap includes:

- ✅ Core sensor framework and API
- ✅ Real-time sensor data processing
- 🚧 Single-shot recognition for camera systems
- 🚧 Advanced threat analysis algorithms
- 🚧 Mobile applications for iOS and Android

# Setup & Installation

There are three ways to get started with Estate Sentry:

1. [Docker Setup](#docker-setup-recommended) - **recommended for production**
2. [Easy Installation with Task](#easy-installation-with-task) - **recommended for development**
3. [Manual Setup](#manual-setup) - For those who prefer full control

## Docker Setup (Recommended)

The fastest way to get Estate Sentry running with production databases (PostgreSQL + Neo4j):

```bash
# 1. Copy and configure environment
cp .env.example .env

# 2. Build and start all services
task docker:build
task docker:up

# 3. Run migrations
task db:migrate:docker
```

Your services will be available at:
- **API**: http://localhost:8000
- **Dashboard**: http://localhost:3000
- **Neo4j Browser**: http://localhost:7474

See [DOCKER.md](DOCKER.md) for complete Docker documentation.

## Easy Installation with Task

## Setup & Build from Source

### Prerequisites

- Python 3.10 or higher
- Node.js 18 or higher
- [Task](https://taskfile.dev/) (optional, for easier development)
  - Install: `npm install -g @go-task/cli` or see [installation guide](https://taskfile.dev/installation/)

### Installation Steps

#### Option 1: Using Task (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/estate-sentry.git
cd estate-sentry

# Complete setup (API + Frontend)
task setup

# Start both servers
task dev
```

#### Option 2: Manual Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/estate-sentry.git
   cd estate-sentry
   ```

2. **Set up the Django API Backend**
   ```bash
   # Navigate to API directory
   cd estate-sentry-api

   # Create and activate virtual environment
   python -m venv .venv
   source .venv/Scripts/activate  # On Windows Git Bash
   # or: .venv\Scripts\activate  # On Windows CMD

   # Install Python dependencies
   pip install -r requirements.txt

   # Run database migrations
   python manage.py migrate

   # Create a superuser (for admin access)
   python manage.py createsuperuser

   # Start the development server
   python manage.py runserver
   ```
   The API will be available at `http://localhost:8000`

3. **Set up the Estate Sentry HQ (Frontend)**
   ```bash
   # Navigate to client directory
   cd estate-sentry-hq

   # Install dependencies
   npm install

   # Start development server
   npm run dev
   ```
   The dashboard will be available at `http://localhost:3000`

### Running Tests

**Using Task:**
```bash
task test              # Run all tests
task api:test          # Run API tests only
task hq:test           # Run HQ tests only
task api:test:verbose  # Run API tests with verbose output
```

**Manual:**
```bash
# Backend Tests
cd estate-sentry-api
source .venv/Scripts/activate
python manage.py test

# Frontend Tests
cd estate-sentry-hq
npm test
```

### Common Development Tasks

```bash
task                    # List all available tasks
task setup             # Initial project setup
task dev               # Start both API and HQ servers
task api:dev           # Start API server only
task hq:dev            # Start HQ server only
task api:migrate       # Run database migrations
task api:superuser     # Create Django superuser
task api:shell         # Open Django shell
task clean             # Clean build artifacts
task check             # Run linting and checks
task info              # Show project information
```

## Architecture

Estate Sentry consists of two main components:

- **Django REST API Backend** - Handles sensor data ingestion, threat analysis, user authentication, and data persistence
- **Next.js/React Frontend (HQ)** - Real-time dashboard for monitoring sensors, viewing alerts, and managing your security system

## Contributing

We welcome contributors! Estate Sentry is an open-source project dedicated to making home security accessible to everyone.

Currently, Estate Sentry has no public contributors - let's change this and make the world a safer place!

## License

See [LICENSE](LICENSE) for details.

## Support

For questions, issues, or feature requests, please open an issue on GitHub.