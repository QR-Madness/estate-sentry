# Security Architecture

Security is a foundational principle of Estate Sentry, not an afterthought. This document describes the security architecture, including authentication, authorization, encryption, and secure coding practices.

## Security Principles

1. **Defense in Depth**: Multiple layers of security controls
2. **Least Privilege**: Minimal access rights for users and systems
3. **Zero Trust**: Verify everything, trust nothing by default
4. **Secure by Default**: Security enabled out of the box
5. **Transparency**: Open source for community review

## Authentication System

### Multi-Method Authentication

Estate Sentry supports multiple authentication methods to balance security and usability:

| Method | Security Level | Use Case |
|--------|---------------|----------|
| Password | High | Primary user authentication |
| PIN | Medium | Quick access, keypad entry |
| Device Certificate | High | Trusted device authentication |
| API Token | High | Service-to-service, automation |

### Password Authentication

Standard username/password authentication with Django's built-in security:

```python
# Password validation (settings.py)
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
```

**Password Storage:**
- PBKDF2 with SHA256 (Django default)
- 600,000 iterations (Django 5.0+)
- Unique salt per password

### PIN Authentication (Secure Implementation)

PINs are hashed using Django's password hashers, never stored in plaintext:

```python
# authentication/models.py
from django.contrib.auth.hashers import make_password, check_password

class User(AbstractUser):
    pin_hash = models.CharField(max_length=128, null=True, blank=True)

    def set_pin(self, raw_pin: str):
        """Hash and store the PIN securely."""
        if not raw_pin.isdigit() or len(raw_pin) != 4:
            raise ValidationError("PIN must be exactly 4 digits")
        self.pin_hash = make_password(raw_pin)

    def check_pin(self, raw_pin: str) -> bool:
        """Verify PIN against stored hash."""
        if not self.pin_hash:
            return False
        return check_password(raw_pin, self.pin_hash)
```

### Device-Bound Authentication

For trusted devices (e.g., wall-mounted panels), authentication is bound to specific hardware:

```python
# authentication/models.py
class TrustedDevice(models.Model):
    """Devices authorized for simplified authentication."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    device_id = models.CharField(max_length=255, unique=True)
    device_name = models.CharField(max_length=100)
    fingerprint = models.JSONField()  # Hardware identifiers
    certificate_hash = models.CharField(max_length=64, null=True)
    ip_whitelist = models.JSONField(default=list)
    last_used = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['device_id']),
            models.Index(fields=['user', 'is_active']),
        ]
```

**Device Fingerprint Components:**
- MAC address (primary interface)
- CPU serial number (if available)
- Disk serial number
- TPM attestation (if available)

### Token Authentication

API tokens for programmatic access:

```python
# Token generation
from rest_framework.authtoken.models import Token

token, created = Token.objects.get_or_create(user=user)

# Token usage (header)
Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
```

**Token Security:**
- 40-character hex tokens (160 bits entropy)
- Stored as SHA256 hash in database
- Single active token per user (configurable)
- Tokens can be rotated via API

## Authorization

### Permission Model

```python
# Ownership-based access control
class Sensor(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

# ViewSet enforcement
class SensorViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Sensor.objects.filter(owner=self.request.user)
```

### Role-Based Access (Future)

```python
class Role(models.TextChoices):
    ADMIN = 'admin', 'Administrator'
    OPERATOR = 'operator', 'Operator'
    VIEWER = 'viewer', 'Viewer'
    GUEST = 'guest', 'Guest'

# Permission matrix
PERMISSIONS = {
    'admin': ['*'],  # Full access
    'operator': ['sensors.view', 'sensors.edit', 'alerts.acknowledge'],
    'viewer': ['sensors.view', 'alerts.view'],
    'guest': ['alerts.view'],  # Limited to guest zone
}
```

## Rate Limiting

### Configuration

```python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '20/minute',
        'user': '1000/hour',
    }
}

# Custom throttle classes
class LoginRateThrottle(throttling.AnonRateThrottle):
    rate = '5/minute'
    scope = 'login'

class SensorReadingThrottle(throttling.UserRateThrottle):
    rate = '60/minute'
    scope = 'sensor_reading'
```

### Endpoint-Specific Limits

| Endpoint | Anonymous | Authenticated | Notes |
|----------|-----------|---------------|-------|
| `/api/auth/login/` | 5/min | N/A | Prevent brute force |
| `/api/auth/register/` | 3/hour | N/A | Prevent spam |
| `/api/sensors/` | N/A | 100/min | Standard CRUD |
| `/api/sensors/{id}/readings/` | N/A | 60/min/sensor | High frequency |
| `/api/alerts/` | N/A | 200/min | Read-heavy |

### Lockout Policy

After repeated failures:

```python
# Lockout after 5 failed attempts in 15 minutes
LOCKOUT_THRESHOLD = 5
LOCKOUT_WINDOW = timedelta(minutes=15)
LOCKOUT_DURATION = timedelta(minutes=30)
```

## Input Validation

### JSON Schema Validation

All JSONFields are validated against schemas:

```python
# core/validators.py
from jsonschema import validate, ValidationError as JsonSchemaError
from django.core.exceptions import ValidationError

class JSONSchemaValidator:
    def __init__(self, schema: dict, max_size: int = 10000):
        self.schema = schema
        self.max_size = max_size

    def __call__(self, value):
        # Size check
        if len(json.dumps(value)) > self.max_size:
            raise ValidationError(f"JSON exceeds maximum size of {self.max_size} bytes")

        # Schema validation
        try:
            validate(value, self.schema)
        except JsonSchemaError as e:
            raise ValidationError(f"Invalid JSON: {e.message}")

# Usage in models
SENSOR_READING_SCHEMA = {
    "type": "object",
    "properties": {
        "state": {"type": "string", "enum": ["open", "closed"]},
        "temperature": {"type": "number", "minimum": -50, "maximum": 150},
        "battery_level": {"type": "integer", "minimum": 0, "maximum": 100},
    },
    "additionalProperties": True,  # Allow custom fields
    "maxProperties": 50  # Prevent bloat
}

value = models.JSONField(
    validators=[JSONSchemaValidator(SENSOR_READING_SCHEMA, max_size=10000)]
)
```

### Connection Config Validation

Sensor connection configurations are strictly validated:

```python
CONNECTION_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "host": {"type": "string", "maxLength": 255, "format": "hostname"},
        "port": {"type": "integer", "minimum": 1, "maximum": 65535},
        "protocol": {"type": "string", "enum": ["mqtt", "rest", "modbus", "websocket"]},
        "username": {"type": "string", "maxLength": 100},
        # Note: passwords should be stored in secrets manager, not here
    },
    "additionalProperties": False,  # Strict - no extra fields
    "required": ["protocol"]
}
```

## Audit Logging

### Audit Log Model

```python
# audit/models.py
class AuditLog(models.Model):
    """Immutable audit trail for security events."""

    class EventType(models.TextChoices):
        # Authentication
        AUTH_LOGIN = 'AUTH_LOGIN'
        AUTH_LOGOUT = 'AUTH_LOGOUT'
        AUTH_FAILED = 'AUTH_FAILED'
        AUTH_LOCKOUT = 'AUTH_LOCKOUT'
        PASSWORD_CHANGE = 'PASSWORD_CHANGE'
        PIN_CHANGE = 'PIN_CHANGE'

        # Resources
        SENSOR_CREATE = 'SENSOR_CREATE'
        SENSOR_UPDATE = 'SENSOR_UPDATE'
        SENSOR_DELETE = 'SENSOR_DELETE'
        ALERT_CREATE = 'ALERT_CREATE'
        ALERT_ACKNOWLEDGE = 'ALERT_ACKNOWLEDGE'

        # System
        CONFIG_CHANGE = 'CONFIG_CHANGE'
        NODE_JOIN = 'NODE_JOIN'
        NODE_LEAVE = 'NODE_LEAVE'
        CERTIFICATE_ISSUE = 'CERTIFICATE_ISSUE'
        CERTIFICATE_REVOKE = 'CERTIFICATE_REVOKE'

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    event_type = models.CharField(max_length=50, choices=EventType.choices)
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    node_id = models.UUIDField(null=True)
    ip_address = models.GenericIPAddressField(null=True)
    user_agent = models.CharField(max_length=500, null=True)
    resource_type = models.CharField(max_length=100)
    resource_id = models.CharField(max_length=100, null=True)
    old_value = models.JSONField(null=True)
    new_value = models.JSONField(null=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        indexes = [
            models.Index(fields=['event_type', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['resource_type', 'resource_id']),
        ]

        # Prevent modification
        managed = True
```

### Audit Middleware

```python
# audit/middleware.py
class AuditMiddleware:
    """Automatically log security-relevant events."""

    AUDITED_PATHS = {
        '/api/auth/login/': 'AUTH_LOGIN',
        '/api/auth/logout/': 'AUTH_LOGOUT',
        '/api/sensors/': 'SENSOR_*',
        '/api/alerts/': 'ALERT_*',
    }

    def __call__(self, request):
        response = self.get_response(request)

        if self._should_audit(request):
            self._create_audit_log(request, response)

        return response
```

### Audit Retention

```python
# Audit logs retained for 7 years (compliance)
AUDIT_RETENTION_DAYS = 365 * 7  # 2555 days

# Automated cleanup (cron job)
def cleanup_old_audit_logs():
    cutoff = timezone.now() - timedelta(days=AUDIT_RETENTION_DAYS)
    # Archive to cold storage before deletion
    archive_audit_logs(cutoff)
    AuditLog.objects.filter(timestamp__lt=cutoff).delete()
```

## Inter-Node Security

### mTLS (Mutual TLS)

All inter-node communication uses mutual TLS:

```python
# nodes/certs/manager.py
class CertificateManager:
    """Manage node certificates for mTLS."""

    def __init__(self, ca_cert_path: str, ca_key_path: str):
        self.ca_cert = load_certificate(ca_cert_path)
        self.ca_key = load_private_key(ca_key_path)

    def issue_node_certificate(self, node_id: str, csr: bytes) -> bytes:
        """Issue a certificate for a node."""
        csr_obj = x509.load_pem_x509_csr(csr)

        cert = (
            x509.CertificateBuilder()
            .subject_name(csr_obj.subject)
            .issuer_name(self.ca_cert.subject)
            .public_key(csr_obj.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=90))
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName(f"{node_id}.estate-sentry.local")
                ]),
                critical=False,
            )
            .sign(self.ca_key, hashes.SHA256())
        )

        return cert.public_bytes(serialization.Encoding.PEM)
```

### Certificate Rotation

```python
# Automatic certificate rotation
CERTIFICATE_ROTATION_DAYS = 90
CERTIFICATE_RENEWAL_BUFFER = 14  # Renew 14 days before expiry

async def check_certificate_expiry():
    """Check and renew certificates approaching expiry."""
    threshold = timezone.now() + timedelta(days=CERTIFICATE_RENEWAL_BUFFER)

    expiring = NodeCertificate.objects.filter(
        expires_at__lte=threshold,
        revoked=False
    )

    for cert in expiring:
        await renew_certificate(cert.node)
```

### gRPC Security

```python
# gRPC server with mTLS
def create_grpc_server(cert_path: str, key_path: str, ca_path: str):
    credentials = grpc.ssl_server_credentials(
        [(read_file(key_path), read_file(cert_path))],
        root_certificates=read_file(ca_path),
        require_client_auth=True  # Mutual TLS
    )

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        options=[
            ('grpc.max_send_message_length', 50 * 1024 * 1024),
            ('grpc.max_receive_message_length', 50 * 1024 * 1024),
        ]
    )
    server.add_secure_port('[::]:8443', credentials)
    return server
```

## Encryption

### Data at Rest

```python
# Database encryption (PostgreSQL)
# Enable in postgresql.conf or use encrypted volumes

# MinIO encryption
# Server-side encryption with customer-provided keys (SSE-C)
MINIO_KMS_SECRET_KEY = os.environ['MINIO_KMS_SECRET_KEY']
```

### Data in Transit

| Connection | Encryption | Protocol |
|------------|------------|----------|
| API ↔ Client | TLS 1.3 | HTTPS |
| Node ↔ Node | mTLS | gRPC |
| API ↔ Database | TLS | PostgreSQL |
| API ↔ Neo4j | TLS | Bolt |
| Switchboard ↔ NATS | TLS | NATS |
| Switchboard ↔ MinIO | TLS | HTTPS |

### Secrets Management

```python
# Environment-based secrets (development)
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
DATABASE_PASSWORD = os.environ['POSTGRES_PASSWORD']

# HashiCorp Vault integration (production)
# vault/client.py
class VaultClient:
    def get_secret(self, path: str) -> dict:
        return self.client.secrets.kv.v2.read_secret_version(path)
```

## Security Headers

```python
# settings.py
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# CSP (Content Security Policy)
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")  # For Tailwind
CSP_IMG_SRC = ("'self'", "data:", "blob:")
CSP_CONNECT_SRC = ("'self'", "wss:")
```

## Security Checklist

### Before Deployment

- [ ] Change all default passwords
- [ ] Generate new `DJANGO_SECRET_KEY`
- [ ] Enable HTTPS with valid certificates
- [ ] Configure firewall rules
- [ ] Set up rate limiting
- [ ] Enable audit logging
- [ ] Review and restrict CORS origins
- [ ] Disable DEBUG mode
- [ ] Configure secure cookie settings

### Ongoing Maintenance

- [ ] Rotate API tokens periodically
- [ ] Review audit logs weekly
- [ ] Update dependencies monthly
- [ ] Rotate certificates before expiry
- [ ] Review user access quarterly
- [ ] Conduct security audits annually

## Incident Response

### Detection

```python
# Suspicious activity detection
SUSPICIOUS_PATTERNS = {
    'brute_force': {
        'threshold': 10,
        'window': timedelta(minutes=5),
        'event': 'AUTH_FAILED'
    },
    'enumeration': {
        'threshold': 50,
        'window': timedelta(minutes=1),
        'event': 'SENSOR_VIEW'
    }
}
```

### Response Procedure

1. **Detect**: Automated alerting on suspicious patterns
2. **Contain**: Automatic lockout of affected accounts/IPs
3. **Investigate**: Review audit logs and correlated events
4. **Remediate**: Rotate credentials, patch vulnerabilities
5. **Report**: Generate incident report for review

## Related Documentation

- [Decentralization](decentralization.md) - Node security and mTLS
- [API Usage](../guides/api-usage.md) - Authentication endpoints
- [Monitoring](../operations/monitoring.md) - Security monitoring
