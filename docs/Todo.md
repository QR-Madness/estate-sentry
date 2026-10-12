# Estate Sentry Development Roadmap

This document tracks all implementation tasks required to build a functional prototype of Estate Sentry with its full architecture including decentralization, the Switchboard, and Sentry Intelligence.

---

## Status

Frames move end to end: a producer writes JPEG bytes to MinIO and publishes a
reference on `frames.{camera_id}.raw`; the perception service fetches, gates on
motion, detects objects, matches them to zones, and appends to the event log.
The dashboard shows live camera tiles and a detection feed.

**Built**

- Switchboard transport (NATS + MinIO) behind swappable interfaces
- L1 motion gate, L2 object detection (RT-DETRv2, Apache-2.0 — *not* YOLOv8, which
  is AGPL-3.0 and would conflict with this project's MIT licence)
- L3 zone intersection, with `zones` and `intelligence` apps
- HQ dashboard: Django templates + htmx, MJPEG and SSE, no build step
- Live overlay: detection brackets and zone perimeters drawn client-side over the
  camera tiles, each independently toggleable
- Development producer in `../mock-estate/` on the real frame contract
- Ingest rate limiting: 60/min per sensor on the readings endpoint
- Redis as the Django cache, so DRF's rate limits hold across worker processes
- JSON Schema validation and size ceilings on every JSONField (`core/`)
- Append-only security audit log, captured by allowlisted async-capable middleware
- Ed25519 signatures on sensor readings, with timestamp and nonce replay defence
- The API container: builds from the repository root, serves ASGI on three
  workers, and ships its own static files

**Known gap**

Seven of the ten sensor types — `GLASS_BREAK`, `MOTION`, `SMOKE`, `CO`,
`WATER_LEAK`, `TEMPERATURE`, `CUSTOM` — have no entry in the handler map, so
`SensorReadingCreateSerializer.validate()` falls through and stores whatever
arrives, unchecked and unnormalised, with no threat detection. A smoke detector
reporting smoke currently raises nothing. Pinned by tests in `sensors/tests.py`
so the behaviour is visible rather than surprising. JSON Schema validation
(Milestone 1) bounds the shape; the handler registry (Milestone 2) closes it.

**Not built, deliberately**

- L4 identity, L5 action/pose, L6 correlation, L7 threat scoring
- Neo4j and ChromaDB integration
- Remaining Milestone 1 item: certificate binding for trusted devices

**Intelligence model split**

The intended shape for the analysis layer, recorded here so it is not lost: an
open-weights model (Gemma 4 or similar) does the bulk classification and
summarisation locally, with a Claude reasoning agent above it for report
generation and escalation control. Local inference keeps continuous footage
analysis on the user's own hardware — which is the point of a self-hosted
security system — while the reasoning agent is invoked only for the small number
of events that clear the threat threshold, where its judgement is worth the call.

This is L7 / Sentry Intelligence territory and nothing depends on it yet.

**Known measurements**

- RT-DETRv2 `r18vd` on CPU: ~0.42s per frame, about 2.4 fps.
- Rate limits and the cache backend. The real `SensorReadingRateThrottle`, run
  100 times against one sensor from two separate processes — which is what two
  server workers are. On LocMemCache both processes allowed 60, so a
  "60/min" limit passed 120; the Dockerfile runs three workers, so it was
  really 180. On a shared Redis the second process allowed 0 and the total was
  60. DRF counts in the Django cache, so a per-process cache multiplies every
  limit — including the auth ones — by the worker count, silently.
- End-to-end detection lag, capture to browser: ~1.0s. Was ~4s until the
  pipeline's inbound queue was shortened to 2 — a deep queue on a slow consumer
  turns directly into staleness, and the pipeline was analysing frames that had
  already left the screen. The remaining second is inference plus one cycle of
  wait, and will not improve without a faster model. Two cameras at 5 fps
  oversubscribe the pipeline roughly fourfold; the bounded queues drop oldest-first
  and the producer is never throttled.

---

## Milestone 1: Security Hardening (Critical)

**Priority:** CRITICAL - Must be completed before any production deployment

- [x] Hash PIN storage using Django password hashers (`make_password`/`check_password`)
- [x] Create data migration to hash existing plaintext PINs
- [x] Implement `TrustedDevice` model for username-only authentication
- [ ] Add device fingerprint and certificate binding for trusted devices —
      the token is the credential today; binding it to a client certificate
      would stop a copied token working from somewhere else.
      *Overlaps Milestone 5, which builds an internal CA for node certificates.
      Client-certificate binding done now would need a CA of its own plus TLS
      termination that passes the certificate through — then be built again. A
      route with no CA at all is proof of possession: the device holds an
      Ed25519 key and signs its requests, the pattern sensor readings already
      use. Choose between them before building either.*
- [x] Add rate limiting to authentication endpoints, plus a per-account lockout
- [x] Add rate limiting to sensor reading endpoints (60/minute per sensor)
- [x] Add `public_key` to `Sensor` and verify reading signatures — rescued from
      issue #4, which predates the Django rewrite. Ed25519, so only public keys
      are stored and a leaked database cannot forge a reading. Enrolled out of
      band with `manage.py enroll_sensor_key`; `signed_at` and a burned nonce
      stop a captured reading being replayed
- [x] Create `core/validators.py` with JSON Schema validators
- [x] Add JSON Schema validation to `connection_config` and `metadata` fields
- [x] Implement `audit` Django app with `AuditLog` model
- [x] Add audit middleware for automatic security event capture
- [x] Configure maximum payload sizes for JSONFields

---

## Milestone 2: Handler Registry & Device Abstraction

**Priority:** HIGH - Foundation for extensibility

**Scoped 2026-10-12.** The registry and the missing handlers come first: seven of
ten sensor types have no handler, so their readings are stored unnormalised and
raise nothing — a smoke detector reporting smoke raises no alert. Two parts are
deferred out of this milestone. The protocol adapters (MQTT, REST, WebSocket)
are the transport question the sensor kit has to answer, and built ahead of it
they would likely be the wrong abstraction. `CameraStreamHandler` belongs with
the Switchboard: a camera's frames reach the system over the frame contract, not
as readings.

- [ ] Create `sensors/registry.py` with `HandlerRegistry` class
- [ ] Implement entry point-based plugin discovery
- [ ] Add class-level metadata to `BaseSensorHandler` (`SENSOR_TYPES`, `PROTOCOLS`, `VERSION`)
- [ ] Add `get_schema()` method for reading JSON Schema
- [ ] Add `get_connection_schema()` method for config validation
- [ ] Implement `GlassBreakHandler`
- [ ] Implement `MotionHandler`
- [ ] Implement `EnvironmentalHandler` (smoke, CO, water, temperature)
- [ ] Implement `CameraStreamHandler` for Switchboard integration — *deferred to Milestone 3*
- [ ] Refactor `sensors/views.py` to use `HandlerRegistry` instead of hardcoded map
- [ ] Refactor `sensors/serializers.py` to use `HandlerRegistry`
- [ ] Create `devices/protocols/base.py` with `BaseProtocolAdapter` — *deferred to the sensor kit*
- [ ] Implement `MQTTProtocolAdapter` — *deferred to the sensor kit*
- [ ] Implement `RESTProtocolAdapter` — *deferred to the sensor kit*
- [ ] Implement `WebSocketProtocolAdapter` — *deferred to the sensor kit*

---

## Milestone 3: Switchboard

**Priority:** HIGH - Central data routing for all sensor data

**Reconciled 2026-10-12.** This milestone first described a separate
`estate-sentry-switchboard/` service. It was never built that way, and
deliberately: at the reboot the transport became a small library inside
`estate-sentry-perception/perception/transport/`, behind two protocols —
`FrameStore` and `EventBus` — with NATS and MinIO implementations and in-memory
doubles for tests. NATS and MinIO *are* the switchboard; the code is a thin
client layer that the pipeline and the API both import, so the frame contract
cannot drift between them. Read with the old checklist, everything below looked
unbuilt. The superseded items are kept at the end, struck through.

### Built — frames, end to end
- [x] NATS with JetStream in Compose (`--jetstream`; `task switchboard:up`)
- [x] MinIO in Compose; buckets via `task minio:create-buckets`, and the frame
      store creates its own on demand (`ensure_bucket`)
- [x] Event bus — `NatsEventBus` (`perception/transport/nats_bus.py`)
- [x] Frame store — `MinioFrameStore` (`perception/transport/minio_store.py`)
- [x] Frame contract — `FrameRef`, `frame_key()`, `frame_subject()`, on
      `frames.{camera_id}.raw` (`perception/transport/protocols.py`)
- [x] In-memory doubles for both, so the pipeline's tests need no infrastructure
- [x] Consumers — the perception service, which posts zone events to the API,
      and the HQ dashboard's live MJPEG and SSE

### Remaining
- [ ] **Sensor readings over NATS** (`sensors.{type}.{id}.readings`). Today they
      go over REST to `/api/sensors/{id}/readings/`. Moving them would let
      JetStream absorb outages for devices on the far side of the internet.
      *Conflicts with signing as built:* a signed reading is refused once
      `signed_at` is more than five minutes old, so a device replaying a buffered
      backlog would be rejected. Design that before readings move to a buffered
      transport.
- [ ] Sensor status subjects (`sensors.{type}.{id}.status`)
- [ ] Alert fan-out (`alerts.{severity}`)
- [ ] Switchboard status endpoints in the API — listed under Milestone 9
- [ ] **Edge agent — now a "sensor kit"**: one lightweight daemon per device
      hosting several sensors, which would replace `mock-estate` as the
      producer. *Not yet specified.* First target is the Raspberry Pi 4B test
      device, whose USB camera emits MJPEG natively (up to 960x720, 15 fps), so
      capture needs no encode step. Milestone 2's protocol adapters belong to
      this design rather than ahead of it.

### Superseded by the library design
- ~~Create `estate-sentry-switchboard/` directory structure~~
- ~~Create `src/main.py`, `src/config.py`, `requirements.txt` and a `Dockerfile`
  for a Switchboard service~~
- ~~`messaging/nats_client.py`, `storage/minio_client.py`,
  `storage/frame_store.py`~~ — built as the transport package above
- ~~`routing/router.py`, `routing/topics.py`~~ — NATS subjects do the routing;
  the contract lives in `protocols.py`
- ~~Add frame compression and encoding~~ — moot for MJPEG cameras, which
  compress in hardware; revisit only for a camera limited to YUYV

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
- [x] Write tests for PIN hashing and authentication security
- [ ] Write tests for handler registry and discovery
- [ ] Write tests for Switchboard message routing
- [ ] Write tests for node discovery and registration
- [ ] Write tests for Sentry threat scoring
- [x] Write integration tests for full sensor → alert pipeline
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
