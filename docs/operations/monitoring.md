# Monitoring Guide

This guide covers monitoring Estate Sentry deployments for health, performance, and security.

## Health Endpoints

### API Health

```bash
# Basic health check
curl http://localhost:8000/api/health/

# Response
{
  "status": "healthy",
  "version": "2.0.0",
  "timestamp": "2025-01-23T10:00:00Z"
}
```

### Detailed Health

```bash
curl http://localhost:8000/api/health/detailed/

# Response
{
  "status": "healthy",
  "components": {
    "database": {"status": "healthy", "latency_ms": 2},
    "neo4j": {"status": "healthy", "latency_ms": 5},
    "nats": {"status": "healthy", "connected": true},
    "minio": {"status": "healthy", "buckets": 4}
  },
  "metrics": {
    "sensors_active": 12,
    "alerts_unacked": 3,
    "readings_today": 15420
  }
}
```

### Node Health (Multi-node)

```bash
curl http://localhost:8000/api/nodes/health/

# Response
{
  "cluster_healthy": true,
  "quorum": true,
  "nodes": {
    "node-1": {
      "status": "healthy",
      "role": "primary",
      "uptime_hours": 168,
      "cpu_percent": 12.5,
      "memory_percent": 45.2,
      "disk_percent": 23.1
    }
  }
}
```

## Metrics Collection

### Prometheus Metrics

Estate Sentry exposes Prometheus-compatible metrics:

```bash
curl http://localhost:8000/metrics/
```

**Available Metrics:**

| Metric | Type | Description |
|--------|------|-------------|
| `estate_sentry_sensors_total` | Gauge | Total registered sensors |
| `estate_sentry_sensors_active` | Gauge | Currently active sensors |
| `estate_sentry_readings_total` | Counter | Total sensor readings |
| `estate_sentry_readings_rate` | Gauge | Readings per minute |
| `estate_sentry_alerts_total` | Counter | Total alerts generated |
| `estate_sentry_alerts_unacked` | Gauge | Unacknowledged alerts |
| `estate_sentry_api_requests_total` | Counter | API requests by endpoint |
| `estate_sentry_api_latency_seconds` | Histogram | API response latency |

### Prometheus Configuration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'estate-sentry'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: /metrics/
    scrape_interval: 15s

  # Multi-node
  - job_name: 'estate-sentry-nodes'
    static_configs:
      - targets:
        - 'node-1:8000'
        - 'node-2:8000'
        - 'node-3:8000'
```

### Grafana Dashboard

Import the Estate Sentry dashboard:

```bash
# Download dashboard
curl -o grafana-dashboard.json \
  https://raw.githubusercontent.com/estate-sentry/dashboards/main/grafana.json

# Import via Grafana API
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @grafana-dashboard.json
```

## Log Monitoring

### Log Locations

| Service | Log Location |
|---------|--------------|
| API | `docker logs estate-sentry-api` |
| PostgreSQL | `docker logs estate-sentry-postgres` |
| Neo4j | `docker logs estate-sentry-neo4j` |
| NATS | `docker logs estate-sentry-nats` |
| Switchboard | `docker logs estate-sentry-switchboard` |

### Log Aggregation

#### Loki Configuration

```yaml
# loki-config.yml
auth_enabled: false
server:
  http_listen_port: 3100

ingester:
  lifecycler:
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1

schema_config:
  configs:
    - from: 2025-01-01
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

storage_config:
  boltdb_shipper:
    active_index_directory: /loki/index
    cache_location: /loki/cache
  filesystem:
    directory: /loki/chunks
```

#### Promtail for Docker

```yaml
# promtail-config.yml
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: estate-sentry
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
    relabel_configs:
      - source_labels: ['__meta_docker_container_name']
        regex: '/estate-sentry-(.*)'
        target_label: 'service'
        replacement: '$1'
```

### Log Queries

#### Find Errors

```logql
{service="api"} |= "ERROR"
```

#### Authentication Failures

```logql
{service="api"} |~ "AUTH_FAILED|Invalid credentials"
```

#### Slow Queries

```logql
{service="api"} | json | latency_ms > 1000
```

## Alerting

### Alert Rules

```yaml
# alert-rules.yml
groups:
  - name: estate-sentry
    rules:
      # Service down
      - alert: ServiceDown
        expr: up{job="estate-sentry"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Estate Sentry service is down"

      # High error rate
      - alert: HighErrorRate
        expr: |
          rate(estate_sentry_api_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High API error rate"

      # Sensor offline
      - alert: SensorOffline
        expr: |
          estate_sentry_sensor_last_seen_seconds > 300
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Sensor {{ $labels.sensor_name }} offline"

      # Unacknowledged critical alerts
      - alert: CriticalAlertUnacked
        expr: |
          estate_sentry_alerts_unacked{severity="critical"} > 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Critical security alert unacknowledged"

      # Node unhealthy
      - alert: NodeUnhealthy
        expr: |
          estate_sentry_node_healthy == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Node {{ $labels.node_name }} is unhealthy"

      # High memory usage
      - alert: HighMemoryUsage
        expr: |
          estate_sentry_node_memory_percent > 90
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage on {{ $labels.node_name }}"
```

### Notification Channels

#### Slack Integration

```yaml
# alertmanager.yml
route:
  receiver: 'slack-notifications'
  routes:
    - match:
        severity: critical
      receiver: 'slack-critical'

receivers:
  - name: 'slack-notifications'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/xxx'
        channel: '#estate-sentry-alerts'

  - name: 'slack-critical'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/xxx'
        channel: '#estate-sentry-critical'
```

#### Email Integration

```yaml
receivers:
  - name: 'email-alerts'
    email_configs:
      - to: 'security@example.com'
        from: 'estate-sentry@example.com'
        smarthost: 'smtp.example.com:587'
        auth_username: 'estate-sentry'
        auth_password: 'password'
```

## Dashboard Metrics

### Key Dashboards

#### System Overview

- Total sensors and status distribution
- Alert volume (24h, 7d trends)
- API request rate and latency
- Resource utilization

#### Security Dashboard

- Real-time alert feed
- Threat score trends
- Sensor trigger heatmap
- Unacknowledged alert count

#### Node Dashboard (Multi-node)

- Node status matrix
- Sync lag between nodes
- Leader/follower status
- Network health

### Example Dashboard Panels

#### Sensor Status (Grafana)

```json
{
  "title": "Sensor Status",
  "type": "stat",
  "targets": [
    {
      "expr": "estate_sentry_sensors_active",
      "legendFormat": "Active"
    },
    {
      "expr": "estate_sentry_sensors_total - estate_sentry_sensors_active",
      "legendFormat": "Inactive"
    }
  ]
}
```

#### Alert Rate (Grafana)

```json
{
  "title": "Alert Rate",
  "type": "graph",
  "targets": [
    {
      "expr": "rate(estate_sentry_alerts_total[5m]) * 60",
      "legendFormat": "Alerts/min"
    }
  ]
}
```

## Performance Monitoring

### Database Performance

```bash
# PostgreSQL slow queries
docker exec estate-sentry-postgres psql -U estate_sentry -c "
SELECT query, calls, mean_time, total_time
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 10;
"

# Neo4j query stats
curl -X POST http://localhost:7474/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"CALL db.stats.collect()"}]}'
```

### API Performance

```python
# Enable slow query logging
# settings.py
LOGGING = {
    'handlers': {
        'slow_queries': {
            'class': 'logging.FileHandler',
            'filename': '/var/log/estate-sentry/slow_queries.log',
        },
    },
    'loggers': {
        'django.db.backends': {
            'handlers': ['slow_queries'],
            'level': 'DEBUG',
        },
    },
}

SLOW_QUERY_THRESHOLD_MS = 100
```

### Switchboard Performance

```bash
# NATS metrics
curl http://localhost:8222/varz

# Message rates
curl http://localhost:8222/jsz?streams=true
```

## Troubleshooting Runbook

### High CPU Usage

1. Check which service:
   ```bash
   docker stats
   ```

2. For API:
   ```bash
   # Check active requests
   curl http://localhost:8000/api/debug/requests/
   ```

3. For Neo4j:
   ```bash
   # Check running queries
   CALL dbms.listQueries()
   ```

### High Memory Usage

1. Check memory by service:
   ```bash
   docker stats --no-stream
   ```

2. For PostgreSQL:
   ```bash
   # Check connections
   SELECT count(*) FROM pg_stat_activity;
   ```

3. Restart if needed:
   ```bash
   task docker:restart:api
   ```

### Sync Lag

1. Check sync status:
   ```bash
   curl http://localhost:8000/api/nodes/sync/status/
   ```

2. Check pending events:
   ```bash
   python manage.py show_event_log --pending
   ```

3. Force sync:
   ```bash
   python manage.py force_sync --all
   ```

## Backup Monitoring

### Backup Status

```bash
# Check last backup
ls -la data/backups/

# Verify backup integrity
task backup:verify --latest
```

### Backup Alerts

```yaml
# Alert if backup is stale
- alert: BackupStale
  expr: |
    time() - estate_sentry_backup_last_success_timestamp > 86400
  for: 1h
  labels:
    severity: warning
  annotations:
    summary: "Backup is more than 24 hours old"
```

## Related Documentation

- [Node Deployment](../guides/node-deployment.md)
- [Security Architecture](../architecture/security.md)
- [Switchboard Architecture](../architecture/switchboard.md)
