# Sentry Intelligence Specification

This document defines the perception and analysis architecture for Estate Sentry's intelligence layer, and specifies how it integrates with the existing stack: Django REST API, Switchboard (NATS + MinIO), PostgreSQL/TimescaleDB, Neo4j, ChromaDB, and the HQ dashboard.

---

## Design Principles

- **Zone-First**: Zones are the top-level organizing entity. Cameras and sensors are bound to zones, and all analysis is zone-scoped.
- **Layered Perception**: Each processing layer filters and enriches data before passing it upward. Early exit at any layer avoids unnecessary compute.
- **Log Everything**: Every detection in every zone is logged regardless of classification outcome.
- **Human-in-the-Loop**: Low-confidence identity matches and high-severity threat assessments are routed to a human review queue.
- **Privacy by Consent**: Face embeddings and biometric data are stored only after explicit user consent through a first-run disclaimer flow.

---

## System Architecture

### Where Perception Fits

The perception pipeline is a new service (`estate-sentry-perception`) that sits between the Switchboard and the Django API. It consumes camera frames from NATS, runs inference, and writes results back to the API and databases.

```
+----------------------------------------------------------------------+
|                          ESTATE SENTRY                                |
|                                                                       |
|  +------------------+    +------------------+    +------------------+ |
|  |  estate-sentry-  |    |   Switchboard    |    | estate-sentry-   | |
|  |  api (Django)    |<-->|   (NATS+MinIO)   |<-->| perception       | |
|  +--------+---------+    +--------+---------+    +--------+---------+ |
|           |                       |                       |           |
|  +--------v---------+    +--------v---------+    +--------v---------+ |
|  | PostgreSQL       |    |  MinIO           |    | ChromaDB         | |
|  | (TimescaleDB)    |    |  (Frames/Media)  |    | (Embeddings)     | |
|  +------------------+    +------------------+    +------------------+ |
|           |                                               |           |
|  +--------v---------+                            +--------v---------+ |
|  | Neo4j            |<-------------------------->| Sentry Intel     | |
|  | (Graph/Threats)  |                            | (MCP Server)     | |
|  +------------------+                            +------------------+ |
+----------------------------------------------------------------------+
         |                                                  |
+--------v---------+                              +---------v--------+
|  estate-sentry-  |                              |  Claude / LLM    |
|  hq (Django)     |                              |  (Analysis)      |
+------------------+                              +------------------+
```

### Service Inventory

| Service | Technology | Role in Intelligence |
|---------|-----------|----------------------|
| `estate-sentry-api` | Django 5 + DRF | Zone CRUD, identity profiles, alerts, review queue API |
| `estate-sentry-api/hq` | Django templates + htmx | Zone editor, identity review UI, perception dashboard |
| `estate-sentry-perception` | Python (async) | L1-L7 perception pipeline, frame processing |
| Switchboard (NATS) | NATS 2.10 JetStream | Frame notifications, detection events, alert routing |
| Switchboard (MinIO) | MinIO | Frame storage, evidence snapshots |
| PostgreSQL | TimescaleDB 16 | Zone events, tracks, identity metadata, alerts |
| Neo4j | Neo4j 5 | Zone adjacency graph, entity relationship graph, threat patterns |
| ChromaDB | ChromaDB | Face embeddings, appearance embeddings, threat pattern vectors |
| Sentry Intelligence | Python MCP Server | LLM-powered threat analysis, case reports |

### Docker Compose Additions

The perception service extends the existing `docker-compose.yml`:

```yaml
services:
  # ... existing services (api, hq, postgres, neo4j, nats, minio, chromadb)

  perception:
    build: ./estate-sentry-perception
    environment:
      NATS_URL: nats://nats:4222
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: estate-sentry
      MINIO_SECRET_KEY: ${MINIO_SECRET_KEY}
      API_URL: http://api:8000
      API_TOKEN: ${PERCEPTION_API_TOKEN}
      CHROMADB_URL: http://chromadb:8001
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: ${NEO4J_PASSWORD}
      DEVICE: auto                    # cpu, cuda, auto
    volumes:
      - ./data/perception/models:/app/models  # ML model cache
    depends_on:
      - nats
      - minio
      - chromadb
      - api
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]     # Optional GPU passthrough
```

---

## First-Run Consent Flow

On first setup, the system presents a mandatory consent prompt:

- The system is a **demonstrational prototype** and is not licensed for public intelligence gathering.
- The user confirms they have legal permission to deploy camera-based monitoring at their location.
- Consent timestamp and terms version are stored in the database.
- The system will not process camera feeds or store biometric data until consent is recorded.

### Django Implementation

Consent is stored via the existing `authentication` app:

```python
# authentication/models.py (extension)
class IntelligenceConsent(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    consented = models.BooleanField(default=False)
    disclaimer_version = models.CharField(max_length=20)
    consented_at = models.DateTimeField(null=True)
    ip_address = models.GenericIPAddressField(null=True)
```

The perception service checks consent status via the API before processing any camera data.

---

## Zone Model

Zones are the primary organizational unit. All detection, analysis, and alerting is zone-scoped.

### Django Models (`zones` App)

A new `zones` Django app extends the existing `sensors` and `alerts` apps:

```python
# zones/models.py
class Zone(models.Model):
    class ZoneType(models.TextChoices):
        ENTRY = 'ENTRY'
        HALLWAY = 'HALLWAY'
        PERIMETER = 'PERIMETER'
        RESTRICTED = 'RESTRICTED'
        COMMON = 'COMMON'

    class TrafficLevel(models.TextChoices):
        HIGH = 'HIGH'
        MEDIUM = 'MEDIUM'
        LOW = 'LOW'
        NONE = 'NONE'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    zone_type = models.CharField(max_length=20, choices=ZoneType.choices)
    expected_traffic = models.CharField(max_length=10, choices=TrafficLevel.choices)
    active_hours_start = models.TimeField(null=True)
    active_hours_end = models.TimeField(null=True)
    known_regulars = models.JSONField(default=list)       # ["household", "delivery"]
    context = models.TextField(blank=True)                 # Free-text zone description
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ZonePerimeter(models.Model):
    """Pixel-space polygon defining zone boundaries within a camera view."""
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='perimeters')
    camera = models.ForeignKey('sensors.Sensor', on_delete=models.CASCADE,
                               limit_choices_to={'sensor_type': 'CAMERA'})
    polygon = models.JSONField()  # [[x1,y1], [x2,y2], ...] normalized 0-1


class ZoneAdjacency(models.Model):
    """Directed edge in the zone adjacency graph."""
    from_zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='exits')
    to_zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='entrances')
    learned_transit_seconds = models.FloatField(null=True)
    transit_sample_count = models.IntegerField(default=0)
    manually_configured = models.BooleanField(default=False)

    class Meta:
        unique_together = ('from_zone', 'to_zone')


class ZoneRule(models.Model):
    """Alert policy for a zone."""
    class RuleType(models.TextChoices):
        ALERT_UNKNOWN_PERSON = 'ALERT_UNKNOWN_PERSON'
        ALERT_AFTER_HOURS = 'ALERT_AFTER_HOURS'
        ALERT_DWELL_TIME = 'ALERT_DWELL_TIME'
        ALERT_ZONE_TRANSITION = 'ALERT_ZONE_TRANSITION'
        SUPPRESS_WINDOW = 'SUPPRESS_WINDOW'
        CUSTOM = 'CUSTOM'

    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='rules')
    rule_type = models.CharField(max_length=30, choices=RuleType.choices)
    enabled = models.BooleanField(default=True)
    parameters = models.JSONField(default=dict)  # Rule-specific config
    # e.g. {"dwell_threshold_seconds": 30} or {"target_zone_id": "uuid"}
```

### Relationship to Existing Models

The `Sensor` model (existing) gains a zone foreign key:

```python
# sensors/models.py (extension)
class Sensor(models.Model):
    # ... existing fields ...
    zone = models.ForeignKey('zones.Zone', null=True, blank=True,
                             on_delete=models.SET_NULL, related_name='sensors')
```

The `Alert` model (existing) gains a zone foreign key:

```python
# alerts/models.py (extension)
class Alert(models.Model):
    # ... existing fields ...
    zone = models.ForeignKey('zones.Zone', null=True, blank=True,
                             on_delete=models.SET_NULL, related_name='alerts')
```

### Zone Context Document

Each zone has both structured and free-text context:

**Structured fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `zone_type` | enum | entry, hallway, perimeter, restricted, common |
| `expected_traffic` | enum | high, medium, low, none |
| `active_hours` | time range | When the zone is normally occupied |
| `known_regulars` | list | Categories of expected visitors |

**Free-text context:**

The `context` text field is where the user describes the zone in natural language. This context is fed to the AI analysis layer (via MCP), enabling the LLM to reason about detections with physical-world understanding.

Example: *"Back patio. Neighbor's cat frequently triggers motion. The gate has no lock. Delivery packages are sometimes left here."*

### Zone Rules Engine

Zone-level policies define alert behavior:

- **Log everything** (baseline for all zones, always on)
- **Alert if unrecognized person detected** (`ALERT_UNKNOWN_PERSON`)
- **Alert if motion detected outside active hours** (`ALERT_AFTER_HOURS`)
- **Alert if person dwells in zone beyond threshold** (`ALERT_DWELL_TIME`, params: `dwell_threshold_seconds`)
- **Alert if person transitions from zone A to zone B** (`ALERT_ZONE_TRANSITION`, params: `target_zone_id`)
- **Suppress alerts during defined windows** (`SUPPRESS_WINDOW`, params: `start_time`, `end_time`)

### Zone Adjacency Graph

Stored in both PostgreSQL (`ZoneAdjacency` model for configuration) and Neo4j (for graph queries):

```
Nodes = Zones (with camera coverage)
Edges = Physical connectivity + learned transit times

     [Front Porch] ──(5s)──> [Entryway] ──(3s)──> [Hallway]
                                                      |
                                              (4s)    (7s)
                                                |       |
                                           [Kitchen]  [Living Room]
```

**Neo4j Representation:**

```cypher
(:Zone {id: $uuid, name: "Front Porch", zone_type: "ENTRY"})
  -[:ADJACENT_TO {transit_seconds: 5.0, sample_count: 142}]->
(:Zone {id: $uuid, name: "Entryway", zone_type: "ENTRY"})
```

- **Transit times** are learned from observed person transitions by the perception service.
- **Adjacency** can be manually configured via the API or inferred from correlated detections.
- The graph enables cross-zone entity tracking without full 3D reconstruction.

---

## Perception Pipeline

A hierarchical inference pipeline processes each camera frame. Each layer filters and enriches before passing data upward.

### Service Architecture

The `estate-sentry-perception` service is a standalone Python async service that:

1. Subscribes to NATS topics (`frames.{camera_id}.raw`) for frame notifications
2. Retrieves frames from MinIO
3. Runs L1-L7 inference
4. Publishes results to NATS topics (`detections.{zone_id}`, `alerts.{severity}`)
5. Writes zone events to PostgreSQL via the Django API
6. Writes/queries embeddings in ChromaDB
7. Updates entity graphs in Neo4j

### Pipeline Overview

```
Frame In (via NATS: frames.{camera_id}.raw)
  |
  v
[L1] Motion Gate ──── no motion ──> skip frame
  |
  v
[L2] Object Detection (YOLO / RT-DETR)
  |   -> bounding boxes + class (person / vehicle / animal / unknown)
  |
  v
[L3] Zone Intersection
  |   -> which zone(s) does this detection fall in?
  |   -> LOG event to PostgreSQL via API
  |
  v
[L4] Identity Pipeline (persons only)
  |   +-- Face embedding extraction (when face visible)
  |   +-- Appearance embedding extraction (always)
  |   +-- Match against ChromaDB identity store -> confidence score
  |      -> Below threshold? Flag for human review via API
  |
  v
[L5] Action / Pose Estimation
  |   -> standing, walking, running, crouching, carrying object
  |   -> single-frame initially, temporal window later
  |
  v
[L6] Event Correlation
  |   -> Link detection to existing tracked entity
  |   -> Query Neo4j zone adjacency for cross-camera linking
  |   -> Update movement history across zones
  |   -> Compute behavioral features (dwell time, path, speed)
  |
  v
[L7] Threat Assessment
      -> Zone rules (from PostgreSQL) + context + behavioral anomaly scoring
      -> Publish to NATS: alerts.{severity}
      -> Write Alert to PostgreSQL via API
      -> If score >= threshold, trigger MCP/LLM analysis via Sentry Intelligence
```

### NATS Topic Integration

New topics added to the existing Switchboard topic structure:

| Topic Pattern | Direction | Description |
|---------------|-----------|-------------|
| `frames.{camera_id}.raw` | Edge Agent -> Perception | Frame captured notification (includes MinIO path) |
| `detections.{zone_id}` | Perception -> Consumers | Detection event in a zone |
| `tracks.{track_id}.update` | Perception -> Consumers | Entity track update |
| `perception.status` | Perception -> Monitoring | Pipeline health and stats |
| `identity.review` | Perception -> API/HQ | New item in human review queue |

These extend the existing Switchboard topics (`sensors.*`, `alerts.*`, `nodes.*`, `system.*`).

### Layer Details

#### L1: Motion Gate

- **Purpose**: Avoid processing static frames.
- **Method**: Frame differencing, background subtraction, or PIR sensor signal from existing `MOTION` sensor handler.
- **Early exit**: If no motion detected, skip all downstream layers.
- **Integration**: Can use existing `MotionHandler` sensor readings as a gate signal, or run frame differencing internally.

#### L2: Object Detection

- **Purpose**: Locate and classify objects in the frame.
- **Models**: YOLO (v8+), RT-DETR, or equivalent single-shot detector.
- **Output**: List of bounding boxes with class labels and confidence scores.
- **Classes**: person, vehicle, animal, unknown.
- **Hardware**: Runs on CPU or GPU. Model variant configurable (`yolov8n` for edge, `yolov8x` for server).

#### L3: Zone Intersection

- **Purpose**: Determine which zone(s) each detection falls within.
- **Method**: Point-in-polygon test using detection centroid against `ZonePerimeter.polygon` definitions (fetched from API on startup, cached).
- **Key behavior**: Every detection that intersects a zone is logged as a `ZoneEvent` in PostgreSQL, regardless of downstream classification results.

#### L4: Identity Pipeline

Triggered only for person detections. Requires consent to be active.

| Approach | When Used | Storage |
|----------|-----------|---------|
| Face embedding | Face visible in frame | ChromaDB `face_embeddings` collection |
| Appearance embedding | Always (full-body crop) | ChromaDB `appearance_embeddings` collection |

**Matching logic:**

1. Extract face embedding if face is visible (ArcFace/FaceNet).
2. Always extract appearance embedding from full-body crop (OSNet/BoT).
3. Query ChromaDB for nearest matches in `face_embeddings` and `appearance_embeddings`.
4. If best match confidence >= threshold (configurable, default 0.7): assign identity.
5. If best match confidence < threshold: flag for human review queue.
6. If no match found: create new anonymous track, flag for review.

**Human Review Queue:**

- Low-confidence matches are written to `IdentityReviewItem` in PostgreSQL via the API.
- HQ dashboard displays side-by-side comparisons.
- User can confirm, reject, or create a new identity profile.
- Confirmed matches update ChromaDB embeddings, improving future accuracy.

#### L5: Action / Pose Estimation

- **Purpose**: Classify what the detected person is doing.
- **Phase 1** (single-frame): Pose estimation models (YOLO-Pose, MediaPipe, OpenPose) to infer posture and basic action.
- **Phase 2** (temporal): Video-based action recognition using sliding window of frames for improved accuracy on actions like loitering, approaching, trying door handles.
- **Output**: Action label + confidence (e.g., `walking: 0.91`, `crouching: 0.73`).

#### L6: Event Correlation

- **Purpose**: Link detections across frames and cameras into coherent entity tracks.
- **Within-camera**: Standard object tracking (SORT, DeepSORT, ByteTrack).
- **Cross-camera**: ReID embedding matching + Neo4j zone adjacency graph.
  - If a person disappears from Zone A and appears in adjacent Zone B within the learned transit window (queried from `ZoneAdjacency` or Neo4j) with high appearance similarity, link the tracks.
- **Output per entity** (written to `EntityTrack` in PostgreSQL):
  - Movement history (zone sequence + timestamps)
  - Dwell times per zone
  - Speed / trajectory within camera view
  - Behavioral features for threat scoring

#### L7: Threat Assessment

Combines all upstream data into a threat determination.

**Threat Score Formula:**

```
threat_score = (
    zone_sensitivity * zone_weight +      # Zone type and rules
    time_of_day_factor +                  # Nighttime activity
    action_suspicion_score +              # Crouching vs walking
    identity_unknown_penalty +            # Unknown person
    behavioral_anomaly_score +            # Deviation from learned patterns
    dwell_time_factor +                   # Lingering in restricted zone
    zone_transition_anomaly               # Unusual path through zones
)
```

**Threat levels:**

| Score | Level | Response |
|-------|-------|----------|
| 80-100 | CRITICAL | Immediate alert, recommend contacting authorities |
| 60-79 | HIGH | Alert with full analysis, review footage |
| 40-59 | MEDIUM | Monitor for escalation, acknowledge after review |
| 20-39 | LOW | Logged, available in dashboard |
| 0-19 | INFO | Logged only |

**LLM Analysis (via Sentry Intelligence MCP server):**

When a threat score exceeds the configured threshold (default 60), the perception service publishes to `sentry.analyze.threat` on NATS. The Sentry Intelligence service picks this up and:

1. Calls `analyze_alert` MCP tool with full context
2. Includes: zone context document, detection history, identity status, action classification, time of day, zone rules
3. LLM produces natural-language threat assessment and recommendations
4. Response is attached to the Alert as `metadata.llm_analysis`

---

## Identity Store

### ChromaDB Collections

Extends the existing ChromaDB collections (`alerts`, `patterns`, `incidents` from Sentry Intelligence) with perception-specific collections:

| Collection | Embedding Type | Purpose |
|------------|---------------|---------|
| `face_embeddings` | Face encoding (ArcFace, FaceNet) | Stable identity matching |
| `appearance_embeddings` | Full-body ReID (OSNet, BoT) | Clothing-based short-term matching |
| `alerts` | Alert text embedding (existing) | Historical alert similarity |
| `patterns` | Threat pattern embedding (existing) | Known threat pattern matching |
| `incidents` | Incident embedding (existing) | Historical incident matching |

### Django Models (`intelligence` App)

A new `intelligence` Django app manages identity profiles and review items:

```python
# intelligence/models.py
class IdentityProfile(models.Model):
    class Classification(models.TextChoices):
        HOUSEHOLD = 'HOUSEHOLD'
        KNOWN_VISITOR = 'KNOWN_VISITOR'
        DELIVERY = 'DELIVERY'
        UNKNOWN = 'UNKNOWN'
        FLAGGED = 'FLAGGED'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    label = models.CharField(max_length=255)           # Display name or description
    classification = models.CharField(max_length=20, choices=Classification.choices,
                                      default=Classification.UNKNOWN)
    first_seen = models.DateTimeField()
    last_seen = models.DateTimeField()
    total_sightings = models.IntegerField(default=0)
    known_zones = models.ManyToManyField('zones.Zone', blank=True)
    human_verified = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    # ChromaDB reference IDs for face/appearance embeddings
    face_embedding_ids = models.JSONField(default=list)
    appearance_embedding_ids = models.JSONField(default=list)
    metadata = models.JSONField(default=dict)


class IdentityReviewItem(models.Model):
    """Queue item for human review of identity matches."""
    class Status(models.TextChoices):
        PENDING = 'PENDING'
        CONFIRMED = 'CONFIRMED'
        REJECTED = 'REJECTED'
        NEW_IDENTITY = 'NEW_IDENTITY'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=Status.choices,
                              default=Status.PENDING)
    # The detection that triggered review
    detection_frame_path = models.CharField(max_length=500)  # MinIO path
    detection_timestamp = models.DateTimeField()
    detection_zone = models.ForeignKey('zones.Zone', on_delete=models.SET_NULL, null=True)
    # Candidate match (if any)
    candidate_identity = models.ForeignKey(IdentityProfile, null=True, blank=True,
                                           on_delete=models.SET_NULL)
    match_confidence = models.FloatField(null=True)
    # Resolution
    resolved_at = models.DateTimeField(null=True)
    resolved_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL,
                                    related_name='resolved_reviews')
    resolved_identity = models.ForeignKey(IdentityProfile, null=True, blank=True,
                                          on_delete=models.SET_NULL,
                                          related_name='confirmed_reviews')
    created_at = models.DateTimeField(auto_now_add=True)


class ZoneEvent(models.Model):
    """Every detection in every zone, regardless of classification outcome."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    zone = models.ForeignKey('zones.Zone', on_delete=models.CASCADE)
    camera = models.ForeignKey('sensors.Sensor', on_delete=models.CASCADE)
    timestamp = models.DateTimeField(db_index=True)
    # Detection data
    object_class = models.CharField(max_length=30)        # person, vehicle, animal, unknown
    confidence = models.FloatField()
    bounding_box = models.JSONField()                      # [x1, y1, x2, y2] normalized
    # Identity (if resolved)
    identity = models.ForeignKey(IdentityProfile, null=True, blank=True,
                                 on_delete=models.SET_NULL)
    identity_confidence = models.FloatField(null=True)
    # Action (if detected)
    action = models.CharField(max_length=50, blank=True)   # walking, running, crouching
    action_confidence = models.FloatField(null=True)
    # Track linkage
    track_id = models.UUIDField(null=True, db_index=True)
    # Frame reference
    frame_path = models.CharField(max_length=500)          # MinIO path
    metadata = models.JSONField(default=dict)

    class Meta:
        indexes = [
            models.Index(fields=['zone', '-timestamp']),
            models.Index(fields=['track_id', 'timestamp']),
            models.Index(fields=['identity', '-timestamp']),
            models.Index(fields=['object_class', '-timestamp']),
        ]


class EntityTrack(models.Model):
    """A tracked entity across frames and zones."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    identity = models.ForeignKey(IdentityProfile, null=True, blank=True,
                                 on_delete=models.SET_NULL)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True)
    is_active = models.BooleanField(default=True)
    # Computed behavioral features
    zone_sequence = models.JSONField(default=list)         # [{"zone_id": .., "enter": .., "exit": ..}]
    total_dwell_seconds = models.FloatField(default=0)
    zones_visited = models.IntegerField(default=0)
    threat_score = models.FloatField(null=True)
    metadata = models.JSONField(default=dict)
```

### Re-Identification Strategy

| Method | Strengths | Limitations |
|--------|-----------|-------------|
| Face embedding | Stable across clothing changes | Requires frontal/semi-frontal view |
| Appearance embedding | Works at any angle, no face needed | Breaks with clothing changes |
| Hybrid (face + appearance) | Best overall accuracy | Higher compute cost |

- **Primary**: Hybrid approach. Use face when available, always compute appearance.
- **Long-term identity**: Face embeddings (persistent across days).
- **Short-term tracking**: Appearance embeddings (within a session/day).

---

## Multi-Camera Tracking

### Phase 1: Topological Tracking (Near-term)

Uses the zone adjacency graph (stored in both PostgreSQL `ZoneAdjacency` and Neo4j) to correlate entities across cameras without 3D reconstruction.

```
Camera A (front door)          Camera B (hallway)
  +------------+                 +------------+
  |  *->       |                 |       ->*  |
  | person     |                 |    person  |
  | exits      |                 |    enters  |
  | t=0:00     |                 |    t=0:08  |
  +------------+                 +------------+
                    |
                    v
         Event Correlation:
         "Person exited Zone A at t=0:00,
          appeared in Zone B at t=0:08.
          Transit time ~8s. Likely same person
          (appearance similarity: 0.82)"
```

**Implementation:**

1. Perception service maintains in-memory track state per camera.
2. When a track ends in one camera, it publishes `tracks.{track_id}.exit` to NATS with the last appearance embedding.
3. When a new track begins in another camera, it queries ChromaDB for recent exit embeddings.
4. If similarity exceeds threshold AND zones are adjacent (Neo4j query) AND transit time is plausible, tracks are linked.
5. Linked tracks share an `EntityTrack` record in PostgreSQL.

### Phase 2: Spatial Reconstruction (Future)

Full spatial model reconstructing movement paths in physical space.

**Requirements (deferred):**

- Camera calibration (position, angle, lens parameters).
- Homography estimation for floor-plane projection.
- Multi-view fusion for overlapping camera fields.
- Bird's-eye-view occupancy map reconstruction.
- Probabilistic position estimation in unobserved areas using transit models.

---

## Data Flow

### End-to-End Frame Processing

```
IP Camera / Edge Agent
    |
    | RTSP / frame capture
    v
[Edge Agent] -- stores frame --> [MinIO: frames/{camera_id}/{date}/{ts}.jpg]
    |
    | publishes notification
    v
[NATS: frames.{camera_id}.raw]
    |
    | perception service subscribes
    v
[estate-sentry-perception]
    |
    +-- L1: Motion gate (skip if no motion)
    +-- L2: Object detection (YOLO)
    +-- L3: Zone intersection (query ZonePerimeter from cache)
    |       |
    |       +-- writes --> [Django API: POST /api/intelligence/zone-events/]
    |                           |
    |                           v
    |                      [PostgreSQL: intelligence_zoneevent]
    |
    +-- L4: Identity pipeline
    |       |
    |       +-- queries/writes --> [ChromaDB: face_embeddings, appearance_embeddings]
    |       +-- writes review --> [Django API: POST /api/intelligence/identity-reviews/]
    |
    +-- L5: Pose estimation
    +-- L6: Event correlation
    |       |
    |       +-- queries --> [Neo4j: Zone adjacency, entity graphs]
    |       +-- writes --> [Django API: PATCH /api/intelligence/tracks/{id}/]
    |
    +-- L7: Threat assessment
            |
            +-- publishes --> [NATS: alerts.{severity}]
            +-- writes --> [Django API: POST /api/alerts/]
            +-- if high score --> [NATS: sentry.analyze.threat]
                                      |
                                      v
                               [Sentry Intelligence MCP]
                                      |
                                      v
                               [Claude / LLM analysis]
```

### Storage Responsibilities

| Store | Data | Retention | Access Pattern |
|-------|------|-----------|----------------|
| PostgreSQL (TimescaleDB) | Zone events, entity tracks, identity profiles (metadata), alerts, zone config, review queue | Configurable (default 1 year for events, indefinite for config) | CRUD via Django ORM |
| ChromaDB | Face embeddings, appearance embeddings, alert/threat pattern vectors | Indefinite (identity store) | Vector similarity queries from perception service |
| Neo4j | Zone adjacency graph, entity relationship graph, threat correlation patterns | Indefinite (intelligence graph) | Graph traversals from perception service and Sentry Intelligence |
| MinIO | Camera frames, evidence snapshots, video clips | Configurable (default 30 days, extended for flagged events) | Object storage from edge agents, read by perception + HQ |

### Neo4j Graph Schema Extensions

New node and relationship types for the perception system, extending the existing Neo4j schema (`:Sensor`, `:Alert`, `:Location`, `:ThreatPattern`):

```cypher
// Zone nodes
(:Zone {id: $uuid, name: "Front Porch", zone_type: "ENTRY"})

// Zone adjacency
(:Zone)-[:ADJACENT_TO {transit_seconds: 5.0, sample_count: 142}]->(:Zone)

// Camera-zone binding
(:Sensor {sensor_type: "CAMERA"})-[:COVERS]->(:Zone)

// Identity nodes
(:Identity {id: $uuid, label: "John", classification: "HOUSEHOLD"})

// Track nodes (ephemeral, for correlation queries)
(:Track {id: $uuid, started_at: datetime(), active: true})

// Relationships
(:Track)-[:ENTERED]->(:Zone)
(:Track)-[:IDENTIFIED_AS {confidence: 0.85}]->(:Identity)
(:Identity)-[:SEEN_IN]->(:Zone)
(:Track)-[:TRIGGERED]->(:Alert)
```

---

## API Surface

### Zone Management (new `zones` app)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/zones/` | GET, POST | List / create zones |
| `/api/zones/{id}/` | GET, PUT, DELETE | Zone CRUD |
| `/api/zones/{id}/perimeters/` | GET, POST | Zone perimeter polygons per camera |
| `/api/zones/{id}/rules/` | GET, POST, DELETE | Zone rule management |
| `/api/zones/{id}/adjacency/` | GET, PUT | Zone adjacency configuration |
| `/api/zones/graph/` | GET | Full zone adjacency graph (from Neo4j) |

### Intelligence (new `intelligence` app)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/intelligence/zone-events/` | GET, POST | Zone event log (paginated, filterable) |
| `/api/intelligence/tracks/` | GET | Entity tracks (active + recent) |
| `/api/intelligence/tracks/{id}/` | GET, PATCH | Single track with full history |
| `/api/intelligence/identities/` | GET, POST | Identity profile CRUD |
| `/api/intelligence/identities/{id}/` | GET, PUT, DELETE | Single identity profile |
| `/api/intelligence/identity-reviews/` | GET, POST | Human review queue |
| `/api/intelligence/identity-reviews/{id}/resolve/` | POST | Confirm / reject / create identity |

### Perception Status (new endpoints on `api`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/perception/status/` | GET | Pipeline health, processing stats, model info |
| `/api/perception/config/` | GET, PUT | Runtime perception configuration |

### Existing Endpoints (unchanged)

The existing `sensors`, `alerts`, and `authentication` endpoints remain unchanged. New fields (`zone` FK on Sensor and Alert) are additive and backward-compatible.

---

## Frontend Integration (estate-sentry-api/hq)

### New Pages

| Route | Purpose |
|-------|---------|
| `/zones` | Zone list with map/grid view |
| `/zones/[id]` | Zone detail: cameras, sensors, perimeter editor, rules, event feed |
| `/zones/[id]/draw` | Perimeter polygon drawing tool (canvas overlay on camera feed) |
| `/identity` | Identity profile list with search/filter |
| `/identity/[id]` | Identity detail: sightings, zones, review history |
| `/identity/review` | Human review queue: side-by-side comparison UI |
| `/perception` | Perception pipeline status dashboard |

### New Components

| Component | Purpose |
|-----------|---------|
| `ZoneGrid` | Grid/card view of all zones with status indicators |
| `ZoneDetail` | Zone info, context editor, rule manager |
| `PerimeterEditor` | Canvas-based polygon drawing over camera snapshot |
| `ZoneEventFeed` | Real-time event log for a zone (via EventSource/NATS) |
| `IdentityCard` | Identity profile summary card |
| `ReviewComparison` | Side-by-side detection vs. candidate identity for review |
| `TrackTimeline` | Visual timeline of an entity's movement across zones |
| `PerceptionStatus` | Pipeline health, FPS, model stats, queue depth |

### Real-Time Updates

The existing EventSource infrastructure (`lib/streamHandler.ts`, `lib/sensorRelay.ts`) extends to support:

- Zone events: `/api/intelligence/zone-events/stream` (SSE)
- Identity review notifications: `/api/intelligence/identity-reviews/stream` (SSE)
- Perception pipeline status: `/api/perception/status/stream` (SSE)

---

## Sensor Handler Evolution

### CameraHandler Extension

The existing `CameraHandler` in `sensors/handlers/camera.py` evolves to publish frame notifications to NATS instead of only processing locally:

```python
# sensors/handlers/camera.py (evolved)
class CameraHandler(BaseSensorHandler):
    SENSOR_TYPES = ['CAMERA']
    PROTOCOLS = ['rtsp', 'rest', 'websocket']
    VERSION = '2.0.0'

    def process_reading(self, data: dict) -> dict:
        processed = {
            'frame_path': data.get('frame_path'),
            'motion_detected': data.get('motion_detected', False),
            'timestamp': data.get('timestamp'),
            'resolution': data.get('resolution'),
        }

        # Publish frame notification to NATS for perception pipeline
        if processed['frame_path']:
            self._publish_frame_notification(processed)

        return processed

    def detect_threats(self, reading: dict) -> list:
        # Basic motion alerts remain for backward compatibility
        # Full perception pipeline handles advanced threat detection
        alerts = []
        if reading.get('motion_detected'):
            alerts.append({
                'alert_type': 'MOTION',
                'severity': 'LOW',
                'title': f"Motion detected on {self.sensor.name}",
                'description': f"Camera {self.sensor.name} detected motion",
            })
        return alerts
```

The camera handler continues to provide basic motion alerts. The perception service provides the advanced analysis layer on top.

---

## Configuration

```yaml
sentry_intelligence:
  # Consent
  consent:
    required: true
    disclaimer_version: "1.0"

  # Perception Pipeline
  perception:
    motion_gate:
      enabled: true
      sensitivity: medium            # low, medium, high
    object_detection:
      model: yolov8n                 # yolov8n (edge), yolov8m, yolov8x (server)
      confidence_threshold: 0.5
      device: auto                   # cpu, cuda, auto
    identity:
      face_model: arcface            # Face embedding model
      appearance_model: osnet        # ReID appearance model
      match_threshold: 0.7           # Confidence threshold for identity match
      review_queue_enabled: true
    pose_estimation:
      model: yolov8n-pose
      temporal_window: null          # null = single-frame, int = frame count

  # Zone Defaults
  zones:
    default_log_all: true
    default_alert_unknown_person: true
    transit_time_learning: true
    transit_time_window_multiplier: 2.0  # Allow 2x learned transit time

  # Threat Assessment
  threat:
    weights:
      zone_sensitivity: 1.0
      time_of_day: 1.0
      action_suspicion: 1.0
      identity_unknown: 1.5
      behavioral_anomaly: 1.0
      dwell_time: 1.0
    nighttime_hours: [0, 6]          # 00:00 - 06:00
    llm_analysis_threshold: 60       # Minimum score to trigger LLM analysis

  # Storage
  storage:
    frame_retention_days: 30
    flagged_event_retention_days: 365
    embedding_collection_prefix: "estate_sentry"
```

---

## Implementation Phases

### Phase 1: Zone Foundation

**Django changes:**

- New `zones` app with `Zone`, `ZonePerimeter`, `ZoneAdjacency`, `ZoneRule` models
- Add `zone` FK to existing `Sensor` and `Alert` models
- Zone CRUD API endpoints
- `IntelligenceConsent` model in `authentication` app

**Neo4j changes:**

- `:Zone` nodes and `:ADJACENT_TO` relationships
- `:Sensor`-`:COVERS`->`:Zone` relationships

**HQ changes:**

- `/zones` page with zone list/grid
- `/zones/[id]` detail page with context editor and rule manager

### Phase 2: Perception Core

**New service:**

- `estate-sentry-perception/` directory and Dockerfile
- L1 motion gate
- L2 object detection (YOLO)
- L3 zone intersection (with perimeter polygon checking)
- NATS subscription to `frames.{camera_id}.raw`
- Zone event writing to API

**Django changes:**

- New `intelligence` app with `ZoneEvent` model
- Zone event API endpoints

**HQ changes:**

- `ZoneEventFeed` component
- `/perception` status page
- Perimeter polygon drawing tool

### Phase 3: Identity & Tracking

**Perception service:**

- L4 identity pipeline (face + appearance embeddings)
- ChromaDB integration for embedding storage/query
- Within-camera object tracking (DeepSORT/ByteTrack)

**Django changes:**

- `IdentityProfile`, `IdentityReviewItem` models
- Identity CRUD and review queue API endpoints

**HQ changes:**

- `/identity` pages (list, detail)
- `/identity/review` human review queue UI
- `ReviewComparison` component

### Phase 4: Correlation & Assessment

**Perception service:**

- L5 action/pose estimation (single-frame)
- L6 cross-camera event correlation (Neo4j adjacency queries)
- L7 threat assessment with scoring
- Alert generation via API

**Django changes:**

- `EntityTrack` model
- Track API endpoints

**Neo4j changes:**

- `:Track`, `:Identity` nodes
- `:ENTERED`, `:IDENTIFIED_AS`, `:SEEN_IN` relationships

**HQ changes:**

- `TrackTimeline` component
- Enhanced alert detail with perception context

### Phase 5: Intelligence Integration

**Sentry Intelligence (MCP server):**

- New MCP tools: `analyze_zone_event`, `correlate_tracks`, `assess_identity`
- LLM analysis triggered by threat score threshold
- Case report generation with perception data

**Camera handler evolution:**

- CameraHandler v2 publishes to NATS
- Basic motion alerts preserved for backward compatibility

### Phase 6: Advanced Capabilities (Future)

- Temporal action recognition (video-based)
- Multi-view spatial reconstruction
- Gait-based identification
- Bird's-eye-view occupancy mapping
- Zone adjacency auto-inference from detection correlations

---

## Related Documentation

- [Architecture Overview](architecture/overview.md) - System-level architecture
- [Switchboard Architecture](architecture/switchboard.md) - NATS + MinIO data routing
- [Sentry Intelligence](architecture/sentry-intelligence.md) - MCP server and AI engine
- [Database Architecture](architecture/database.md) - Storage layer schemas
- [Device Abstraction](architecture/device-abstraction.md) - Sensor handler framework
- [Security Architecture](architecture/security.md) - Authentication and data protection
- [Development Roadmap](Todo.md) - Implementation task tracking
