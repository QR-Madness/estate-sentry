# API Usage Guide

Complete reference for the Estate Sentry REST API endpoints.

## Base URL

- **Development**: `http://localhost:8000`
- **Docker**: `http://localhost:8000`

## Authentication

Estate Sentry uses token-based authentication. Include the token in the Authorization header:

```
Authorization: Token YOUR_TOKEN_HERE
```

## Authentication Endpoints

### Register User

**POST** `/api/auth/register/`

Create a new user account.

**Request Body:**
```json
{
  "username": "testuser",
  "email": "test@example.com",
  "password": "securepass123",
  "auth_method": "password"
}
```

**Auth Methods:**
- `"password"` - Standard username/password
- `"pin"` - 4-digit PIN authentication
- `"username"` - Username-only (for trusted devices)

**Response:**
```json
{
  "id": 1,
  "username": "testuser",
  "email": "test@example.com",
  "auth_method": "password"
}
```

### Login

**POST** `/api/auth/login/`

Login and receive authentication token.

**Request Body:**
```json
{
  "username": "testuser",
  "password": "securepass123"
}
```

**Response:**
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

### Logout

**POST** `/api/auth/logout/`

Invalidate the current authentication token.

**Headers:** Requires authentication

**Response:**
```json
{
  "message": "Successfully logged out"
}
```

### Get Current User

**GET** `/api/auth/user/`

Get current user information.

**Headers:** Requires authentication

**Response:**
```json
{
  "id": 1,
  "username": "testuser",
  "email": "test@example.com",
  "auth_method": "password"
}
```

### Update User Profile

**PATCH** `/api/auth/user/`

Update user profile information.

**Headers:** Requires authentication

**Request Body:**
```json
{
  "email": "newemail@example.com"
}
```

## Sensor Endpoints

### List Sensors

**GET** `/api/sensors/`

Get all sensors for the authenticated user.

**Headers:** Requires authentication

**Response:**
```json
[
  {
    "id": 1,
    "name": "Front Door Sensor",
    "sensor_type": "DOOR_CONTACT",
    "location": "Main Entrance",
    "status": "ACTIVE",
    "handler_class": "ContactHandler",
    "connection_config": {},
    "metadata": {},
    "created_at": "2024-11-27T10:00:00Z",
    "updated_at": "2024-11-27T10:00:00Z"
  }
]
```

### Create Sensor

**POST** `/api/sensors/`

Register a new sensor.

**Headers:** Requires authentication

**Request Body:**
```json
{
  "name": "Front Door Sensor",
  "sensor_type": "DOOR_CONTACT",
  "location": "Main Entrance",
  "status": "ACTIVE",
  "connection_config": {},
  "metadata": {}
}
```

**Sensor Types:**
- `CAMERA`
- `DOOR_CONTACT`
- `WINDOW_CONTACT`
- `GLASS_BREAK`
- `MOTION`
- `SMOKE`
- `CO`
- `WATER_LEAK`
- `CUSTOM`

**Sensor Status:**
- `ACTIVE`
- `INACTIVE`
- `ERROR`
- `MAINTENANCE`

### Get Sensor Details

**GET** `/api/sensors/{id}/`

Get details for a specific sensor.

**Headers:** Requires authentication

**Response:**
```json
{
  "id": 1,
  "name": "Front Door Sensor",
  "sensor_type": "DOOR_CONTACT",
  "location": "Main Entrance",
  "status": "ACTIVE",
  "handler_class": "ContactHandler",
  "connection_config": {},
  "metadata": {},
  "created_at": "2024-11-27T10:00:00Z",
  "updated_at": "2024-11-27T10:00:00Z"
}
```

### Update Sensor

**PATCH** `/api/sensors/{id}/`

Update sensor configuration.

**Headers:** Requires authentication

**Request Body:**
```json
{
  "location": "Side Entrance",
  "status": "INACTIVE"
}
```

### Delete Sensor

**DELETE** `/api/sensors/{id}/`

Remove a sensor.

**Headers:** Requires authentication

**Response:**
```json
{
  "message": "Sensor deleted successfully"
}
```

### Submit Sensor Reading

**POST** `/api/sensors/{id}/readings/`

Submit a new sensor reading.

**Headers:** Requires authentication

**Request Body:**
```json
{
  "value": {"state": "open"},
  "reading_type": "contact_state"
}
```

**Response:**
```json
{
  "id": 1,
  "sensor": 1,
  "value": {"state": "open"},
  "reading_type": "contact_state",
  "timestamp": "2024-11-27T10:30:00Z",
  "processed": true
}
```

**Note:** This automatically triggers threat detection and may create alerts.

### Get Reading History

**GET** `/api/sensors/{id}/reading_history/`

Get historical readings for a sensor.

**Headers:** Requires authentication

**Query Parameters:**
- `limit` - Number of readings to return (default: 100)
- `start_date` - Filter readings after this date (ISO 8601)
- `end_date` - Filter readings before this date (ISO 8601)

**Response:**
```json
[
  {
    "id": 1,
    "value": {"state": "open"},
    "reading_type": "contact_state",
    "timestamp": "2024-11-27T10:30:00Z",
    "processed": true
  }
]
```

## Alert Endpoints

### List Alerts

**GET** `/api/alerts/`

Get all alerts for the authenticated user.

**Headers:** Requires authentication

**Query Parameters:**
- `severity` - Filter by severity (INFO, LOW, MEDIUM, HIGH, CRITICAL)
- `acknowledged` - Filter by acknowledgment status (true/false)
- `sensor` - Filter by sensor ID

**Response:**
```json
[
  {
    "id": 1,
    "alert_type": "INTRUSION",
    "severity": "HIGH",
    "sensor": 1,
    "sensor_name": "Front Door Sensor",
    "description": "Door opened unexpectedly",
    "timestamp": "2024-11-27T10:30:00Z",
    "acknowledged": false,
    "acknowledged_at": null,
    "metadata": {}
  }
]
```

### Get Alert Details

**GET** `/api/alerts/{id}/`

Get details for a specific alert.

**Headers:** Requires authentication

**Response:**
```json
{
  "id": 1,
  "alert_type": "INTRUSION",
  "severity": "HIGH",
  "sensor": 1,
  "sensor_name": "Front Door Sensor",
  "description": "Door opened unexpectedly",
  "timestamp": "2024-11-27T10:30:00Z",
  "acknowledged": false,
  "acknowledged_at": null,
  "metadata": {}
}
```

### Acknowledge Alert

**PATCH** `/api/alerts/{id}/acknowledge/`

Mark an alert as acknowledged.

**Headers:** Requires authentication

**Response:**
```json
{
  "id": 1,
  "acknowledged": true,
  "acknowledged_at": "2024-11-27T10:35:00Z"
}
```

### Get Alert Statistics

**GET** `/api/alerts/statistics/`

Get alert statistics and trends.

**Headers:** Requires authentication

**Query Parameters:**
- `days` - Number of days to include (default: 7)

**Response:**
```json
{
  "total_alerts": 42,
  "by_severity": {
    "CRITICAL": 2,
    "HIGH": 8,
    "MEDIUM": 15,
    "LOW": 12,
    "INFO": 5
  },
  "by_type": {
    "INTRUSION": 10,
    "ENVIRONMENTAL": 5,
    "SYSTEM": 2
  },
  "acknowledged": 30,
  "unacknowledged": 12
}
```

## Error Responses

All endpoints return standard error responses:

**400 Bad Request:**
```json
{
  "error": "Invalid data provided",
  "details": {
    "field_name": ["Error message"]
  }
}
```

**401 Unauthorized:**
```json
{
  "detail": "Authentication credentials were not provided."
}
```

**403 Forbidden:**
```json
{
  "detail": "You do not have permission to perform this action."
}
```

**404 Not Found:**
```json
{
  "detail": "Not found."
}
```

**500 Internal Server Error:**
```json
{
  "error": "An unexpected error occurred"
}
```

## Rate Limiting

Currently no rate limiting is implemented. This will be added in future versions.

## Pagination

List endpoints support pagination:

**Query Parameters:**
- `page` - Page number (default: 1)
- `page_size` - Items per page (default: 100, max: 1000)

**Response:**
```json
{
  "count": 150,
  "next": "http://localhost:8000/api/sensors/?page=2",
  "previous": null,
  "results": [...]
}
```

## WebSocket Support (Future)

Real-time sensor data streaming via WebSockets is planned for future releases using Django Channels.

## Additional Resources

- [Quick Start Guide](../getting-started/quickstart.md)
- [Architecture Overview](../architecture/overview.md)
- [Development Guide](../contributing/development.md)
