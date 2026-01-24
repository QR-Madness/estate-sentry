# Switchboard Architecture

The Switchboard is Estate Sentry's central data routing backbone, responsible for ingesting, routing, and distributing all sensor data across the system. It handles everything from simple contact sensor states to high-bandwidth video streams from embedded cameras.

## Overview

```
+------------------+     +------------------+     +------------------+
|  Embedded Camera |     |  Motion Sensor   |     |   Door Contact   |
|  (Edge Agent)    |     |  (MQTT)          |     |   (REST)         |
+--------+---------+     +--------+---------+     +--------+---------+
         |                        |                        |
         v                        v                        v
+------------------------------------------------------------------------+
|                           SWITCHBOARD                                   |
|  +------------------+  +------------------+  +------------------+       |
|  |  Frame Ingress   |  |  NATS JetStream  |  |    MinIO         |      |
|  |  (Edge Agents)   |  |  (Message Queue) |  |  (Object Store)  |      |
|  +--------+---------+  +--------+---------+  +--------+---------+      |
|           |                     |                     |                 |
|           +---------------------+---------------------+                 |
|                                 |                                       |
|                    +------------+------------+                          |
|                    |      Message Router     |                          |
|                    +------------+------------+                          |
+----------------------------|--------------------------------------------+
                             |
         +-------------------+-------------------+
         |                   |                   |
+--------v--------+ +--------v--------+ +--------v--------+
|  Django API     | |  Sentry Intel   | |  Other Nodes    |
|  (Processing)   | |  (Analysis)     | |  (Sync)         |
+-----------------+ +-----------------+ +-----------------+
```

## Core Components

### 1. NATS JetStream (Message Queue)

NATS JetStream provides the messaging backbone for all sensor data routing.

**Why NATS:**
- Extremely lightweight (single binary, ~15MB)
- Built-in persistence with JetStream
- At-least-once and exactly-once delivery
- Perfect for edge deployment
- Native clustering for multi-node setups

**Configuration:**

```yaml
# nats-server.conf
server_name: estate-sentry-switchboard
port: 4222

jetstream {
  store_dir: /data/nats
  max_memory_store: 256MB
  max_file_store: 10GB
}

cluster {
  name: estate-sentry
  listen: 0.0.0.0:6222
  routes: [
    nats-route://node-secondary:6222
  ]
}
```

### 2. MinIO (Object Storage)

MinIO provides S3-compatible object storage for media files (images, video frames, recordings).

**Why MinIO:**
- S3-compatible API (industry standard)
- Self-hosted (no cloud dependency)
- Supports erasure coding for data protection
- Built-in replication for multi-node
- Lightweight enough for edge devices

**Bucket Structure:**

```
estate-sentry/
├── frames/                    # Camera frames
│   ├── {camera_id}/
│   │   ├── {date}/
│   │   │   ├── {timestamp}.jpg
│   │   │   └── {timestamp}_thumb.jpg
│   │
├── recordings/                # Video recordings
│   ├── {camera_id}/
│   │   ├── {date}/
│   │   │   └── {start_time}_{end_time}.mp4
│   │
├── snapshots/                 # Alert snapshots
│   ├── {alert_id}/
│   │   ├── frame.jpg
│   │   └── context.json
│   │
└── exports/                   # Report exports
    └── {report_id}/
        └── report.pdf
```

### 3. Message Router

The router directs messages to appropriate consumers based on topic and content.

```python
# routing/router.py
class MessageRouter:
    """Routes messages to appropriate handlers."""

    def __init__(self, nats_client, handlers):
        self.nats = nats_client
        self.handlers = handlers

    async def route(self, subject: str, message: bytes):
        """Route a message to its handler."""
        # Parse subject: sensors.{type}.{id}.{event}
        parts = subject.split('.')
        sensor_type = parts[1]
        sensor_id = parts[2]
        event_type = parts[3]

        handler = self.handlers.get(sensor_type)
        if handler:
            await handler.process(sensor_id, event_type, message)
```

## Topic Structure

NATS subjects follow a hierarchical naming convention:

```
sensors.{sensor_type}.{sensor_id}.{event_type}
```

### Sensor Topics

| Topic Pattern | Description | Example |
|---------------|-------------|---------|
| `sensors.camera.{id}.frame` | Camera frame captured | `sensors.camera.front_door.frame` |
| `sensors.camera.{id}.motion` | Motion detected | `sensors.camera.front_door.motion` |
| `sensors.contact.{id}.state` | Door/window state | `sensors.contact.front_door.state` |
| `sensors.motion.{id}.triggered` | Motion sensor triggered | `sensors.motion.hallway.triggered` |
| `sensors.environmental.{id}.reading` | Environmental reading | `sensors.environmental.kitchen.reading` |

### System Topics

| Topic Pattern | Description |
|---------------|-------------|
| `alerts.{severity}` | Generated alerts by severity |
| `nodes.{node_id}.heartbeat` | Node heartbeat messages |
| `nodes.{node_id}.status` | Node status changes |
| `system.config.update` | Configuration updates |
| `system.sync.request` | Sync request from nodes |

### Frame Topics (High-Bandwidth)

Camera frames use a dedicated stream with special handling:

```
frames.{camera_id}.{quality}
```

| Quality | Resolution | Use Case |
|---------|------------|----------|
| `raw` | Original | Storage, analysis |
| `hd` | 1080p | Streaming to dashboard |
| `sd` | 480p | Thumbnails, mobile |
| `thumb` | 160x120 | Preview grid |

## Edge Agents

Edge agents run on or near sensors that require local processing before data transmission.

### Camera Edge Agent

For embedded cameras and IP cameras that need frame extraction:

```python
# edge/camera.py
class CameraEdgeAgent:
    """Lightweight agent for camera frame capture and transmission."""

    def __init__(self, camera_id: str, config: dict):
        self.camera_id = camera_id
        self.config = config
        self.nats_client = None
        self.minio_client = None

    async def capture_loop(self):
        """Main capture loop."""
        while True:
            frame = await self.capture_frame()

            # Store in MinIO
            frame_path = await self.store_frame(frame)

            # Publish frame notification
            await self.nats_client.publish(
                f"sensors.camera.{self.camera_id}.frame",
                json.dumps({
                    "timestamp": datetime.utcnow().isoformat(),
                    "path": frame_path,
                    "resolution": frame.shape[:2],
                    "motion_detected": self.detect_motion(frame)
                })
            )

            await asyncio.sleep(1 / self.config['fps'])

    async def store_frame(self, frame: np.ndarray) -> str:
        """Store frame in MinIO and return path."""
        timestamp = datetime.utcnow()
        path = f"frames/{self.camera_id}/{timestamp.date()}/{timestamp.isoformat()}.jpg"

        # Encode and upload
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        await self.minio_client.put_object(
            "estate-sentry",
            path,
            io.BytesIO(buffer),
            len(buffer)
        )

        return path
```

### Supported Camera Types

| Type | Connection | Edge Agent Location |
|------|------------|---------------------|
| IP Camera (RTSP) | Network | Switchboard |
| USB Camera | Direct | Local device |
| Raspberry Pi Camera | CSI | Pi itself |
| ESP32-CAM | WiFi | ESP32 (minimal) |
| Commercial NVR | API | Switchboard |

### Edge Agent Configuration

```yaml
# edge_agents.yaml
cameras:
  front_door:
    type: rtsp
    url: rtsp://192.168.1.100:554/stream
    fps: 5
    resolution: 1080p
    motion_detection: true
    motion_threshold: 0.05

  garage:
    type: usb
    device: /dev/video0
    fps: 2
    resolution: 720p
    motion_detection: true

  doorbell:
    type: esp32
    endpoint: http://192.168.1.101/capture
    fps: 1
    motion_detection: false  # Done on device
```

## Frame Processing Pipeline

### Ingestion

```
Camera → Edge Agent → NATS (notification) + MinIO (storage)
```

### Processing

```python
# Switchboard processes frame notifications
async def process_frame_notification(msg):
    data = json.loads(msg.data)

    # 1. Log the frame
    await db.sensor_readings.insert({
        "sensor_id": data["camera_id"],
        "value": {
            "frame_path": data["path"],
            "motion_detected": data["motion_detected"]
        },
        "timestamp": data["timestamp"]
    })

    # 2. If motion detected, trigger analysis
    if data["motion_detected"]:
        await nats.publish(
            f"alerts.LOW",
            json.dumps({
                "type": "MOTION",
                "sensor_id": data["camera_id"],
                "frame_path": data["path"],
                "timestamp": data["timestamp"]
            })
        )

    # 3. Forward to Sentry for ML analysis (if enabled)
    if config.sentry_ml_enabled:
        await nats.publish(
            "sentry.analyze.frame",
            msg.data
        )
```

### Retention

```python
# Frame retention policy
RETENTION_POLICY = {
    "motion_frames": timedelta(days=30),      # Frames with motion
    "regular_frames": timedelta(days=7),       # Regular captures
    "alert_frames": timedelta(days=365),       # Alert-related frames
    "thumbnails": timedelta(days=90),          # Low-res thumbnails
}
```

## Multi-Node Switchboard

In decentralized deployments, each node runs its own Switchboard instance.

### Topology

```
+------------------+          +------------------+
|  Node A          |          |  Node B          |
|  Switchboard     |<-------->|  Switchboard     |
|  +-----------+   |   NATS   |  +-----------+   |
|  | NATS      |   |  Cluster |  | NATS      |   |
|  | MinIO     |   |          |  | MinIO     |   |
|  +-----------+   |          |  +-----------+   |
+------------------+          +------------------+
```

### NATS Clustering

```yaml
# Node A nats.conf
cluster {
  name: estate-sentry
  listen: 0.0.0.0:6222
  routes: [
    nats-route://node-b:6222
    nats-route://node-c:6222
  ]
}

# JetStream replication
jetstream {
  store_dir: /data/nats
  domain: estate
}
```

### MinIO Replication

```bash
# Set up site replication between nodes
mc admin replicate add \
  node-a-minio node-b-minio \
  --replicate "existing-objects,delete,delete-marker"
```

## API Integration

The Switchboard exposes REST endpoints for status and control:

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/switchboard/status` | GET | Overall status |
| `/api/switchboard/streams` | GET | Active NATS streams |
| `/api/switchboard/topics` | GET | Topic subscriptions |
| `/api/switchboard/storage` | GET | MinIO storage stats |
| `/api/switchboard/agents` | GET | Edge agent status |

### WebSocket Streaming

Real-time data streaming via WebSocket:

```javascript
// Connect to Switchboard WebSocket
const ws = new WebSocket('wss://node:8000/ws/switchboard/');

// Subscribe to topics
ws.send(JSON.stringify({
  action: 'subscribe',
  topics: [
    'sensors.camera.front_door.frame',
    'alerts.*'
  ]
}));

// Receive messages
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`[${data.topic}]`, data.message);
};
```

## Docker Deployment

```yaml
# docker-compose.switchboard.yml
version: '3.8'

services:
  nats:
    image: nats:2.10-alpine
    command: ["-js", "-c", "/etc/nats/nats.conf"]
    volumes:
      - ./config/nats.conf:/etc/nats/nats.conf
      - nats-data:/data/nats
    ports:
      - "4222:4222"
      - "8222:8222"  # Monitoring

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: estate-sentry
      MINIO_ROOT_PASSWORD: changeme
    volumes:
      - minio-data:/data
    ports:
      - "9000:9000"
      - "9001:9001"  # Console

  switchboard:
    build: ./estate-sentry-switchboard
    environment:
      NATS_URL: nats://nats:4222
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: estate-sentry
      MINIO_SECRET_KEY: changeme
    depends_on:
      - nats
      - minio
    ports:
      - "8001:8001"

volumes:
  nats-data:
  minio-data:
```

## Performance Tuning

### NATS Optimization

```yaml
# High-throughput configuration
max_payload: 8MB          # For large frames
max_pending: 256MB        # Buffer size
write_deadline: 10s       # Write timeout

jetstream:
  max_memory_store: 1GB   # In-memory buffer
  max_file_store: 100GB   # Persistent storage
```

### MinIO Optimization

```bash
# Enable caching
mc admin config set minio cache \
  "drives=/tmp/minio-cache" \
  "quota=90" \
  "after=1" \
  "watermark_low=70" \
  "watermark_high=90"
```

### Edge Agent Optimization

| Setting | Low-Power Device | Standard Device |
|---------|------------------|-----------------|
| FPS | 1-2 | 5-15 |
| Resolution | 720p | 1080p |
| JPEG Quality | 70 | 85 |
| Motion Threshold | 0.1 | 0.05 |
| Buffer Size | 5 frames | 30 frames |

## Monitoring

### Health Checks

```python
# Health check endpoint
async def health_check():
    return {
        "nats": await check_nats_connection(),
        "minio": await check_minio_connection(),
        "agents": await check_edge_agents(),
        "queues": await get_queue_depths(),
        "storage": await get_storage_stats()
    }
```

### Metrics

| Metric | Description |
|--------|-------------|
| `switchboard_messages_total` | Total messages processed |
| `switchboard_frames_stored` | Frames stored in MinIO |
| `switchboard_queue_depth` | Current queue depth |
| `switchboard_agent_status` | Edge agent health |
| `switchboard_storage_used` | Storage utilization |

## Related Documentation

- [Decentralization](decentralization.md) - Multi-node deployment
- [Device Abstraction](device-abstraction.md) - Sensor handlers
- [Monitoring](../operations/monitoring.md) - Operational monitoring
