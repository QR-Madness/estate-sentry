# Quick Start Guide

This guide will help you get started with Estate Sentry by testing the API and creating your first sensors.

## Prerequisites

Make sure you've completed the [Installation](installation.md) and have:

- API running at http://localhost:8000
- Admin user created
- Terminal ready for curl commands

## Step 1: Register a User

```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "securepass123",
    "auth_method": "password"
  }'
```

## Step 2: Login and Get Token

```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "securepass123"
  }'
```

**Save the token from the response** - you'll need it for authenticated requests.

Example response:
```json
{
  "token": "abc123def456...",
  "user": {
    "id": 1,
    "username": "testuser",
    "email": "test@example.com"
  }
}
```

## Step 3: Create a Sensor

Replace `YOUR_TOKEN_HERE` with the token from Step 2:

```bash
curl -X POST http://localhost:8000/api/sensors/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Token YOUR_TOKEN_HERE" \
  -d '{
    "name": "Front Door Sensor",
    "sensor_type": "DOOR_CONTACT",
    "location": "Main Entrance",
    "status": "ACTIVE"
  }'
```

Save the sensor `id` from the response.

## Step 4: Submit a Sensor Reading

Replace `1` with your sensor ID and use your token:

```bash
curl -X POST http://localhost:8000/api/sensors/1/readings/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Token YOUR_TOKEN_HERE" \
  -d '{
    "value": {"state": "open"},
    "reading_type": "contact_state"
  }'
```

**This will automatically create an alert** because the door was opened!

## Step 5: View Alerts

```bash
curl http://localhost:8000/api/alerts/ \
  -H "Authorization: Token YOUR_TOKEN_HERE"
```

You should see an alert for the door opening.

## Step 6: Acknowledge an Alert

Replace `1` with your alert ID:

```bash
curl -X PATCH http://localhost:8000/api/alerts/1/acknowledge/ \
  -H "Authorization: Token YOUR_TOKEN_HERE"
```

## Available Sensor Types

When creating sensors, you can use these sensor types:

- `CAMERA` - Camera systems
- `DOOR_CONTACT` - Door contact sensors
- `WINDOW_CONTACT` - Window contact sensors
- `GLASS_BREAK` - Glass break detectors
- `MOTION` - Motion detectors
- `SMOKE` - Smoke detectors
- `CO` - Carbon monoxide detectors
- `WATER_LEAK` - Water leak detectors
- `CUSTOM` - Custom sensor types

## Using Task Commands

If you're using Task, here are some helpful commands:

```bash
# Start development servers
task dev

# Run tests
task test

# Create superuser
task api:superuser

# Run migrations
task api:migrate

# View all available tasks
task --list
```

## Using the Admin Interface

1. Visit http://localhost:8000/admin/
2. Login with your superuser credentials
3. Explore:
   - **Users** - Manage user accounts
   - **Sensors** - View and configure sensors
   - **Sensor readings** - View all sensor data
   - **Alerts** - Monitor security alerts

## Next Steps

- Check the [API Usage Guide](../guides/api-usage.md) for complete endpoint documentation
- Read the [Architecture Overview](../architecture/overview.md) to understand the system
- See the [Development Guide](../contributing/development.md) to contribute
