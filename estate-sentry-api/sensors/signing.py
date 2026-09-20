"""Reading signatures: proving a reading came from the device it names.

Without this a reading is trusted on the strength of the account token alone —
any account holder can post any reading as any of their own sensors, and a
reading is not attributable to the hardware that produced it.

**Ed25519, not an HMAC shared secret.** HMAC is simpler, but the server would
have to hold the same secret it verifies with, so a database leak would let an
attacker forge readings from every sensor on the estate. On a security appliance
that is the whole threat. Only the public key is stored here; a leaked database
reveals nothing that helps forge. Keys are 32 bytes and signatures 64, with no
nonce generation needed on the device, which suits constrained hardware.

The wire contract
-----------------

The client sends `nonce` and `signed_at` alongside `value`, and the signature
base64-encoded in an `X-Sensor-Signature` header — matching the `X-Device-Token`
convention already used for trusted devices. What is signed is::

    json.dumps(
        {"nonce": ..., "sensor_id": ..., "signed_at": ..., "value": ...},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")

Every part of that is load-bearing and a producer must reproduce it byte for
byte. `sort_keys` and the separators remove the two degrees of freedom JSON
otherwise leaves. `sensor_id` is inside the payload so a captured signature
cannot be replayed against a different sensor. `value` is the **raw** body as
sent, not the shape the handler normalises it into — the device signs what it
said, not what the server inferred.

Replay
------

A signature alone is a licence to resend a captured "door closed" for ever.
`signed_at` must be within `MAX_CLOCK_SKEW` of now, and the nonce is burned in
the cache for twice that window, so a message is good once and briefly.

The nonce is burned only *after* the signature verifies. Burning it first would
let anyone with the endpoint deny a sensor by pre-spending the nonces it was
about to use.
"""

import base64
import json
from datetime import UTC, datetime, timedelta

from django.core.cache import cache

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

#: How far a device's clock may drift from the server's.
MAX_CLOCK_SKEW = timedelta(minutes=5)

#: Nonces are remembered for twice the acceptance window, so one cannot be
#: reused anywhere inside it.
NONCE_TTL_SECONDS = int(2 * MAX_CLOCK_SKEW.total_seconds())

#: WSGI/ASGI spelling of `X-Sensor-Signature`.
SIGNATURE_HEADER = 'HTTP_X_SENSOR_SIGNATURE'

_ED25519_KEY_BYTES = 32


class SignatureError(Exception):
    """A reading's signature is missing, malformed, stale, replayed or wrong."""


def canonical_bytes(sensor_id, nonce, signed_at, value):
    """The exact bytes a producer must sign. See the module docstring."""
    return json.dumps(
        {
            'nonce': nonce,
            'sensor_id': int(sensor_id),
            'signed_at': signed_at,
            'value': value,
        },
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=True,
    ).encode('utf-8')


def load_public_key(encoded):
    """Load a base64 Ed25519 public key as stored on `Sensor.public_key`."""
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise SignatureError('Stored public key is not valid base64.') from exc

    if len(raw) != _ED25519_KEY_BYTES:
        raise SignatureError(
            f'Stored public key is {len(raw)} bytes; an Ed25519 key is '
            f'{_ED25519_KEY_BYTES}.'
        )

    try:
        return Ed25519PublicKey.from_public_bytes(raw)
    except Exception as exc:
        raise SignatureError('Stored public key could not be loaded.') from exc


def _check_freshness(signed_at, now=None):
    try:
        moment = datetime.fromisoformat(signed_at)
    except (TypeError, ValueError) as exc:
        raise SignatureError(
            "'signed_at' must be an ISO 8601 timestamp."
        ) from exc

    if moment.tzinfo is None:
        raise SignatureError("'signed_at' must carry a UTC offset.")

    now = now or datetime.now(UTC)
    if abs(now - moment) > MAX_CLOCK_SKEW:
        raise SignatureError(
            f"'signed_at' is outside the {int(MAX_CLOCK_SKEW.total_seconds())}s "
            'acceptance window; check the device clock.'
        )


def _burn_nonce(sensor_id, nonce):
    """Claim a nonce, or refuse it as already spent.

    `cache.add` writes only if the key is absent and reports whether it did,
    which is the atomic test-and-set this needs. Like the rate limits, it is
    only as strong as the cache behind it: with a per-process cache each worker
    has its own view of what has been spent.
    """
    if not cache.add(f'sensor-nonce:{sensor_id}:{nonce}', 1, NONCE_TTL_SECONDS):
        raise SignatureError('This nonce has already been used.')


def verify_reading(sensor, signature_b64, nonce, signed_at, value, now=None):
    """Verify one signed reading, or raise `SignatureError`."""
    if not nonce:
        raise SignatureError("A signed reading needs a 'nonce'.")
    if not signed_at:
        raise SignatureError("A signed reading needs a 'signed_at' timestamp.")

    try:
        signature = base64.b64decode(signature_b64, validate=True)
    except (ValueError, TypeError) as exc:
        raise SignatureError('Signature is not valid base64.') from exc

    public_key = load_public_key(sensor.public_key)

    # Freshness before crypto: it is far cheaper, and a stale message is not
    # worth verifying.
    _check_freshness(signed_at, now=now)

    try:
        public_key.verify(
            signature, canonical_bytes(sensor.pk, nonce, signed_at, value)
        )
    except InvalidSignature as exc:
        raise SignatureError(
            'Signature does not match the reading.'
        ) from exc

    # Only now. Burning before verifying would let anyone deny this sensor by
    # spending the nonces it was about to use.
    _burn_nonce(sensor.pk, nonce)


def enforce_policy(sensor, signature_b64, nonce, signed_at, value, now=None):
    """Apply the sensor's signing policy to an incoming reading.

    Four states, which together give a staged rollout rather than a flag day:

    =================  =================  ==========================================
    ``public_key``     ``require_signature``
    =================  =================  ==========================================
    unset              False              unsigned accepted (how every sensor starts)
    set                False              verified when present, absent still accepted
    set                True               required and verified
    unset              True               everything refused — fail closed
    =================  =================  ==========================================
    """
    if not sensor.public_key:
        if sensor.require_signature:
            raise SignatureError(
                'This sensor requires signed readings but has no enrolled key. '
                'Enrol one with `manage.py enroll_sensor_key`.'
            )
        return

    if not signature_b64:
        if sensor.require_signature:
            raise SignatureError(
                'This sensor requires a signed reading; no X-Sensor-Signature '
                'header was sent.'
            )
        return

    verify_reading(sensor, signature_b64, nonce, signed_at, value, now=now)
