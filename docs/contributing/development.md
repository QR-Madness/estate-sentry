# Development Guide

Welcome to Estate Sentry development! This guide will help you contribute to the project.

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Git
- Task (optional but recommended)

### Initial Setup

```bash
# Clone repository
git clone https://github.com/yourusername/estate-sentry.git
cd estate-sentry

# Setup environment
task setup

# Create admin user
task api:superuser

# Start development servers
task dev
```

## Project Structure

```
estate-sentry-source/
├── estate-sentry-api/      # Django backend
├── estate-sentry-hq/       # Next.js frontend
├── data/                   # Database volumes
├── docs/                   # Documentation (mkdocs)
├── Taskfile.yaml          # Task automation
├── docker-compose.yml     # Docker orchestration
└── .env.example           # Environment template
```

## Development Workflow

### Daily Development

```bash
# Start servers
task dev

# In another terminal
task api:test          # Run tests
task api:shell         # Django shell
task check             # Run linting
```

### Making Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Backend: `estate-sentry-api/`
   - Frontend: `estate-sentry-hq/`
   - Docs: `docs/`

3. **Run tests**
   ```bash
   task test
   task check
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "Add: your feature description"
   ```

5. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   ```

## Backend Development

### Django Apps

Estate Sentry follows Django's app-based architecture:

- **authentication** - User management
- **sensors** - Sensor framework
- **alerts** - Alert system

### Creating a New App

```bash
cd estate-sentry-api
python manage.py startapp your_app_name

# Add to INSTALLED_APPS in settings.py
# Create models, views, serializers, tests
```

### Database Changes

```bash
# Create migrations
task api:makemigrations

# Apply migrations
task api:migrate

# Backup first (recommended)
task db:backup
```

### Adding a Sensor Handler

1. **Create handler file**
   ```bash
   # estate-sentry-api/sensors/handlers/your_sensor.py
   ```

2. **Implement handler**
   ```python
   from .base import BaseSensorHandler

   class YourSensorHandler(BaseSensorHandler):
       def validate_reading(self, data):
           """Validate sensor data"""
           if 'required_field' not in data:
               return False, "Missing required_field"
           return True, None

       def process_reading(self, sensor, data):
           """Process and store reading"""
           # Your processing logic
           return processed_data

       def detect_threats(self, reading):
           """Analyze for threats"""
           threats = []
           # Your threat detection logic
           return threats
   ```

3. **Register handler**
   ```python
   # In sensors/serializers.py and sensors/views.py
   HANDLER_MAP = {
       'YOUR_SENSOR': 'YourSensorHandler',
       # ...
   }
   ```

4. **Write tests**
   ```python
   # In sensors/tests.py
   class YourSensorHandlerTest(TestCase):
       def test_validate_reading(self):
           # Test validation
           pass
   ```

### Writing Tests

```bash
# Run all tests
task api:test

# Run specific app
python manage.py test authentication

# Run specific test
python manage.py test sensors.tests.ContactHandlerTest

# With coverage
task api:test:coverage
```

**Test Structure:**
```python
from django.test import TestCase
from rest_framework.test import APIClient

class YourTest(TestCase):
    def setUp(self):
        """Setup test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='test',
            password='test123'
        )
        self.client.force_authenticate(user=self.user)

    def test_your_feature(self):
        """Test your feature"""
        response = self.client.get('/api/your-endpoint/')
        self.assertEqual(response.status_code, 200)
```

### API Documentation

Update API docs when adding endpoints:

```python
# In views.py
class YourViewSet(viewsets.ModelViewSet):
    """
    API endpoint for your resource.

    list: Get all items
    create: Create new item
    retrieve: Get single item
    update: Update item
    destroy: Delete item
    """
```

## Frontend Development

### Component Structure

```
estate-sentry-hq/
├── pages/              # Next.js pages
├── components/         # React components
├── contexts/           # React contexts
├── lib/               # Utilities
└── styles/            # CSS/Tailwind
```

### Creating Components

```typescript
// components/YourComponent.tsx
import React from 'react';

interface YourComponentProps {
  title: string;
}

export default function YourComponent({ title }: YourComponentProps) {
  return (
    <div>
      <h2>{title}</h2>
    </div>
  );
}
```

### Using API

```typescript
import useSWR from 'swr';

function YourComponent() {
  const { data, error } = useSWR('/api/sensors/', fetcher);

  if (error) return <div>Error loading data</div>;
  if (!data) return <div>Loading...</div>;

  return <div>{/* Your component */}</div>;
}
```

### Styling

Estate Sentry uses Tailwind CSS:

```tsx
<div className="bg-gray-900 text-white p-4 rounded-lg shadow-xl">
  <h2 className="text-2xl font-bold mb-4">Title</h2>
</div>
```

## Docker Development

### Building Images

```bash
# Build all images
task docker:build

# Build specific image
task docker:build:api
task docker:build:hq
```

### Development with Docker

```bash
# Start services
task docker:up

# View logs
task docker:logs:api

# Access shell
task docker:shell:api

# Restart after code changes
task docker:restart:api
```

### Dockerfile Changes

When modifying Dockerfiles:

```bash
# Rebuild image
task docker:build:api

# Restart container
task docker:restart:api
```

## Documentation

### Writing Documentation

Estate Sentry uses MkDocs:

```bash
# Serve locally
mkdocs serve

# Build documentation
mkdocs build
```

**Documentation Location:**
- User docs: `docs/`
- Code comments: In source files
- API docs: Docstrings in views

### Documentation Standards

- Use clear, concise language
- Include code examples
- Add screenshots when helpful
- Keep structure organized
- Update when changing features

## Code Standards

### Python (Backend)

- **Style**: PEP 8
- **Linting**: flake8
- **Formatting**: black (optional)
- **Type hints**: Encouraged

```bash
# Lint code
task api:lint

# Format code (if black installed)
task format
```

**Example:**
```python
from typing import List, Optional

def get_sensors(user_id: int) -> List[Sensor]:
    """
    Get all sensors for a user.

    Args:
        user_id: The user's ID

    Returns:
        List of Sensor objects
    """
    return Sensor.objects.filter(owner_id=user_id)
```

### TypeScript (Frontend)

- **Style**: Airbnb/Standard
- **Linting**: ESLint
- **Formatting**: Prettier

```bash
# Lint code
task hq:lint

# Format code
task format
```

**Example:**
```typescript
interface Sensor {
  id: number;
  name: string;
  sensorType: string;
  status: string;
}

function getSensors(): Promise<Sensor[]> {
  return fetch('/api/sensors/')
    .then(res => res.json());
}
```

## Git Workflow

### Commit Messages

Use conventional commits:

```
feat: Add glass break sensor handler
fix: Correct alert severity calculation
docs: Update installation guide
test: Add tests for contact handler
refactor: Simplify sensor validation
```

### Branch Naming

```
feature/sensor-glass-break
fix/alert-timestamp
docs/api-reference
test/contact-handler
```

### Pull Requests

1. Create descriptive PR title
2. Explain changes in description
3. Reference related issues
4. Ensure tests pass
5. Request review

## Testing Strategy

### Unit Tests

Test individual components:

```python
def test_sensor_creation(self):
    sensor = Sensor.objects.create(
        name="Test Sensor",
        sensor_type="DOOR_CONTACT",
        owner=self.user
    )
    self.assertEqual(sensor.name, "Test Sensor")
```

### Integration Tests

Test API endpoints:

```python
def test_create_sensor_endpoint(self):
    response = self.client.post('/api/sensors/', {
        'name': 'Front Door',
        'sensor_type': 'DOOR_CONTACT',
        'location': 'Main Entrance'
    })
    self.assertEqual(response.status_code, 201)
```

### Coverage Goals

- Maintain 80%+ code coverage
- Test all API endpoints
- Test sensor handlers
- Test authentication flows

## Debugging

### Backend Debugging

```python
# Add breakpoints
import pdb; pdb.set_trace()

# Or use Django's built-in debugging
import logging
logger = logging.getLogger(__name__)
logger.debug(f"Sensor data: {sensor_data}")
```

### Frontend Debugging

```typescript
// Console debugging
console.log('Sensor data:', sensors);

// React DevTools
// Install browser extension for component inspection
```

### Docker Debugging

```bash
# View logs
task docker:logs:api

# Access shell
task docker:shell:api

# Check environment
docker-compose exec api env
```

## Performance

### Database Optimization

```python
# Use select_related for foreign keys
sensors = Sensor.objects.select_related('owner').all()

# Use prefetch_related for reverse relations
users = User.objects.prefetch_related('sensors').all()

# Add indexes
class Meta:
    indexes = [
        Index(fields=['owner', '-created_at']),
    ]
```

### Frontend Optimization

```typescript
// Use SWR for caching
const { data } = useSWR('/api/sensors/', fetcher);

// Memoize expensive computations
const filteredSensors = useMemo(
  () => sensors.filter(s => s.status === 'ACTIVE'),
  [sensors]
);
```

## Security

### Backend Security

- Never commit secrets
- Use environment variables
- Validate all input
- Use Django's built-in protections
- Keep dependencies updated

### Frontend Security

- Sanitize user input
- Use HTTPS in production
- Implement CORS properly
- Store tokens securely

## Getting Help

- **Documentation**: Check `docs/`
- **Issues**: Open GitHub issue
- **Discussions**: GitHub discussions
- **Code**: Read existing code for examples

## Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [DRF Documentation](https://www.django-rest-framework.org/)
- [Next.js Documentation](https://nextjs.org/docs)
- [React Documentation](https://react.dev/)
- [Task Documentation](https://taskfile.dev/)
