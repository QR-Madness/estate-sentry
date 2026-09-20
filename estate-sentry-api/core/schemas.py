"""JSON Schemas for the JSONFields, and the compiled validators for them.

Every model here leans on `JSONField` for flexibility — `Sensor.connection_config`,
`Sensor.metadata`, `SensorReading.value`, `Alert.metadata` — which until now meant
the database would accept any JSON at all, including a scalar where an object was
expected or a payload large enough to matter.

**Schemas are addressed by name, not by value.** Validators store the name and
look the schema up here, so a schema can be tightened without generating a
migration: the migration records `JSONSchemaValidator('sensor.connection_config')`
and nothing about its contents.

**They are deliberately permissive.** `additionalProperties` stays open because
the per-sensor-type schemas that would close it belong on the handler
(`get_connection_schema()`, Milestone 2) and do not exist yet. What these bound
is shape and size — that a config is an object rather than a string, that a port
is a port. A schema that rejects real data is worse than one that is merely loose.
"""

from jsonschema import Draft202012Validator

#: Ceilings in bytes, measured on the compact JSON encoding. Generous against
#: any real payload: a contact reading is a few dozen bytes, and a camera
#: reading carries a URL rather than an image.
MAX_BYTES = {
    'sensor.connection_config': 16 * 1024,
    'sensor.metadata': 16 * 1024,
    'sensor_reading.value': 64 * 1024,
    'alert.metadata': 16 * 1024,
    'audit.metadata': 8 * 1024,
}

_OBJECT = {
    '$schema': 'https://json-schema.org/draft/2020-12/schema',
    'type': 'object',
}

SCHEMAS = {
    # Connection details: host, port, credentials, transport. The named
    # properties are typed where a type is obvious; anything else is allowed
    # through until the handler registry can supply a per-type schema.
    'sensor.connection_config': {
        **_OBJECT,
        'properties': {
            'host': {'type': 'string', 'minLength': 1, 'maxLength': 255},
            'port': {'type': 'integer', 'minimum': 1, 'maximum': 65535},
            'protocol': {
                'type': 'string',
                'enum': ['http', 'https', 'mqtt', 'mqtts', 'ws', 'wss', 'serial'],
            },
            'path': {'type': 'string', 'maxLength': 1024},
            'timeout': {'type': 'number', 'minimum': 0, 'maximum': 300},
        },
        'additionalProperties': True,
    },

    # Free-form annotation: make, model, firmware, install notes.
    'sensor.metadata': {**_OBJECT, 'additionalProperties': True},

    # A reading's payload. Required to be an object, which is the one real
    # tightening here: every handler's `process_reading` returns a dict, and the
    # types that have no handler were previously free to store a bare scalar.
    'sensor_reading.value': {**_OBJECT, 'additionalProperties': True},

    # Alert context: the reading that caused it, a frame path, a timestamp.
    'alert.metadata': {**_OBJECT, 'additionalProperties': True},

    # Whatever a view chose to record about a security event. Small by
    # intention: the audit log is an index of what happened, not a copy of the
    # request that caused it.
    'audit.metadata': {**_OBJECT, 'additionalProperties': True},
}

# Compile once, at import. Two reasons: `check_schema` turns a malformed schema
# into a startup failure rather than a surprise on the first request that
# happens to hit it, and ingest is a hot path — 60 readings a minute per sensor
# — where recompiling a schema per request would be pure waste.
_COMPILED = {}
for _name, _schema in SCHEMAS.items():
    Draft202012Validator.check_schema(_schema)
    _COMPILED[_name] = Draft202012Validator(_schema)


def get_validator(name):
    """Return the compiled validator registered under `name`."""
    try:
        return _COMPILED[name]
    except KeyError:
        raise KeyError(
            f'No JSON Schema registered as {name!r}. '
            f'Known: {", ".join(sorted(SCHEMAS))}'
        ) from None


def get_max_bytes(name):
    """Return the payload ceiling registered under `name`, or None."""
    return MAX_BYTES.get(name)
