"""Validators for the JSONFields.

Both are `@deconstructible`, which is not optional: Django serialises field
validators into migrations, and without it `makemigrations` cannot write them
out.

`JSONSchemaValidator` holds a schema *name* rather than a schema. That keeps
migrations stable across schema edits — the migration records the name, so
tightening a schema in `core/schemas.py` does not generate one.
"""

import json

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible

from .schemas import get_max_bytes, get_validator


@deconstructible
class JSONSchemaValidator:
    """Validate a JSONField against the schema registered under `schema_name`."""

    def __init__(self, schema_name):
        # Resolve now so a typo is an import-time error rather than a 500 on the
        # first request that happens to exercise this field.
        get_validator(schema_name)
        self.schema_name = schema_name

    def __call__(self, value):
        # `iter_errors`, not `validate`: a caller fixing a malformed config
        # should see everything wrong with it at once rather than discovering
        # the next problem on each retry.
        errors = sorted(
            get_validator(self.schema_name).iter_errors(value),
            key=lambda error: error.json_path,
        )
        if errors:
            raise ValidationError(
                [f'{error.json_path}: {error.message}' for error in errors]
            )

    def __eq__(self, other):
        # Django's autodetector compares validators; without this every
        # `makemigrations` would see a change and write another no-op migration.
        return (
            isinstance(other, JSONSchemaValidator)
            and self.schema_name == other.schema_name
        )

    def __hash__(self):
        return hash((self.__class__, self.schema_name))


@deconstructible
class MaxJSONSizeValidator:
    """Bound the encoded size of a JSONField.

    A schema constrains shape, not volume: `{"notes": "<a megabyte>"}` satisfies
    every schema here. This is the backstop that keeps one row from becoming a
    storage problem, measured on the compact encoding actually stored.
    """

    def __init__(self, max_bytes):
        self.max_bytes = max_bytes

    def __call__(self, value):
        try:
            encoded = json.dumps(value, separators=(',', ':'))
        except (TypeError, ValueError) as exc:
            # Not JSON-serialisable at all. The field would fail on save
            # regardless; reporting it here makes it a 400 rather than a 500.
            raise ValidationError(f'Value is not JSON-serialisable: {exc}') from exc

        size = len(encoded.encode('utf-8'))
        if size > self.max_bytes:
            raise ValidationError(
                f'JSON payload is {size} bytes, over the '
                f'{self.max_bytes}-byte limit for this field.'
            )

    def __eq__(self, other):
        return (
            isinstance(other, MaxJSONSizeValidator)
            and self.max_bytes == other.max_bytes
        )

    def __hash__(self):
        return hash((self.__class__, self.max_bytes))


def for_field(schema_name):
    """The validator list for the JSONField registered under `schema_name`.

    Keeps the model definitions to one call and guarantees a field cannot get
    the schema without its matching ceiling.
    """
    validators = [JSONSchemaValidator(schema_name)]

    max_bytes = get_max_bytes(schema_name)
    if max_bytes is not None:
        validators.append(MaxJSONSizeValidator(max_bytes))

    return validators
