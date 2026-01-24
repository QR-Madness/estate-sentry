# Decentralized Node Architecture

Estate Sentry is designed from the ground up for decentralized deployment across multiple nodes within an estate. This architecture provides redundancy, fault tolerance, and scalability for installations ranging from small homes to large estates with hundreds of sensors.

## Overview

The decentralized architecture follows a **Hybrid Mesh-Federation** pattern, combining the benefits of peer-to-peer mesh networking with optional centralized intelligence coordination.

```
                    +-------------------+
                    |  Federation Hub   |  (Optional Cloud/Central)
                    |  (Sentry Brain)   |
                    +--------+----------+
                             |
            +----------------+----------------+
            |                |                |
    +-------v------+  +------v-------+  +-----v--------+
    |  Zone Node   |  |  Zone Node   |  |  Zone Node   |
    |  (Primary)   |--|  (Secondary) |--|  (Guest)     |
    +-------+------+  +------+-------+  +-----+--------+
            |                |                |
    +-------v------+  +------v-------+  +-----v--------+
    | Local Sensors|  | Local Sensors|  | Local Sensors|
    +-------------+   +--------------+  +--------------+
```

## Node Types

### Zone Node

A Zone Node is a compute unit responsible for a logical area of the estate. Each zone operates autonomously and can continue functioning even when disconnected from other nodes.

**Responsibilities:**
- Collect data from local sensors
- Run the Switchboard for local sensor routing
- Process sensor readings through handlers
- Generate alerts for local events
- Synchronize with other nodes

**Hardware Examples:**
- Raspberry Pi 4/5
- Intel NUC
- Any Linux-capable device

### Federation Hub (Optional)

The Federation Hub provides centralized intelligence and coordination. It's optional - the system works without it, but adds advanced capabilities when present.

**Responsibilities:**
- Run the Sentry Intelligence service
- Aggregate data from all zones
- Perform cross-zone threat correlation
- Generate estate-wide reports
- Coordinate leader election

**Deployment Options:**
- Local server (recommended for privacy)
- Cloud instance (for remote access)
- High-powered Zone Node (dual-purpose)

## Node Discovery

Nodes discover each other through a combination of automatic and manual methods.

### mDNS Discovery (Automatic)

On the local network, nodes automatically discover each other using mDNS (Multicast DNS), also known as Bonjour or Avahi.

```python
# Example mDNS service advertisement
service_type = "_estate-sentry._tcp.local."
service_name = "zone-primary._estate-sentry._tcp.local."
properties = {
    "node_id": "uuid-here",
    "role": "zone_primary",
    "zone": "main_house",
    "version": "2.0.0"
}
```

**Discovery Process:**
1. Node starts and advertises its service via mDNS
2. Other nodes on the LAN detect the advertisement
3. Nodes exchange credentials and establish trust
4. Mesh topology is formed automatically

### Manual Registration (WAN/Remote)

For nodes not on the same LAN (guest houses, remote locations), manual registration is required.

```bash
# Register a remote node
curl -X POST https://primary-node:8000/api/nodes/register/ \
  -H "Authorization: Token <admin-token>" \
  -d '{
    "name": "guest-house",
    "address": "192.168.2.100:8000",
    "zone": "guest",
    "certificate": "<base64-cert>"
  }'
```

## Inter-Node Communication

### Protocol: gRPC with mTLS

All inter-node communication uses gRPC (Google Remote Procedure Call) secured with mutual TLS (mTLS).

**Why gRPC:**
- Efficient binary protocol (Protocol Buffers)
- Bi-directional streaming support
- Built-in load balancing
- Strong typing and code generation

**Protocol Buffer Definitions:**

```protobuf
// node.proto
syntax = "proto3";

package estate_sentry.nodes;

service NodeService {
  // Health and status
  rpc Heartbeat(HeartbeatRequest) returns (HeartbeatResponse);
  rpc GetStatus(StatusRequest) returns (StatusResponse);

  // Data synchronization
  rpc SyncEvents(stream EventBatch) returns (stream SyncAck);
  rpc RequestSync(SyncRequest) returns (stream EventBatch);

  // Alert propagation
  rpc PropagateAlert(Alert) returns (AlertAck);

  // Leader election
  rpc RequestVote(VoteRequest) returns (VoteResponse);
  rpc AppendEntries(EntriesRequest) returns (EntriesResponse);
}

message HeartbeatRequest {
  string node_id = 1;
  int64 timestamp = 2;
  NodeMetrics metrics = 3;
}

message EventBatch {
  repeated Event events = 1;
  VectorClock clock = 2;
}

message VectorClock {
  map<string, int64> clocks = 1;
}
```

### mTLS Certificate Management

Each node has a unique certificate signed by an internal Certificate Authority (CA).

**Certificate Hierarchy:**
```
Estate Sentry Root CA
├── Zone Primary Certificate
│   ├── Zone Secondary Certificate
│   └── Zone Sensor Certificate
├── Guest Zone Certificate
└── Federation Hub Certificate
```

**Certificate Lifecycle:**
1. Node generates key pair on first boot
2. Node requests certificate from CA (primary node or hub)
3. CA validates node identity and signs certificate
4. Certificate is rotated every 90 days automatically

## Data Synchronization

### Event Sourcing Model

All changes are captured as events in an append-only log, enabling reliable synchronization and replay.

```python
class EventLog(models.Model):
    """Append-only event log for synchronization."""
    node_id = models.UUIDField(index=True)
    event_type = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100)  # sensor, alert, reading
    entity_id = models.UUIDField()
    payload = models.JSONField()
    vector_clock = models.JSONField()
    timestamp = models.DateTimeField(auto_now_add=True)
    synced_to = models.JSONField(default=list)
```

### Vector Clocks

Vector clocks track causality across distributed nodes, enabling conflict detection.

```python
# Example vector clock
{
    "node-primary": 42,
    "node-secondary": 38,
    "node-guest": 15
}
```

**Conflict Resolution:**
- Concurrent events are detected via vector clock comparison
- CRDT (Conflict-free Replicated Data Types) used for automatic resolution
- Manual resolution required for true conflicts (rare)

### Sync Priority Tiers

Events are synchronized based on priority:

| Priority | Examples | Sync Window | Delivery |
|----------|----------|-------------|----------|
| Critical | Alerts, intrusion, node failures | Immediate | At-least-once |
| Important | Sensor readings, state changes | 5 seconds | Best-effort |
| Background | Config, metadata, analytics | 1 minute | Eventually |

### Sync Protocol

```
Node A                          Node B
   |                               |
   |--- SyncRequest (since: t) --->|
   |                               |
   |<-- EventBatch [e1, e2, e3] ---|
   |                               |
   |--- SyncAck [e1, e2, e3] ----->|
   |                               |
   |<-- EventBatch [e4] -----------|
   |                               |
   |--- SyncAck [e4] ------------->|
   |                               |
```

## Failover and Redundancy

### Node Failure Detection

**Heartbeat Protocol:**
- Interval: 5 seconds
- Timeout: 3 missed heartbeats (15 seconds)
- Escalation: Alert generated after confirmed failure

```python
class NodeHeartbeat(models.Model):
    node = models.ForeignKey(Node, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    cpu_usage = models.FloatField()
    memory_usage = models.FloatField()
    disk_usage = models.FloatField()
    sensor_count = models.IntegerField()
    pending_sync = models.IntegerField()
```

### Leader Election

Zone primaries are elected using a simplified Raft consensus algorithm.

**Election Process:**
1. Leader sends heartbeats to followers
2. If followers miss heartbeats, election timeout triggers
3. Candidate requests votes from other nodes
4. Majority vote wins election
5. New leader begins accepting requests

**Leader Responsibilities:**
- Coordinate data writes within zone
- Manage certificate signing for zone
- Route external requests
- Initiate data backups

### Data Replication

**Replication Factor:** Configurable (default: 2)

```python
# settings.py
ESTATE_SENTRY = {
    'REPLICATION_FACTOR': 2,  # Minimum nodes storing each piece of data
    'ALERT_REPLICATION': 'all',  # Alerts replicated to ALL nodes
    'READING_REPLICATION': 2,  # Readings replicated to N nodes
}
```

**Replication Strategy:**
- Alerts: Replicated to ALL nodes (critical data)
- Sensor readings: Replicated to N nearest nodes
- Configuration: Replicated to ALL nodes
- Media files: Stored on originating node + 1 backup

### Graceful Degradation

When nodes fail or disconnect, the system degrades gracefully:

| Scenario | Behavior |
|----------|----------|
| Single node failure | Other nodes take over, data syncs on recovery |
| Network partition | Zones operate independently, sync on reconnect |
| Hub failure | Zones continue autonomously, no central intelligence |
| All nodes except one | Single node operates fully, awaits reconnection |

## Zone Configuration

### Defining Zones

Zones are logical groupings of nodes and sensors:

```yaml
# zones.yaml
zones:
  main_house:
    description: "Primary residence"
    primary_node: node-living-room
    nodes:
      - node-living-room
      - node-kitchen
      - node-bedroom
    sensors:
      - front_door_contact
      - living_room_motion
      - kitchen_smoke

  guest_house:
    description: "Guest residence"
    primary_node: node-guest
    nodes:
      - node-guest
    sensors:
      - guest_door_contact
      - guest_motion
```

### Cross-Zone Communication

Zones communicate for:
- Alert propagation (all zones receive critical alerts)
- User authentication (centralized or replicated)
- Analytics aggregation (to hub if present)

## Network Requirements

### Minimum Bandwidth

| Traffic Type | Bandwidth | Notes |
|--------------|-----------|-------|
| Heartbeats | < 1 Kbps | Per node pair |
| Sensor sync | ~10 Kbps | Average, bursty |
| Media sync | Variable | Depends on cameras |
| Alerts | < 1 Kbps | Rare, bursty |

### Port Requirements

| Port | Protocol | Purpose |
|------|----------|---------|
| 8000 | HTTPS | REST API |
| 8443 | gRPC | Inter-node RPC |
| 5353 | UDP | mDNS discovery |
| 4222 | TCP | NATS (Switchboard) |

### Firewall Configuration

```bash
# Allow Estate Sentry traffic
ufw allow 8000/tcp comment "Estate Sentry API"
ufw allow 8443/tcp comment "Estate Sentry gRPC"
ufw allow 5353/udp comment "mDNS Discovery"
ufw allow 4222/tcp comment "NATS Switchboard"
```

## Deployment Patterns

### Single Node (Development/Small Home)

```
+-------------------+
|   Single Node     |
|  +-----------+    |
|  | API       |    |
|  | Switchboard|   |
|  | Sentry    |    |
|  +-----------+    |
|        |          |
|   [Sensors]       |
+-------------------+
```

### Multi-Node Estate

```
+-------------+     +-------------+     +-------------+
| Zone: Main  |     | Zone: Guest |     | Zone: Pool  |
|   (Primary) |<--->|  (Primary)  |<--->|  (Primary)  |
+------+------+     +------+------+     +------+------+
       |                   |                   |
+------+------+     +------+------+     +------+------+
|   Backup    |     |   Sensors   |     |   Sensors   |
|   (Standby) |     +-------------+     +-------------+
+-------------+
```

### Enterprise with Hub

```
                +------------------+
                | Federation Hub   |
                | (Cloud/On-Prem)  |
                +--------+---------+
                         |
        +----------------+----------------+
        |                |                |
+-------+------+  +------+-------+  +-----+--------+
|   Building A |  |  Building B  |  |  Building C  |
|   (Zone)     |  |   (Zone)     |  |   (Zone)     |
+--------------+  +--------------+  +--------------+
```

## Future Enhancements

- **Kubernetes Operator**: Deploy nodes via K8s
- **Mesh VPN**: Automatic WireGuard mesh between nodes
- **Edge ML**: Distributed inference across nodes
- **Geo-Redundancy**: Multi-site disaster recovery

## Related Documentation

- [Switchboard Architecture](switchboard.md) - Data routing between nodes
- [Security Architecture](security.md) - mTLS and certificate management
- [Node Deployment Guide](../guides/node-deployment.md) - Step-by-step setup
