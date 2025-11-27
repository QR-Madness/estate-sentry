# Database Architecture

Estate Sentry uses a dual-database architecture combining relational and graph databases.

## PostgreSQL (Relational Database)

### Overview

PostgreSQL handles all relational data including users, sensors, readings, and alerts.

**Production Setup:**
- PostgreSQL 16 (Docker)
- Automatic backups
- Connection pooling

**Development Setup:**
- SQLite (default)
- Automatic migrations
- Easy to reset

### Configuration

Set via environment variable:

```python
# SQLite (local development)
DATABASE_ENGINE=sqlite

# PostgreSQL (Docker/production)
DATABASE_ENGINE=postgresql
POSTGRES_DB=estate_sentry
POSTGRES_USER=estate_sentry
POSTGRES_PASSWORD=your-password
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
```

### Data Models

#### User Model

Extends Django's `AbstractUser`:

```python
class User(AbstractUser):
    auth_method = CharField(max_length=20)  # password/pin/username
    pin = CharField(max_length=4, null=True)
    # Inherits: username, email, password, etc.
```

#### Sensor Model

```python
class Sensor(Model):
    owner = ForeignKey(User)
    name = CharField(max_length=255)
    sensor_type = CharField(max_length=50)  # CAMERA, DOOR_CONTACT, etc.
    location = CharField(max_length=255)
    status = CharField(max_length=20)  # ACTIVE, INACTIVE, ERROR, MAINTENANCE
    handler_class = CharField(max_length=100)
    connection_config = JSONField()
    metadata = JSONField()
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
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

#### SensorReading Model

Time-series data storage:

```python
class SensorReading(Model):
    sensor = ForeignKey(Sensor)
    timestamp = DateTimeField(auto_now_add=True)
    value = JSONField()  # Flexible sensor data
    reading_type = CharField(max_length=50)
    processed = BooleanField(default=False)
```

**Example Values:**
```json
// Door contact
{"state": "open"}

// Camera
{"image_url": "/media/cameras/front.jpg", "motion_detected": true}

// Temperature
{"temperature": 72.5, "unit": "F"}
```

#### Alert Model

```python
class Alert(Model):
    owner = ForeignKey(User)
    alert_type = CharField(max_length=50)
    severity = CharField(max_length=20)  # INFO, LOW, MEDIUM, HIGH, CRITICAL
    sensor = ForeignKey(Sensor)
    timestamp = DateTimeField(auto_now_add=True)
    description = TextField()
    acknowledged = BooleanField(default=False)
    acknowledged_at = DateTimeField(null=True)
    metadata = JSONField()
```

**Alert Types:**
- `INTRUSION` - Unauthorized entry
- `ENVIRONMENTAL` - Smoke, CO, water
- `MALFUNCTION` - Sensor errors
- `SYSTEM` - System issues
- `CUSTOM` - User-defined

### Indexing Strategy

Key indexes for performance:

```python
# Sensors
indexes = [
    Index(fields=['owner', 'status']),
    Index(fields=['sensor_type']),
]

# SensorReadings
indexes = [
    Index(fields=['sensor', '-timestamp']),
    Index(fields=['processed']),
]

# Alerts
indexes = [
    Index(fields=['owner', '-timestamp']),
    Index(fields=['acknowledged', 'severity']),
]
```

### Migrations

Django handles schema migrations:

```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Show migration status
python manage.py showmigrations
```

### Backup & Restore

**SQLite (Development):**
```bash
task db:backup    # Backup to timestamped file
task db:restore   # Restore from latest backup
```

**PostgreSQL (Docker):**
```bash
task db:postgres:backup    # pg_dump to data/backups/
task db:postgres:restore   # Restore from latest
task db:reset:docker       # Reset database (⚠️)
```

## Neo4j (Graph Database)

### Overview

Neo4j stores relationship data and powers advanced threat intelligence.

**Features:**
- APOC plugins
- Graph Data Science
- Real-time sync to `./data/neo4j/`

**Access:**
- Browser: http://localhost:7474
- Bolt: bolt://localhost:7687
- User: neo4j / changeme

### Configuration

```python
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=changeme
```

### Data Model

Neo4j stores relationships:

**Nodes:**
- `(:User)` - User accounts
- `(:Sensor)` - Sensors
- `(:Alert)` - Security alerts
- `(:Location)` - Physical locations
- `(:ThreatPattern)` - Known threat patterns

**Relationships:**
```cypher
(:User)-[:OWNS]->(:Sensor)
(:Sensor)-[:LOCATED_IN]->(:Location)
(:Sensor)-[:GENERATED]->(:Alert)
(:Alert)-[:SIMILAR_TO]->(:ThreatPattern)
(:Sensor)-[:CONNECTED_TO]->(:Sensor)
```

### Example Queries

**Find all sensors in a location:**
```cypher
MATCH (u:User {username: 'john'})-[:OWNS]->(s:Sensor)-[:LOCATED_IN]->(l:Location {name: 'Living Room'})
RETURN s
```

**Find related alerts:**
```cypher
MATCH (a:Alert)-[:SIMILAR_TO]->(pattern:ThreatPattern)
WHERE a.timestamp > datetime() - duration('P7D')
RETURN pattern.name, count(a) as occurrences
ORDER BY occurrences DESC
```

**Analyze sensor network:**
```cypher
MATCH path = (s1:Sensor)-[:CONNECTED_TO*]-(s2:Sensor)
WHERE s1.status = 'ACTIVE' AND s2.status = 'ACTIVE'
RETURN path
```

### Data Synchronization

Neo4j data is automatically synchronized:

```
data/neo4j/
├── data/       # Database files (auto-generated)
├── logs/       # Server logs
├── import/     # Files for LOAD CSV
├── export/     # Exported backups
└── plugins/    # APOC, GDS plugins
```

**Commands:**
```bash
task db:neo4j:sync      # Show sync status
task db:neo4j:export    # Export to Cypher script
task db:neo4j:import    # Import from latest export
task db:neo4j:clear     # Clear all data (⚠️)
```

### Backup & Restore

```bash
# Export database
task db:neo4j:export

# Files saved to: data/neo4j/export/backup_TIMESTAMP.cypher

# Import from latest
task db:neo4j:import
```

### Graph Data Science

Neo4j includes Graph Data Science (GDS) for analytics:

**Community Detection:**
```cypher
// Find sensor clusters
CALL gds.louvain.stream('sensor-graph')
YIELD nodeId, communityId
RETURN gds.util.asNode(nodeId).name, communityId
```

**Pathfinding:**
```cypher
// Find shortest path between sensors
MATCH (s1:Sensor {name: 'Front Door'}), (s2:Sensor {name: 'Back Door'})
CALL gds.shortestPath.dijkstra.stream('sensor-graph', {
    sourceNode: s1,
    targetNode: s2
})
YIELD path
RETURN path
```

**Centrality Analysis:**
```cypher
// Find most connected sensors
CALL gds.degree.stream('sensor-graph')
YIELD nodeId, score
RETURN gds.util.asNode(nodeId).name, score
ORDER BY score DESC
LIMIT 10
```

## Database Strategy

### When to Use PostgreSQL

- User authentication
- Sensor configurations
- Time-series sensor readings
- Alert records
- Any tabular data

### When to Use Neo4j

- Sensor relationships
- Location hierarchies
- Threat pattern matching
- Behavioral analysis
- Network topology

### Data Consistency

Both databases stay synchronized:

1. Django ORM updates PostgreSQL
2. Signals trigger Neo4j updates
3. Neo4j stores relationships only
4. PostgreSQL is source of truth

## Performance Optimization

### PostgreSQL

- Indexes on foreign keys
- Indexes on timestamp fields
- Connection pooling (production)
- Query optimization with `select_related()`

### Neo4j

- Property indexes on IDs
- Composite indexes for common queries
- Memory configuration (1GB page cache, 2GB heap)
- APOC for batch operations

## Monitoring

### PostgreSQL

```bash
# Docker logs
task docker:logs:postgres

# Database size
docker-compose exec postgres psql -U estate_sentry -d estate_sentry -c "\l+"

# Table sizes
docker-compose exec postgres psql -U estate_sentry -d estate_sentry -c "\dt+"
```

### Neo4j

```bash
# Docker logs
task docker:logs:neo4j

# Database info
task docker:shell:neo4j
CALL dbms.components() YIELD name, versions, edition
```

## Future Enhancements

- **TimescaleDB** - Time-series optimization for sensor readings
- **Redis** - Caching layer
- **Elasticsearch** - Full-text search for alerts
- **Replication** - Database clustering for HA

## Resources

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Neo4j Documentation](https://neo4j.com/docs/)
- [Django ORM](https://docs.djangoproject.com/en/stable/topics/db/)
- [Graph Data Science](https://neo4j.com/docs/graph-data-science/)
