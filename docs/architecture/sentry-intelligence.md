# Sentry Intelligence System

The Sentry Intelligence System is Estate Sentry's AI-powered threat analysis engine. It provides sophisticated pattern detection, alert correlation, behavioral analysis, and automated case report generation through integration with large language models via the Model Context Protocol (MCP).

## Overview

```
+------------------------------------------------------------------+
|                     SENTRY INTELLIGENCE                           |
|                                                                   |
|  +------------------+    +------------------+    +--------------+ |
|  |   MCP Server     |    |  Vector Store    |    |   Neo4j      | |
|  |  (AI Interface)  |    |  (ChromaDB)      |    |  (Graphs)    | |
|  +--------+---------+    +--------+---------+    +------+-------+ |
|           |                       |                     |         |
|           +-------------+---------+---------------------+         |
|                         |                                         |
|              +----------v-----------+                             |
|              |  Intelligence Engine |                             |
|              |  - Correlation       |                             |
|              |  - Scoring           |                             |
|              |  - Analysis          |                             |
|              +----------+-----------+                             |
|                         |                                         |
|              +----------v-----------+                             |
|              |   Report Generator   |                             |
|              +----------------------+                             |
+------------------------------------------------------------------+
         |                    |                    |
+--------v--------+  +--------v--------+  +--------v--------+
|  Claude/LLM     |  |  Django API     |  |  Dashboard      |
|  (Analysis)     |  |  (Alerts)       |  |  (Reports)      |
+-----------------+  +-----------------+  +-----------------+
```

## Core Components

### 1. MCP Server

The MCP (Model Context Protocol) server exposes Estate Sentry's security data and analysis capabilities to AI assistants like Claude.

```python
# sentry/mcp/server.py
from mcp import Server, Tool, Resource

class SentryMCPServer(Server):
    """MCP server for AI-powered security analysis."""

    def __init__(self, intelligence_engine):
        super().__init__(
            name="estate-sentry",
            version="1.0.0"
        )
        self.engine = intelligence_engine

    def get_tools(self):
        return [
            Tool(
                name="analyze_alert",
                description="Analyze a security alert for threat assessment and context",
                input_schema={
                    "type": "object",
                    "properties": {
                        "alert_id": {"type": "string", "description": "Alert UUID"},
                        "depth": {"type": "string", "enum": ["quick", "standard", "deep"]}
                    },
                    "required": ["alert_id"]
                }
            ),
            Tool(
                name="correlate_events",
                description="Find related security events within a time window",
                input_schema={
                    "type": "object",
                    "properties": {
                        "alert_ids": {"type": "array", "items": {"type": "string"}},
                        "time_window_minutes": {"type": "integer", "default": 30}
                    },
                    "required": ["alert_ids"]
                }
            ),
            Tool(
                name="search_patterns",
                description="Search for known threat patterns matching current activity",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "default": 10}
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="generate_report",
                description="Generate a comprehensive security case report",
                input_schema={
                    "type": "object",
                    "properties": {
                        "alert_ids": {"type": "array", "items": {"type": "string"}},
                        "format": {"type": "string", "enum": ["markdown", "pdf", "json"]}
                    },
                    "required": ["alert_ids"]
                }
            ),
            Tool(
                name="get_threat_score",
                description="Calculate threat score for a set of events",
                input_schema={
                    "type": "object",
                    "properties": {
                        "alert_ids": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["alert_ids"]
                }
            )
        ]

    def get_resources(self):
        return [
            Resource(
                uri="sentry://alerts/recent",
                name="Recent Alerts",
                description="Last 100 security alerts",
                mime_type="application/json"
            ),
            Resource(
                uri="sentry://sensors/status",
                name="Sensor Status",
                description="Current status of all sensors",
                mime_type="application/json"
            ),
            Resource(
                uri="sentry://patterns/known",
                name="Known Patterns",
                description="Database of known threat patterns",
                mime_type="application/json"
            ),
            Resource(
                uri="sentry://statistics/daily",
                name="Daily Statistics",
                description="Security statistics for the past 24 hours",
                mime_type="application/json"
            )
        ]
```

### MCP Tool Implementations

```python
# sentry/mcp/tools/analyze.py
async def analyze_alert(alert_id: str, depth: str = "standard") -> dict:
    """Analyze a security alert for threat assessment."""

    alert = await Alert.objects.aget(id=alert_id)
    sensor = alert.sensor

    # Gather context based on depth
    context = {
        "alert": AlertSerializer(alert).data,
        "sensor": SensorSerializer(sensor).data if sensor else None,
    }

    if depth in ["standard", "deep"]:
        # Add recent readings from this sensor
        readings = await get_recent_readings(sensor, limit=20)
        context["recent_readings"] = readings

        # Add related alerts
        related = await get_related_alerts(alert, window_minutes=60)
        context["related_alerts"] = related

    if depth == "deep":
        # Add graph relationships from Neo4j
        graph_context = await neo4j_client.get_alert_context(alert_id)
        context["graph_relationships"] = graph_context

        # Add similar historical patterns
        similar = await vector_store.search_similar(alert, k=5)
        context["similar_incidents"] = similar

    return context
```

### 2. Vector Store (ChromaDB)

ChromaDB stores embeddings of security events for similarity search and pattern matching.

```python
# sentry/intelligence/vector_store.py
import chromadb
from chromadb.config import Settings

class VectorStore:
    """ChromaDB-based vector store for security patterns."""

    def __init__(self, persist_directory: str = "./data/chromadb"):
        self.client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=persist_directory
        ))

        # Collections for different data types
        self.alerts = self.client.get_or_create_collection(
            name="alerts",
            metadata={"description": "Security alert embeddings"}
        )

        self.patterns = self.client.get_or_create_collection(
            name="patterns",
            metadata={"description": "Known threat pattern embeddings"}
        )

        self.incidents = self.client.get_or_create_collection(
            name="incidents",
            metadata={"description": "Historical incident embeddings"}
        )

    async def embed_alert(self, alert: Alert) -> str:
        """Generate and store embedding for an alert."""
        text = self._alert_to_text(alert)
        embedding = await self._generate_embedding(text)

        self.alerts.add(
            ids=[str(alert.id)],
            embeddings=[embedding],
            metadatas=[{
                "alert_type": alert.alert_type,
                "severity": alert.severity,
                "sensor_id": str(alert.sensor_id) if alert.sensor else None,
                "timestamp": alert.timestamp.isoformat(),
            }],
            documents=[text]
        )

        return str(alert.id)

    async def search_similar(self, alert: Alert, k: int = 5) -> list:
        """Find similar historical alerts."""
        text = self._alert_to_text(alert)
        embedding = await self._generate_embedding(text)

        results = self.alerts.query(
            query_embeddings=[embedding],
            n_results=k,
            where={"timestamp": {"$lt": alert.timestamp.isoformat()}}
        )

        return results

    async def search_patterns(self, query: str, limit: int = 10) -> list:
        """Search known threat patterns."""
        embedding = await self._generate_embedding(query)

        results = self.patterns.query(
            query_embeddings=[embedding],
            n_results=limit
        )

        return results

    def _alert_to_text(self, alert: Alert) -> str:
        """Convert alert to text for embedding."""
        parts = [
            f"Alert: {alert.alert_type}",
            f"Severity: {alert.severity}",
            f"Title: {alert.title}",
            f"Description: {alert.description}",
        ]
        if alert.sensor:
            parts.extend([
                f"Sensor: {alert.sensor.name}",
                f"Location: {alert.sensor.location}",
                f"Type: {alert.sensor.sensor_type}",
            ])
        return " | ".join(parts)

    async def _generate_embedding(self, text: str) -> list:
        """Generate embedding using local model or API."""
        # Use sentence-transformers for local embedding
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')
        return model.encode(text).tolist()
```

### 3. Neo4j Graph Database

Neo4j stores relationships between entities for graph-based analysis.

```python
# sentry/graph/neo4j_client.py
from neo4j import AsyncGraphDatabase

class ThreatGraphClient:
    """Neo4j client for threat intelligence graph operations."""

    def __init__(self, uri: str, user: str, password: str):
        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def create_alert_node(self, alert: Alert):
        """Create an alert node with relationships."""
        async with self.driver.session() as session:
            await session.execute_write(self._create_alert_tx, alert)

    @staticmethod
    async def _create_alert_tx(tx, alert):
        query = """
        // Create or match sensor
        MERGE (s:Sensor {id: $sensor_id})
        SET s.name = $sensor_name, s.type = $sensor_type

        // Create alert
        CREATE (a:Alert {
            id: $alert_id,
            type: $alert_type,
            severity: $severity,
            timestamp: datetime($timestamp),
            title: $title
        })

        // Create relationship
        CREATE (s)-[:TRIGGERED]->(a)

        // Link to temporal neighbors (previous alert from same sensor)
        WITH a, s
        OPTIONAL MATCH (prev:Alert)<-[:TRIGGERED]-(s)
        WHERE prev.timestamp < a.timestamp
        WITH a, prev ORDER BY prev.timestamp DESC LIMIT 1
        FOREACH (_ IN CASE WHEN prev IS NOT NULL THEN [1] ELSE [] END |
            CREATE (prev)-[:FOLLOWED_BY]->(a)
        )
        """
        await tx.run(query, {
            "sensor_id": str(alert.sensor.id),
            "sensor_name": alert.sensor.name,
            "sensor_type": alert.sensor.sensor_type,
            "alert_id": str(alert.id),
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "timestamp": alert.timestamp.isoformat(),
            "title": alert.title,
        })

    async def find_correlated_alerts(
        self,
        alert_id: str,
        window_minutes: int = 30
    ) -> list:
        """Find alerts correlated in time and space."""
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (a:Alert {id: $alert_id})<-[:TRIGGERED]-(s:Sensor)
                MATCH (s)-[:LOCATED_IN]->(l:Location)
                MATCH (other:Sensor)-[:LOCATED_IN]->(l)
                MATCH (other)-[:TRIGGERED]->(related:Alert)
                WHERE related.timestamp > a.timestamp - duration({minutes: $window})
                  AND related.timestamp < a.timestamp + duration({minutes: $window})
                  AND related.id <> a.id
                RETURN related, other.name as sensor_name
                ORDER BY abs(duration.between(a.timestamp, related.timestamp).minutes)
                LIMIT 20
            """, {"alert_id": alert_id, "window": window_minutes})

            return [record.data() async for record in result]

    async def detect_patterns(self, timeframe_hours: int = 24) -> list:
        """Detect suspicious patterns in recent activity."""
        async with self.driver.session() as session:
            # Find rapid succession of alerts (potential coordinated attack)
            rapid_succession = await session.run("""
                MATCH (a1:Alert)-[:FOLLOWED_BY]->(a2:Alert)
                WHERE a1.timestamp > datetime() - duration({hours: $hours})
                  AND duration.between(a1.timestamp, a2.timestamp).seconds < 60
                WITH a1, collect(a2) as followers
                WHERE size(followers) >= 3
                RETURN a1, followers
            """, {"hours": timeframe_hours})

            # Find multiple sensors triggering in same location
            location_burst = await session.run("""
                MATCH (s:Sensor)-[:LOCATED_IN]->(l:Location)
                MATCH (s)-[:TRIGGERED]->(a:Alert)
                WHERE a.timestamp > datetime() - duration({hours: $hours})
                WITH l, collect(DISTINCT s) as sensors, collect(a) as alerts
                WHERE size(sensors) >= 2
                RETURN l.name as location, sensors, alerts
            """, {"hours": timeframe_hours})

            return {
                "rapid_succession": [r.data() async for r in rapid_succession],
                "location_bursts": [r.data() async for r in location_burst]
            }
```

### 4. Intelligence Engine

The intelligence engine coordinates analysis across all data sources.

```python
# sentry/intelligence/engine.py
class IntelligenceEngine:
    """Core intelligence engine for threat analysis."""

    def __init__(
        self,
        vector_store: VectorStore,
        graph_client: ThreatGraphClient,
    ):
        self.vector_store = vector_store
        self.graph_client = graph_client

    async def analyze_incident(self, alert_ids: list[str]) -> dict:
        """Comprehensive analysis of an incident."""

        # Fetch alerts
        alerts = await Alert.objects.filter(id__in=alert_ids).all()

        # Get graph context
        correlations = []
        for alert in alerts:
            correlated = await self.graph_client.find_correlated_alerts(
                str(alert.id)
            )
            correlations.extend(correlated)

        # Find similar historical incidents
        similar_incidents = []
        for alert in alerts:
            similar = await self.vector_store.search_similar(alert, k=3)
            similar_incidents.extend(similar)

        # Calculate threat score
        threat_score = self._calculate_threat_score(
            alerts, correlations, similar_incidents
        )

        # Build timeline
        timeline = self._build_timeline(alerts, correlations)

        return {
            "alerts": [AlertSerializer(a).data for a in alerts],
            "correlations": correlations,
            "similar_incidents": similar_incidents,
            "threat_score": threat_score,
            "timeline": timeline,
            "recommendations": self._generate_recommendations(threat_score)
        }

    def _calculate_threat_score(
        self,
        alerts: list,
        correlations: list,
        similar_incidents: list
    ) -> dict:
        """Calculate comprehensive threat score."""

        score = 0
        factors = []

        # Severity contribution
        severity_weights = {
            "CRITICAL": 40,
            "HIGH": 30,
            "MEDIUM": 20,
            "LOW": 10,
            "INFO": 5
        }
        max_severity = max(a.severity for a in alerts)
        severity_score = severity_weights.get(max_severity, 10)
        score += severity_score
        factors.append(f"Severity ({max_severity}): +{severity_score}")

        # Multi-alert bonus
        if len(alerts) > 1:
            multi_bonus = min(len(alerts) * 5, 25)
            score += multi_bonus
            factors.append(f"Multiple alerts ({len(alerts)}): +{multi_bonus}")

        # Correlation bonus
        if correlations:
            corr_bonus = min(len(correlations) * 3, 15)
            score += corr_bonus
            factors.append(f"Correlated events ({len(correlations)}): +{corr_bonus}")

        # Similar incident history
        if similar_incidents:
            history_factor = 10
            score += history_factor
            factors.append(f"Historical precedent: +{history_factor}")

        # Time of day factor (nighttime = higher risk)
        hour = datetime.now().hour
        if 0 <= hour < 6:
            night_bonus = 10
            score += night_bonus
            factors.append(f"Nighttime activity: +{night_bonus}")

        return {
            "score": min(score, 100),
            "level": self._score_to_level(score),
            "factors": factors
        }

    def _score_to_level(self, score: int) -> str:
        if score >= 80:
            return "CRITICAL"
        elif score >= 60:
            return "HIGH"
        elif score >= 40:
            return "MEDIUM"
        elif score >= 20:
            return "LOW"
        return "INFO"

    def _build_timeline(self, alerts: list, correlations: list) -> list:
        """Build chronological timeline of events."""
        events = []

        for alert in alerts:
            events.append({
                "timestamp": alert.timestamp.isoformat(),
                "type": "alert",
                "data": AlertSerializer(alert).data
            })

        for corr in correlations:
            events.append({
                "timestamp": corr.get("timestamp"),
                "type": "correlated",
                "data": corr
            })

        return sorted(events, key=lambda e: e["timestamp"])

    def _generate_recommendations(self, threat_score: dict) -> list:
        """Generate actionable recommendations."""
        recommendations = []

        level = threat_score["level"]

        if level == "CRITICAL":
            recommendations.extend([
                "IMMEDIATE: Verify physical security of affected areas",
                "Contact local authorities if intrusion confirmed",
                "Review camera footage for the past hour",
                "Check all entry points in affected zone"
            ])
        elif level == "HIGH":
            recommendations.extend([
                "Review all related alerts within the past 30 minutes",
                "Verify sensor functionality",
                "Consider arming additional zones"
            ])
        elif level == "MEDIUM":
            recommendations.extend([
                "Monitor situation for escalation",
                "Acknowledge alerts after verification"
            ])

        return recommendations
```

### 5. Report Generator

```python
# sentry/reports/generator.py
class CaseReportGenerator:
    """Generate security investigation case reports."""

    def __init__(self, engine: IntelligenceEngine):
        self.engine = engine

    async def generate_report(
        self,
        alert_ids: list[str],
        format: str = "markdown"
    ) -> str:
        """Generate a comprehensive case report."""

        # Get analysis
        analysis = await self.engine.analyze_incident(alert_ids)

        # Build report
        report = self._build_report(analysis)

        # Format output
        if format == "markdown":
            return self._to_markdown(report)
        elif format == "json":
            return json.dumps(report, indent=2)
        elif format == "pdf":
            return await self._to_pdf(report)

    def _build_report(self, analysis: dict) -> dict:
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "summary": self._generate_summary(analysis),
            "threat_assessment": analysis["threat_score"],
            "timeline": analysis["timeline"],
            "affected_sensors": self._extract_sensors(analysis["alerts"]),
            "correlations": analysis["correlations"],
            "historical_context": analysis["similar_incidents"],
            "recommendations": analysis["recommendations"],
        }

    def _to_markdown(self, report: dict) -> str:
        return f"""
# Security Incident Report

**Generated:** {report['generated_at']}

## Executive Summary

{report['summary']}

## Threat Assessment

**Score:** {report['threat_assessment']['score']}/100
**Level:** {report['threat_assessment']['level']}

### Contributing Factors

{chr(10).join('- ' + f for f in report['threat_assessment']['factors'])}

## Timeline of Events

| Time | Event | Details |
|------|-------|---------|
{self._timeline_table(report['timeline'])}

## Affected Sensors

{self._sensors_list(report['affected_sensors'])}

## Recommendations

{chr(10).join('1. ' + r for r in report['recommendations'])}

---

*Report generated by Estate Sentry Intelligence System*
"""
```

## Configuration

```yaml
# sentry_config.yaml
sentry:
  # MCP Server
  mcp:
    host: 0.0.0.0
    port: 8002
    transport: stdio  # or 'sse' for web

  # Vector Store
  vector_store:
    type: chromadb
    persist_directory: ./data/chromadb
    embedding_model: all-MiniLM-L6-v2

  # Neo4j
  neo4j:
    uri: bolt://localhost:7687
    user: neo4j
    password: ${NEO4J_PASSWORD}

  # Analysis
  analysis:
    correlation_window_minutes: 30
    pattern_detection_hours: 24
    similar_incidents_limit: 5

  # Reports
  reports:
    output_directory: ./data/reports
    default_format: markdown
```

## Docker Deployment

```yaml
# docker-compose.sentry.yml
version: '3.8'

services:
  sentry:
    build: ./estate-sentry-sentry
    environment:
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: ${NEO4J_PASSWORD}
      CHROMADB_PATH: /data/chromadb
    volumes:
      - sentry-data:/data
    ports:
      - "8002:8002"
    depends_on:
      - neo4j

  chromadb:
    image: chromadb/chroma:latest
    volumes:
      - chromadb-data:/chroma/chroma
    ports:
      - "8003:8000"

volumes:
  sentry-data:
  chromadb-data:
```

## API Integration

```python
# API endpoints for Sentry
# alerts/views.py

class AlertViewSet(viewsets.ModelViewSet):
    @action(detail=True, methods=['post'])
    async def analyze(self, request, pk=None):
        """Trigger Sentry analysis for an alert."""
        alert = self.get_object()
        analysis = await sentry_engine.analyze_incident([str(alert.id)])
        return Response(analysis)

    @action(detail=False, methods=['post'])
    async def correlate(self, request):
        """Correlate multiple alerts."""
        alert_ids = request.data.get('alert_ids', [])
        analysis = await sentry_engine.analyze_incident(alert_ids)
        return Response(analysis)

    @action(detail=False, methods=['post'])
    async def generate_report(self, request):
        """Generate case report."""
        alert_ids = request.data.get('alert_ids', [])
        format = request.data.get('format', 'markdown')
        report = await report_generator.generate_report(alert_ids, format)
        return Response({'report': report})
```

## Related Documentation

- [MCP Integration Guide](../guides/mcp-integration.md) - Using Sentry with Claude
- [Database Architecture](database.md) - Neo4j schema details
- [Security Architecture](security.md) - Data protection
