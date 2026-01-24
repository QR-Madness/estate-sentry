# MCP Integration Guide

This guide explains how to use Estate Sentry's Sentry Intelligence system with Claude and other MCP-compatible AI assistants.

## What is MCP?

The Model Context Protocol (MCP) is a standard for connecting AI assistants to external data sources and tools. Estate Sentry's Sentry Intelligence service implements an MCP server that allows AI assistants like Claude to:

- Analyze security alerts
- Correlate events across sensors
- Search for threat patterns
- Generate case reports

## Setup

### Prerequisites

- Estate Sentry running (single or multi-node)
- Sentry Intelligence service deployed
- Claude Desktop or another MCP client

### Configure Claude Desktop

Add Estate Sentry to your Claude Desktop configuration:

```json
// ~/Library/Application Support/Claude/claude_desktop_config.json (macOS)
// %APPDATA%\Claude\claude_desktop_config.json (Windows)
{
  "mcpServers": {
    "estate-sentry": {
      "command": "python",
      "args": ["-m", "sentry.mcp.server"],
      "cwd": "/path/to/estate-sentry-sentry",
      "env": {
        "ESTATE_SENTRY_API_URL": "http://localhost:8000",
        "ESTATE_SENTRY_API_TOKEN": "your-api-token"
      }
    }
  }
}
```

### Alternative: HTTP/SSE Transport

For remote access, use the HTTP transport:

```json
{
  "mcpServers": {
    "estate-sentry": {
      "url": "http://localhost:8002/mcp",
      "transport": "sse"
    }
  }
}
```

### Verify Connection

After restarting Claude Desktop, you should see "estate-sentry" in the available tools. Test with:

> "What tools are available from Estate Sentry?"

Claude should list the available analysis tools.

## Available Tools

### analyze_alert

Analyze a specific security alert for threat assessment.

**Parameters:**
- `alert_id` (required): UUID of the alert
- `depth`: Analysis depth - "quick", "standard", or "deep"

**Example conversation:**

> "I just got an alert with ID abc-123. Can you analyze it?"

Claude will use the `analyze_alert` tool to fetch context and provide analysis.

**Sample output:**

```json
{
  "alert": {
    "id": "abc-123",
    "type": "MOTION",
    "severity": "LOW",
    "title": "Motion detected on Front Camera",
    "timestamp": "2025-01-23T02:30:00Z"
  },
  "sensor": {
    "name": "Front Camera",
    "location": "Front Porch",
    "type": "CAMERA"
  },
  "recent_readings": [...],
  "related_alerts": [...],
  "similar_incidents": [...]
}
```

### correlate_events

Find related security events within a time window.

**Parameters:**
- `alert_ids` (required): List of alert UUIDs
- `time_window_minutes`: Window for correlation (default: 30)

**Example:**

> "I have three alerts: abc-123, def-456, and ghi-789. Are they related?"

Claude will analyze temporal and spatial relationships between the alerts.

### search_patterns

Search for known threat patterns matching current activity.

**Parameters:**
- `query` (required): Description of the pattern to search
- `limit`: Maximum results (default: 10)

**Example:**

> "Search for patterns similar to 'multiple door sensors triggering in sequence'"

### generate_report

Generate a comprehensive security case report.

**Parameters:**
- `alert_ids` (required): List of alert UUIDs to include
- `format`: Output format - "markdown", "pdf", or "json"

**Example:**

> "Generate a case report for alerts abc-123 and def-456"

### get_threat_score

Calculate a threat score for a set of events.

**Parameters:**
- `alert_ids` (required): List of alert UUIDs

**Returns:**
- Threat score (0-100)
- Risk level (INFO, LOW, MEDIUM, HIGH, CRITICAL)
- Contributing factors

## Available Resources

Resources provide read access to Estate Sentry data:

### sentry://alerts/recent

Last 100 security alerts.

> "Show me recent alerts from Estate Sentry"

### sentry://sensors/status

Current status of all sensors.

> "What's the status of my sensors?"

### sentry://patterns/known

Database of known threat patterns.

> "What threat patterns does the system know about?"

### sentry://statistics/daily

Security statistics for the past 24 hours.

> "Give me a summary of security activity today"

## Example Conversations

### Alert Investigation

**User:** I woke up to several alerts overnight. Can you help me understand what happened?

**Claude:** I'll analyze the overnight alerts for you.

*[Uses sentry://alerts/recent to fetch alerts]*

I see 4 alerts between 2:00 AM and 2:15 AM:
1. Motion detected on Front Camera (2:00 AM)
2. Front Door contact opened (2:02 AM)
3. Motion detected in Living Room (2:05 AM)
4. Motion detected on Back Camera (2:15 AM)

Let me correlate these events.

*[Uses correlate_events tool]*

These events appear to be related. The temporal sequence suggests movement from the front of the house to the back. Would you like me to:
1. Generate a full case report?
2. Check for similar historical patterns?
3. Calculate the threat score?

---

### Pattern Analysis

**User:** I keep getting false alarms from my motion sensor. Can you find a pattern?

**Claude:** I'll search for patterns in your motion sensor alerts.

*[Uses search_patterns with "repeated motion sensor false alarms"]*

I found a pattern: Your Living Room motion sensor triggers frequently between 6:00-7:00 AM. This coincides with:
- Sunrise times (light changes)
- HVAC system activation

Recommendations:
1. Adjust sensor sensitivity during these hours
2. Reposition sensor away from HVAC vents
3. Enable "pet immune" mode if available

---

### Daily Security Briefing

**User:** Give me a security briefing for the day.

**Claude:** I'll compile your daily security briefing.

*[Uses sentry://statistics/daily]*

**Security Briefing - January 23, 2025**

**Summary:**
- Total alerts: 12
- High priority: 0
- Medium priority: 2
- Low priority: 10

**Sensor Status:**
- All 8 sensors online
- Battery levels normal (lowest: Guest Door at 67%)

**Notable Events:**
- 2 motion detections during armed hours (both acknowledged as expected arrivals)
- Front door opened 6 times (within normal range)

**Threat Score:** 5/100 (Normal)

No concerning patterns detected. Would you like details on any specific events?

## Custom Prompts

You can create custom prompts for common tasks:

### Security Check Prompt

```
Perform a comprehensive security check:
1. Get current sensor status
2. List any unacknowledged alerts
3. Check for unusual patterns in the last 24 hours
4. Provide a threat assessment

Format as a brief report suitable for review.
```

### Incident Response Prompt

```
I believe there may be an active security incident. Please:
1. Analyze all alerts from the last hour
2. Correlate related events
3. Calculate threat score
4. Provide recommended immediate actions
5. Generate a preliminary incident report

Prioritize speed over completeness.
```

## Programmatic Access

### Python Client

```python
from mcp import Client

async def analyze_security():
    client = Client()
    await client.connect("estate-sentry")

    # Call a tool
    result = await client.call_tool(
        "analyze_alert",
        {"alert_id": "abc-123", "depth": "deep"}
    )

    # Read a resource
    alerts = await client.read_resource("sentry://alerts/recent")

    return result, alerts
```

### HTTP API

```bash
# List available tools
curl http://localhost:8002/mcp/tools

# Call a tool
curl -X POST http://localhost:8002/mcp/tools/analyze_alert \
  -H "Content-Type: application/json" \
  -d '{"alert_id": "abc-123"}'

# Read a resource
curl http://localhost:8002/mcp/resources/sentry%3A%2F%2Falerts%2Frecent
```

## Security Considerations

### API Token Security

- Store tokens securely (environment variables, not in config files)
- Rotate tokens regularly
- Use separate tokens for different MCP clients

### Access Control

The MCP server respects Estate Sentry's permission model:

- User tokens only access owned resources
- Admin tokens can access all data
- Read-only tokens available for monitoring

### Audit Logging

All MCP tool calls are logged:

```python
# View MCP audit log
python manage.py show_mcp_audit --limit 50
```

## Troubleshooting

### MCP Server Not Starting

```bash
# Check server logs
python -m sentry.mcp.server --debug

# Common issues:
# - Missing API token
# - API URL unreachable
# - Port already in use
```

### Tool Calls Failing

```bash
# Test API connectivity
curl http://localhost:8000/api/alerts/

# Verify token
curl http://localhost:8000/api/auth/user/ \
  -H "Authorization: Token your-token"
```

### Slow Responses

Deep analysis can take time. For faster responses:

1. Use `depth: "quick"` for initial triage
2. Limit `time_window_minutes` for correlations
3. Reduce `limit` for pattern searches

## Related Documentation

- [Sentry Intelligence Architecture](../architecture/sentry-intelligence.md)
- [API Usage Guide](api-usage.md)
- [Security Architecture](../architecture/security.md)
