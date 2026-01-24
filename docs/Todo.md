# Estate Sentry Development Roadmap

This document tracks all implementation tasks required to build a functional prototype of Estate Sentry with its full architecture including decentralization, the Switchboard, and Sentry Intelligence.

---

## Milestone 1: Security Hardening (Critical)

**Priority:** CRITICAL - Must be completed before any production deployment

- [ ] Hash PIN storage using Django password hashers (`make_password`/`check_password`)
- [ ] Create data migration to hash existing plaintext PINs
- [ ] Implement `TrustedDevice` model for username-only authentication
- [ ] Add device fingerprint and certificate binding for trusted devices
- [ ] Add rate limiting to authentication endpoints (5/minute for login)
- [ ] Add rate limiting to sensor reading endpoints (60/minute per sensor)
- [ ] Create `core/validators.py` with JSON Schema validators
- [ ] Add JSON Schema validation to `connection_config` and `metadata` fields
- [ ] Implement `audit` Django app with `AuditLog` model
- [ ] Add audit middleware for automatic security event capture
- [ ] Configure maximum payload sizes for JSONFields

---

## Milestone 2: Handler Registry & Device Abstraction

**Priority:** HIGH - Foundation for extensibility

- [ ] Create `sensors/registry.py` with `HandlerRegistry` class
- [ ] Implement entry point-based plugin discovery
- [ ] Add class-level metadata to `BaseSensorHandler` (`SENSOR_TYPES`, `PROTOCOLS`, `VERSION`)
- [ ] Add `get_schema()` method for reading JSON Schema
- [ ] Add `get_connection_schema()` method for config validation
- [ ] Implement `GlassBreakHandler`
- [ ] Implement `MotionHandler`
- [ ] Implement `EnvironmentalHandler` (smoke, CO, water, temperature)
- [ ] Implement `CameraStreamHandler` for Switchboard integration
- [ ] Refactor `sensors/views.py` to use `HandlerRegistry` instead of hardcoded map
- [ ] Refactor `sensors/serializers.py` to use `HandlerRegistry`
- [ ] Create `devices/protocols/base.py` with `BaseProtocolAdapter`
- [ ] Implement `MQTTProtocolAdapter`
- [ ] Implement `RESTProtocolAdapter`
- [ ] Implement `WebSocketProtocolAdapter`

---

## Milestone 3: Switchboard Foundation

**Priority:** HIGH - Central data routing for all sensor data

### Service Setup
- [ ] Create `estate-sentry-switchboard/` directory structure
- [ ] Create `src/main.py` entry point
- [ ] Create `src/config.py` configuration module
- [ ] Add `requirements.txt` with dependencies (nats-py, minio, etc.)
- [ ] Create `Dockerfile` for Switchboard service

### NATS Integration
- [ ] Set up NATS JetStream configuration
- [ ] Implement `messaging/nats_client.py` wrapper
- [ ] Create topic structure for sensor data routing:
  - `sensors.{sensor_type}.{sensor_id}.readings`
  - `sensors.{sensor_type}.{sensor_id}.status`
  - `alerts.{severity}`
  - `frames.{camera_id}`
- [ ] Implement `messaging/handlers.py` for message processing

### Media Storage
- [ ] Set up MinIO for S3-compatible object storage
- [ ] Implement `storage/minio_client.py` wrapper
- [ ] Implement `storage/frame_store.py` for camera frame storage
- [ ] Create bucket structure for media organization

### Routing
- [ ] Implement `routing/router.py` message routing logic
- [ ] Implement `routing/topics.py` topic definitions

### Edge Agent
- [ ] Create `edge/agent.py` lightweight edge agent
- [ ] Implement `edge/camera.py` for camera frame capture
- [ ] Add frame compression and encoding

### Integration
- [ ] Add Docker Compose configuration for Switchboard
- [ ] Create API endpoints for Switchboard status
- [ ] Integrate Switchboard events with Django API

---

## Milestone 4: Database Enhancements

**Priority:** MEDIUM - Performance optimization

### TimescaleDB
- [ ] Add TimescaleDB extension to Docker Compose
- [ ] Create migration to convert `sensor_readings` to hypertable
- [ ] Configure chunk time interval (1 day)
- [ ] Add compression policy (compress after 7 days)
- [ ] Add retention policy (configurable, default 1 year)

### Event Sourcing
- [ ] Create `event_log` table for node synchronization
- [ ] Add `vector_clock` field for causality tracking
- [ ] Implement event replay functionality

### Additional Tables
- [ ] Create `media_files` table for MinIO references
- [ ] Add indexes for time-range queries
- [ ] Add materialized views for statistics

---

## Milestone 5: Node Architecture

**Priority:** MEDIUM - Decentralization foundation

### Django App
- [ ] Create `nodes` Django app
- [ ] Implement `Node` model (uuid, name, zone, role, status)
- [ ] Implement `NodeHeartbeat` model (node, timestamp, metrics)
- [ ] Implement `NodeCertificate` model (node, cert_pem, fingerprint, expires)

### Discovery
- [ ] Implement mDNS discovery service using `zeroconf`
- [ ] Create manual node registration endpoint
- [ ] Implement node health check endpoint

### gRPC Communication
- [ ] Create `nodes/grpc/node.proto` protocol definitions
- [ ] Generate Python stubs from proto
- [ ] Implement `nodes/grpc/server.py` gRPC server
- [ ] Implement `nodes/grpc/client.py` gRPC client

### Synchronization
- [ ] Implement `nodes/sync.py` event synchronization service
- [ ] Add CRDT-based conflict resolution for concurrent updates
- [ ] Implement sync priority tiers (critical, important, background)

### Security
- [ ] Implement internal CA for node certificates
- [ ] Add mTLS enforcement for inter-node communication
- [ ] Implement certificate rotation

### Failover
- [ ] Implement leader election for zone primaries (Raft-based)
- [ ] Add automatic failover on primary node failure
- [ ] Configure data replication factor (default: 2)

---

## Milestone 6: Neo4j Integration

**Priority:** MEDIUM - Threat intelligence graphs

- [ ] Create `sentry/graph/neo4j_client.py` client wrapper
- [ ] Implement Django signals to sync data to Neo4j
- [ ] Create `:Sensor` nodes with properties
- [ ] Create `:Reading` nodes with temporal relationships
- [ ] Create `:Alert` nodes with correlation relationships
- [ ] Create `:Pattern` nodes for known threat patterns
- [ ] Create `:Location` nodes for spatial analysis
- [ ] Implement `GENERATED`, `FOLLOWED_BY`, `SIMILAR_TO` relationships
- [ ] Create temporal neighbor linking queries
- [ ] Implement alert correlation queries (30-minute window)
- [ ] Add Graph Data Science algorithms for pattern detection
- [ ] Create community detection queries for sensor clusters

---

## Milestone 7: Sentry Intelligence Service

**Priority:** MEDIUM - AI-powered threat analysis

### Service Setup
- [ ] Create `estate-sentry-sentry/` directory structure
- [ ] Create `src/main.py` entry point
- [ ] Add `requirements.txt` (chromadb, mcp, anthropic, etc.)
- [ ] Create `Dockerfile` for Sentry service

### Vector Store
- [ ] Implement `intelligence/vector_store.py` abstraction interface
- [ ] Implement `ChromaVectorStore` class
- [ ] Create event embedding schema
- [ ] Implement similarity search for historical patterns

### Embeddings
- [ ] Implement `intelligence/embeddings.py` event embedding pipeline
- [ ] Create text representation of security events
- [ ] Implement batch embedding for historical data

### MCP Server
- [ ] Implement `mcp/server.py` MCP server skeleton
- [ ] Create `mcp/tools/analyze.py` alert analysis tool
- [ ] Create `mcp/tools/correlate.py` event correlation tool
- [ ] Create `mcp/tools/search.py` pattern search tool
- [ ] Create `mcp/tools/report.py` report generation tool
- [ ] Expose resources via MCP protocol:
  - `sentry://alerts/recent`
  - `sentry://sensors/status`
  - `sentry://patterns/known`

### Threat Analysis
- [ ] Implement `intelligence/scoring.py` threat scoring algorithm
- [ ] Create severity escalation rules
- [ ] Implement alert correlation engine
- [ ] Add behavioral baseline detection

### Case Reports
- [ ] Create `reports/generator.py` report generator
- [ ] Create markdown report template
- [ ] Create PDF report template (optional)
- [ ] Implement timeline generation from correlated events
- [ ] Add recommendation generation based on threat score

### Integration
- [ ] Add Docker Compose configuration for Sentry
- [ ] Create API endpoints for Sentry analysis
- [ ] Integrate with Django alerts for automatic analysis

---

## Milestone 8: Frontend Updates

**Priority:** LOW - Can work with existing frontend initially

- [ ] Add Switchboard WebSocket connection to HQ
- [ ] Implement real-time sensor streaming display
- [ ] Add node status dashboard component
- [ ] Create Sentry analysis panel
- [ ] Add case report viewer component
- [ ] Implement media/frame viewer for camera feeds
- [ ] Add node management interface
- [ ] Create device registration wizard

---

## Milestone 9: API Enhancements

**Priority:** MEDIUM - Documentation and new endpoints

### OpenAPI
- [ ] Add `drf-spectacular` to requirements
- [ ] Configure `SPECTACULAR_SETTINGS` in settings.py
- [ ] Add schema and docs endpoints to urls.py
- [ ] Generate new `openapi.yaml`

### New Endpoints
- [ ] Add `/api/switchboard/status/` endpoint
- [ ] Add `/api/switchboard/topics/` endpoint
- [ ] Add `/api/nodes/` CRUD endpoints
- [ ] Add `/api/nodes/{id}/health/` endpoint
- [ ] Add `/api/nodes/discover/` mDNS discovery endpoint
- [ ] Add `/api/sentry/analyze/` analysis endpoint
- [ ] Add `/api/sentry/correlate/` correlation endpoint
- [ ] Add `/api/sentry/reports/` report generation endpoint

---

## Milestone 10: Testing & Documentation

**Priority:** ONGOING

### Testing
- [ ] Write tests for PIN hashing and authentication security
- [ ] Write tests for handler registry and discovery
- [ ] Write tests for Switchboard message routing
- [ ] Write tests for node discovery and registration
- [ ] Write tests for Sentry threat scoring
- [ ] Write integration tests for full sensor → alert pipeline
- [ ] Write integration tests for multi-node sync
- [ ] Add test fixtures for Neo4j graph data

### Documentation
- [ ] Complete architecture documentation (see docs/ updates)
- [ ] Write plugin development guide with examples
- [ ] Create deployment runbook for production
- [ ] Document backup and restore procedures
- [ ] Create troubleshooting guide
- [ ] Add API changelog

---

## Quick Reference: Priority Order

1. **CRITICAL**: Milestone 1 (Security) - Do first, blocks everything
2. **HIGH**: Milestone 2 (Handler Registry) - Foundation for devices
3. **HIGH**: Milestone 3 (Switchboard) - Central to architecture
4. **MEDIUM**: Milestone 4 (Database) - Performance optimization
5. **MEDIUM**: Milestone 5 (Nodes) - Decentralization
6. **MEDIUM**: Milestone 6 (Neo4j) - Intelligence backend
7. **MEDIUM**: Milestone 7 (Sentry) - AI analysis
8. **MEDIUM**: Milestone 9 (API) - Documentation
9. **LOW**: Milestone 8 (Frontend) - Works without changes
10. **ONGOING**: Milestone 10 (Testing) - Throughout development

---

## Dependencies Between Milestones

```
Milestone 1 (Security)
    ↓
Milestone 2 (Handlers) ──────────────────┐
    ↓                                    ↓
Milestone 3 (Switchboard) ←──── Milestone 4 (Database)
    ↓                                    ↓
Milestone 5 (Nodes) ─────────────────────┤
    ↓                                    ↓
Milestone 6 (Neo4j) ←────────────────────┘
    ↓
Milestone 7 (Sentry)
    ↓
Milestone 8 (Frontend) & Milestone 9 (API)
    ↓
Milestone 10 (Testing) - runs throughout
```

---

## Notes

- Each milestone should be completed in a separate feature branch
- Security (Milestone 1) must be merged before any production deployment
- Switchboard and Sentry are separate services with their own repositories
- Neo4j integration should use Django signals for automatic sync
- All new API endpoints must include OpenAPI documentation
- Tests should be written alongside implementation, not after
