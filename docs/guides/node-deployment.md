# Node Deployment Guide

This guide covers deploying Estate Sentry in single-node and multi-node configurations.

## Prerequisites

- Linux-based system (Ubuntu 22.04+ recommended)
- Docker and Docker Compose
- 2GB RAM minimum (4GB recommended)
- Network connectivity between nodes (for multi-node)

## Single-Node Deployment

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/estate-sentry.git
cd estate-sentry

# Copy environment template
cp .env.example .env

# Edit configuration
nano .env

# Build and start services
task docker:build
task docker:up

# Run database migrations
task db:migrate:docker

# Create admin user
task api:superuser
```

### Verify Installation

```bash
# Check running services
task docker:ps

# View logs
task docker:logs

# Test API
curl http://localhost:8000/api/sensors/
```

### Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| API | http://localhost:8000 | Token auth |
| Dashboard | http://localhost:8000/hq/ | Login required |
| Neo4j Browser | http://localhost:7474 | neo4j / changeme |
| MinIO Console | http://localhost:9001 | estate-sentry / changeme |

## Multi-Node Deployment

### Network Planning

Before deploying multiple nodes, plan your network:

```
Zone: Main House
├── Node: living-room (Primary)
│   ├── IP: 192.168.1.10
│   └── Sensors: front_door, motion_lr, camera_front
│
├── Node: kitchen (Secondary)
│   ├── IP: 192.168.1.11
│   └── Sensors: back_door, smoke_kitchen

Zone: Guest House
└── Node: guest (Primary)
    ├── IP: 192.168.2.10
    └── Sensors: guest_door, guest_motion
```

### Node Configuration

Each node needs a unique configuration:

```bash
# .env on each node
NODE_ID=unique-uuid-here
NODE_NAME=living-room
NODE_ZONE=main-house
NODE_ROLE=primary  # or 'secondary'

# Network
NODE_HOST=192.168.1.10
NODE_API_PORT=8000
NODE_GRPC_PORT=8443

# Cluster
CLUSTER_DISCOVERY=mdns  # or 'manual'
CLUSTER_PEERS=192.168.1.11:8443,192.168.2.10:8443  # for manual
```

### Primary Node Setup

The first node becomes the zone primary:

```bash
# On primary node (e.g., living-room)
cd estate-sentry

# Generate node identity
python manage.py generate_node_identity

# Start services
task docker:up

# Initialize as primary
python manage.py init_primary --zone main-house
```

This generates:

- Node UUID
- Certificate signing request
- Self-signed CA (for zone)

### Secondary Node Setup

Additional nodes join via discovery or manual registration:

```bash
# On secondary node (e.g., kitchen)
cd estate-sentry

# Generate node identity
python manage.py generate_node_identity

# Join existing zone
python manage.py join_zone --primary 192.168.1.10
```

The join process:

1. Connects to primary node
2. Submits certificate signing request
3. Receives signed certificate
4. Starts data synchronization

### Manual Node Registration

For nodes on different networks:

```bash
# On the primary node
curl -X POST http://localhost:8000/api/nodes/register/ \
  -H "Authorization: Token <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "guest-house",
    "address": "192.168.2.10:8443",
    "zone": "guest",
    "public_key": "<base64-encoded-key>"
  }'
```

### Verify Multi-Node Setup

```bash
# Check node status on any node
curl http://localhost:8000/api/nodes/

# Expected response
{
  "nodes": [
    {
      "id": "uuid-1",
      "name": "living-room",
      "zone": "main-house",
      "role": "primary",
      "status": "online",
      "last_heartbeat": "2025-01-23T10:00:00Z"
    },
    {
      "id": "uuid-2",
      "name": "kitchen",
      "zone": "main-house",
      "role": "secondary",
      "status": "online",
      "last_heartbeat": "2025-01-23T10:00:01Z"
    }
  ]
}
```

## Certificate Management

### View Certificates

```bash
# List node certificates
python manage.py list_certificates

# Output
NODE                ZONE        EXPIRES         STATUS
living-room         main-house  2025-04-23      valid
kitchen             main-house  2025-04-23      valid
guest-house         guest       2025-04-20      expiring_soon
```

### Rotate Certificates

Certificates auto-rotate 14 days before expiry. To manually rotate:

```bash
# Rotate specific node
python manage.py rotate_certificate --node guest-house

# Rotate all expiring
python manage.py rotate_certificates --expiring
```

### Revoke Node

Remove a compromised or decommissioned node:

```bash
# Revoke node certificate
python manage.py revoke_node --node kitchen --reason decommissioned

# This will:
# 1. Revoke the certificate
# 2. Remove from cluster
# 3. Prevent reconnection
```

## Zone Configuration

### Create Zone File

```yaml
# zones.yaml
zones:
  main-house:
    description: "Primary residence"
    primary_node: living-room
    failover_priority:
      - kitchen
      - bedroom
    settings:
      replication_factor: 2
      sync_interval_seconds: 5

  guest-house:
    description: "Guest cottage"
    primary_node: guest
    standalone: true  # No failover
    settings:
      replication_factor: 1
```

### Apply Zone Configuration

```bash
# Apply zone config
python manage.py apply_zones --config zones.yaml

# Verify
python manage.py show_zones
```

## Firewall Configuration

### Required Ports

| Port | Protocol | Purpose | Open To |
|------|----------|---------|---------|
| 8000 | TCP | REST API | Clients, other nodes |
| 8443 | TCP | gRPC | Other nodes only |
| 5353 | UDP | mDNS | LAN only |
| 4222 | TCP | NATS | Other nodes only |
| 7474 | TCP | Neo4j HTTP | Admin only |
| 7687 | TCP | Neo4j Bolt | Local only |

### UFW Rules

```bash
# API access (from anywhere)
ufw allow 8000/tcp comment "Estate Sentry API"

# gRPC (from cluster only)
ufw allow from 192.168.1.0/24 to any port 8443 comment "ES gRPC cluster"
ufw allow from 192.168.2.0/24 to any port 8443 comment "ES gRPC guest zone"

# mDNS (LAN only)
ufw allow 5353/udp comment "mDNS discovery"

# NATS (cluster only)
ufw allow from 192.168.1.0/24 to any port 4222 comment "NATS cluster"
```

## Backup and Recovery

### Backup Primary Node

```bash
# Full backup (database + certificates + config)
task backup:full

# Backup location: ./data/backups/backup_TIMESTAMP.tar.gz
```

### Restore to New Hardware

```bash
# On new hardware
git clone https://github.com/yourusername/estate-sentry.git
cd estate-sentry

# Restore backup
task backup:restore --file backup_2025-01-23.tar.gz

# Reconfigure network (if IP changed)
python manage.py update_node_address --address 192.168.1.10

# Restart services
task docker:restart
```

### Promote Secondary to Primary

If primary fails permanently:

```bash
# On secondary node
python manage.py promote_to_primary

# This will:
# 1. Assume primary role
# 2. Update cluster configuration
# 3. Notify other nodes
```

## Monitoring Nodes

### Health Checks

```bash
# Check all nodes
curl http://localhost:8000/api/nodes/health/

# Response
{
  "cluster_healthy": true,
  "nodes": {
    "living-room": {
      "status": "healthy",
      "cpu": 15.2,
      "memory": 42.1,
      "disk": 23.5,
      "sensors": 5,
      "pending_sync": 0
    },
    "kitchen": {
      "status": "healthy",
      "cpu": 8.1,
      "memory": 38.4,
      "disk": 21.2,
      "sensors": 2,
      "pending_sync": 3
    }
  }
}
```

### View Sync Status

```bash
# Check synchronization status
curl http://localhost:8000/api/nodes/sync/status/

# Response
{
  "last_sync": "2025-01-23T10:00:00Z",
  "pending_events": 0,
  "sync_lag_seconds": 0,
  "peers": {
    "kitchen": {"synced": true, "lag": 0},
    "guest": {"synced": true, "lag": 2}
  }
}
```

## Troubleshooting

### Node Not Discovering Peers

```bash
# Check mDNS
avahi-browse -a | grep estate-sentry

# If no results, check avahi-daemon
systemctl status avahi-daemon

# Verify multicast is enabled
ip link show | grep MULTICAST
```

### Certificate Errors

```bash
# Verify certificate chain
openssl verify -CAfile ca.pem node.pem

# Check certificate details
openssl x509 -in node.pem -text -noout

# Common issues:
# - Clock skew between nodes
# - Expired certificates
# - Wrong CA certificate
```

### Sync Issues

```bash
# Force full sync
python manage.py force_sync --node kitchen

# Check event log
python manage.py show_event_log --limit 100

# Clear stuck events
python manage.py clear_sync_queue --node kitchen
```

### Node Offline

```bash
# Check node status
curl http://localhost:8000/api/nodes/living-room/

# If node is unreachable:
# 1. Check network connectivity
ping 192.168.1.10

# 2. Check services on remote node
ssh user@192.168.1.10 "task docker:ps"

# 3. View remote logs
ssh user@192.168.1.10 "task docker:logs"
```

## Production Checklist

- [ ] Change all default passwords
- [ ] Generate unique NODE_ID for each node
- [ ] Configure firewall rules
- [ ] Set up SSL/TLS certificates
- [ ] Configure backup schedule
- [ ] Set up monitoring alerts
- [ ] Document network topology
- [ ] Test failover procedure
- [ ] Configure log rotation
- [ ] Set up remote access (VPN)

## Related Documentation

- [Decentralization Architecture](../architecture/decentralization.md)
- [Security Architecture](../architecture/security.md)
- [Monitoring Guide](../operations/monitoring.md)
