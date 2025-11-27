# Estate Sentry API

Django REST Framework API for the Estate Sentry home threat intelligence system.

## Quick Start

```bash
# Activate virtual environment
source .venv/Scripts/activate  # Windows Git Bash
# or: .venv\Scripts\activate   # Windows CMD

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

## Project Structure

```
estate-sentry-api/
├── .venv/                  # Virtual environment
├── estate_sentry/          # Main Django project
│   ├── settings.py         # Django settings
│   └── urls.py            # Root URL configuration
├── authentication/         # User authentication app
├── sensors/               # Sensor management app
│   └── handlers/          # Sensor-specific handlers
├── alerts/                # Alert management app
├── manage.py              # Django management script
└── requirements.txt       # Python dependencies
```

## Available Apps

### Authentication
User management with flexible authentication methods (username, PIN, password).

**Models:** User

**Endpoints:**
- POST /api/auth/register/
- POST /api/auth/login/
- POST /api/auth/logout/
- GET/PATCH /api/auth/user/

### Sensors
Sensor registration, configuration, and reading ingestion.

**Models:** Sensor, SensorReading

**Endpoints:**
- GET/POST /api/sensors/
- GET/PATCH/DELETE /api/sensors/{id}/
- POST /api/sensors/{id}/readings/
- GET /api/sensors/{id}/reading_history/

### Alerts
Security alerts and threat notifications.

**Models:** Alert

**Endpoints:**
- GET /api/alerts/
- GET /api/alerts/{id}/
- PATCH /api/alerts/{id}/acknowledge/
- GET /api/alerts/statistics/

## Development

### Running Tests

```bash
python manage.py test
python manage.py test authentication  # Specific app
python manage.py test --verbosity=2    # Verbose output
```

### Database Management

```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Reset database (development only)
rm db.sqlite3
python manage.py migrate
```

### Admin Interface

Access at http://localhost:8000/admin/ after creating a superuser.

## Environment Variables

Copy `.env.example` to `.env` and configure:

- `SECRET_KEY` - Django secret key
- `DEBUG` - Debug mode (True/False)
- `DATABASE_URL` - Database connection string
- `ALLOWED_HOSTS` - Allowed hosts for production
- `CORS_ALLOWED_ORIGINS` - CORS origins for frontend

## Sensor Handler Framework

See `sensors/handlers/` for the extensible handler framework. Each sensor type has a handler that:

1. Validates incoming sensor data
2. Processes data into standard format
3. Detects threats and generates alerts

Add new sensor types by creating handlers in `sensors/handlers/`.
