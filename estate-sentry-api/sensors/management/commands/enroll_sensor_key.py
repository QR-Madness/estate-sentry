"""Enrol a signing key for a sensor.

Deliberately not an API endpoint, for the same reason `enroll_device` is not: if
the account token could install a sensor's key, an attacker holding that token
could install their own and sign whatever they liked, and the signature would
prove nothing beyond what the token already proved. Whoever physically installs
a sensor has shell access to the appliance it reports to, and shell access is
already the stronger credential.

    python manage.py enroll_sensor_key 3                     # generate a keypair
    python manage.py enroll_sensor_key 3 --require           # generate and enforce
    python manage.py enroll_sensor_key 3 --public-key <b64>  # device made its own
    python manage.py enroll_sensor_key 3 --require-only      # enforce an enrolled key
"""

import base64

from django.core.management.base import BaseCommand, CommandError

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from sensors.models import Sensor
from sensors.signing import SignatureError, load_public_key


class Command(BaseCommand):
    help = "Enrol an Ed25519 signing key for a sensor and print the private key once."

    def add_arguments(self, parser):
        parser.add_argument("sensor_id", type=int)
        parser.add_argument(
            "--public-key",
            help="Base64 Ed25519 public key the device generated itself. "
                 "Preferred when the hardware can keep a secret: the private "
                 "key then never exists anywhere but on the device.",
        )
        parser.add_argument(
            "--require",
            action="store_true",
            help="Also refuse unsigned readings from this sensor from now on",
        )
        parser.add_argument(
            "--require-only",
            action="store_true",
            help="Turn on enforcement for a key that is already enrolled",
        )

    def handle(self, *args, **options):
        try:
            sensor = Sensor.objects.get(pk=options["sensor_id"])
        except Sensor.DoesNotExist:
            raise CommandError(f"No sensor with id {options['sensor_id']}.") from None

        if options["require_only"]:
            if not sensor.public_key:
                raise CommandError(
                    f"{sensor.name!r} has no enrolled key, so requiring signatures "
                    "would refuse every reading. Enrol a key first."
                )
            sensor.require_signature = True
            sensor.save(update_fields=["require_signature"])
            self.stdout.write(
                self.style.SUCCESS(f"{sensor.name!r} now requires signed readings.")
            )
            return

        private_key = None

        if options["public_key"]:
            encoded = options["public_key"]
            try:
                load_public_key(encoded)
            except SignatureError as exc:
                raise CommandError(str(exc)) from None
        else:
            private_key = ed25519.Ed25519PrivateKey.generate()
            encoded = base64.b64encode(
                private_key.public_key().public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                )
            ).decode()

        replacing = bool(sensor.public_key)
        sensor.public_key = encoded
        if options["require"]:
            sensor.require_signature = True
        sensor.save(update_fields=["public_key", "require_signature"])

        verb = "Replaced the key for" if replacing else "Enrolled a key for"
        self.stdout.write(
            self.style.SUCCESS(f"\n{verb} {sensor.name!r} (id {sensor.pk}).")
        )
        self.stdout.write(f"\n  public key:  {encoded}")

        if private_key is not None:
            secret = base64.b64encode(
                private_key.private_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PrivateFormat.Raw,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            ).decode()
            self.stdout.write(f"  private key: {secret}\n")
            self.stdout.write(
                "\nInstall the private key on the device now. It is not stored "
                "here and cannot be shown again.\n"
            )

        if replacing:
            self.stdout.write(
                self.style.WARNING(
                    "The previous key no longer verifies. Any device still "
                    "holding it will start being refused."
                )
            )

        if not sensor.require_signature:
            self.stdout.write(
                self.style.WARNING(
                    "\nSignatures are verified when present but not yet required, "
                    "so unsigned readings are still accepted. Re-run with "
                    "--require-only once the device is signing."
                )
            )
