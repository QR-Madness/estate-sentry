"""The JSONField validators.

Weighted towards the properties the rest of the system leans on: that a caller
sees every problem at once, that a schema can be edited without a migration, and
that the size cap is measured on what is actually stored.
"""

from django.core.exceptions import ValidationError
from django.test import TestCase

from .schemas import SCHEMAS, get_max_bytes, get_validator
from .validators import JSONSchemaValidator, MaxJSONSizeValidator, for_field


class SchemaRegistryTests(TestCase):
    def test_every_registered_schema_compiles(self):
        """`check_schema` runs at import, so a malformed schema is a startup
        failure. This asserts the registry is actually populated."""
        for name in SCHEMAS:
            with self.subTest(name=name):
                self.assertIsNotNone(get_validator(name))

    def test_an_unknown_name_is_a_useful_error(self):
        with self.assertRaises(KeyError) as ctx:
            get_validator('sensor.nonexistent')

        self.assertIn('sensor.connection_config', str(ctx.exception))

    def test_every_schema_has_a_ceiling(self):
        """A schema without a size cap bounds shape but not volume."""
        for name in SCHEMAS:
            with self.subTest(name=name):
                self.assertIsNotNone(
                    get_max_bytes(name), f'{name} has no MAX_BYTES entry'
                )


class JSONSchemaValidatorTests(TestCase):
    def setUp(self):
        self.validate = JSONSchemaValidator('sensor.connection_config')

    def test_a_valid_config_passes(self):
        self.validate({'host': 'camera.local', 'port': 554, 'protocol': 'https'})

    def test_unknown_keys_are_allowed(self):
        """Deliberately permissive until the handler registry can supply
        per-type schemas. If this starts failing, that decision changed."""
        self.validate({'anything': 'at all', 'nested': {'deeply': [1, 2]}})

    def test_a_scalar_is_refused_where_an_object_belongs(self):
        with self.assertRaises(ValidationError):
            self.validate('camera.local:554')

    def test_a_bad_port_is_refused(self):
        with self.assertRaises(ValidationError) as ctx:
            self.validate({'port': 99999})

        self.assertIn('65535', ctx.exception.messages[0])

    def test_every_problem_is_reported_at_once(self):
        """Not just the first. A caller fixing a config should not have to
        discover the next problem on each retry."""
        with self.assertRaises(ValidationError) as ctx:
            self.validate({'port': 99999, 'protocol': 'carrier-pigeon', 'host': ''})

        self.assertEqual(len(ctx.exception.messages), 3)

    def test_messages_name_the_offending_path(self):
        with self.assertRaises(ValidationError) as ctx:
            self.validate({'port': 99999})

        self.assertTrue(ctx.exception.messages[0].startswith('$.port:'))

    def test_an_unknown_schema_name_fails_at_construction(self):
        """Rather than on the first request that happens to hit the field."""
        with self.assertRaises(KeyError):
            JSONSchemaValidator('sensor.nonexistent')


class MaxJSONSizeValidatorTests(TestCase):
    def test_a_payload_under_the_limit_passes(self):
        MaxJSONSizeValidator(1000)({'note': 'x' * 100})

    def test_a_payload_over_the_limit_is_refused(self):
        with self.assertRaises(ValidationError) as ctx:
            MaxJSONSizeValidator(100)({'note': 'x' * 500})

        self.assertIn('over the 100-byte limit', ctx.exception.messages[0])

    def test_the_measurement_is_on_the_encoded_bytes(self):
        """Not on character count: a multi-byte character costs what it costs
        in storage."""
        with self.assertRaises(ValidationError):
            # 40 characters, but well over 40 bytes once encoded.
            MaxJSONSizeValidator(40)({'n': 'é' * 40})

    def test_unserialisable_input_is_a_validation_error_not_a_crash(self):
        with self.assertRaises(ValidationError):
            MaxJSONSizeValidator(1000)({'when': object()})


class DeconstructionTests(TestCase):
    """Both validators end up inside migrations, which requires all of this."""

    def test_a_schema_validator_round_trips(self):
        original = JSONSchemaValidator('sensor.metadata')
        path, args, kwargs = original.deconstruct()

        self.assertEqual(path, 'core.validators.JSONSchemaValidator')
        self.assertEqual(JSONSchemaValidator(*args, **kwargs), original)

    def test_a_size_validator_round_trips(self):
        original = MaxJSONSizeValidator(2048)
        path, args, kwargs = original.deconstruct()

        self.assertEqual(MaxJSONSizeValidator(*args, **kwargs), original)

    def test_equal_validators_compare_equal(self):
        """Without this the autodetector writes a no-op migration every run."""
        self.assertEqual(
            JSONSchemaValidator('sensor.metadata'),
            JSONSchemaValidator('sensor.metadata'),
        )
        self.assertNotEqual(
            JSONSchemaValidator('sensor.metadata'),
            JSONSchemaValidator('alert.metadata'),
        )

    def test_the_migration_records_the_name_not_the_schema(self):
        """The reason validators hold a name: editing a schema in
        core/schemas.py must not generate a migration."""
        _, args, _ = JSONSchemaValidator('sensor.metadata').deconstruct()

        self.assertEqual(args, ('sensor.metadata',))


class ForFieldTests(TestCase):
    def test_it_pairs_a_schema_with_its_ceiling(self):
        validators = for_field('sensor.connection_config')

        self.assertEqual(
            [type(v).__name__ for v in validators],
            ['JSONSchemaValidator', 'MaxJSONSizeValidator'],
        )
        self.assertEqual(validators[1].max_bytes, get_max_bytes('sensor.connection_config'))
