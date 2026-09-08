from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import timedelta

from django.contrib.auth.hashers import (
    check_password,
    is_password_usable,
    make_password,
)
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

#: Consecutive failures before an account stops accepting credentials.
#:
#: This is not optional for PIN accounts. A four-digit PIN is 10,000
#: possibilities — hashing protects it if the database leaks, but nothing about
#: hashing slows down someone simply trying every combination against the login
#: endpoint. The lockout is what makes the PIN mean anything.
MAX_FAILED_ATTEMPTS = 5

#: How long an account stays locked. Deliberately finite: a permanent lock would
#: let anyone who knows a username deny the owner access to their own alarm by
#: failing five times, and being locked out of your own house is its own kind of
#: security failure. Fifteen minutes reduces a 10,000-guess search to years
#: while keeping a mistyped PIN a minor annoyance.
LOCKOUT_DURATION = timedelta(minutes=15)


class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    Supports multiple authentication methods: username-only, PIN, or password.
    """

    AUTH_METHOD_CHOICES = [
        ('username', 'Trusted device (username only)'),
        ('pin', 'PIN'),
        ('password', 'Password'),
    ]

    auth_method = models.CharField(
        max_length=20,
        choices=AUTH_METHOD_CHOICES,
        default='password',
        help_text='Authentication method for this user'
    )

    pin = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        help_text='Hashed 4-digit PIN. Never stores the PIN itself.',
    )

    # Additional fields beyond AbstractUser
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    notification_enabled = models.BooleanField(default=True)

    failed_auth_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.username} ({self.get_auth_method_display()})"

    # -- PIN ------------------------------------------------------------------

    def set_pin(self, raw_pin: str | None) -> None:
        """Hash and store a PIN. Passing None clears it.

        Uses the same hasher chain as passwords. A four-digit PIN is weak enough
        that an attacker with the database can exhaust it regardless, but the
        cost per guess still matters, and it means a leaked database does not
        hand over PINs that people have very likely reused on a phone or a door.
        """
        self.pin = make_password(raw_pin) if raw_pin else None

    def check_pin(self, raw_pin: str | None) -> bool:
        """Verify a PIN against the stored hash, in constant time."""
        if not raw_pin or not self.pin:
            return False
        return check_password(raw_pin, self.pin)

    def has_usable_pin(self) -> bool:
        return bool(self.pin) and is_password_usable(self.pin)

    # -- lockout --------------------------------------------------------------

    @property
    def is_locked_out(self) -> bool:
        return bool(self.locked_until and self.locked_until > timezone.now())

    def register_failed_auth(self) -> None:
        """Count a failed attempt, locking the account once the cap is reached."""
        self.failed_auth_attempts += 1
        if self.failed_auth_attempts >= MAX_FAILED_ATTEMPTS:
            self.locked_until = timezone.now() + LOCKOUT_DURATION
        self.save(update_fields=["failed_auth_attempts", "locked_until"])

    def register_successful_auth(self) -> None:
        """Clear the failure count after a genuine login."""
        if self.failed_auth_attempts or self.locked_until:
            self.failed_auth_attempts = 0
            self.locked_until = None
            self.save(update_fields=["failed_auth_attempts", "locked_until"])


def _hash_device_token(raw_token: str) -> str:
    """Hash a device token with SHA-256.

    Not a password hasher, deliberately. Device tokens are 256 bits from
    `secrets`, so there is no dictionary to run and no work factor worth paying:
    the entropy already puts brute force out of reach. Running PBKDF2 on every
    authenticated device request would only be a cost we inflict on ourselves.
    The same reasoning Django applies to session keys.
    """
    return hashlib.sha256(raw_token.encode()).hexdigest()


class TrustedDevice(models.Model):
    """A device that may authenticate a user without a typed credential.

    This is what makes `auth_method='username'` mean something. Previously that
    mode granted a token to anyone who knew a username, which is not
    authentication at all — the username is an identifier, and identifiers are
    not secret. Now the *device* holds the secret: a wall tablet or a kiosk is
    enrolled once by an already-authenticated user, keeps a high-entropy token,
    and presents it on every login. The convenience is preserved (nobody types a
    password on a hallway screen) without the hole.

    The raw token is shown exactly once, at enrolment, and only its hash is kept.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="trusted_devices"
    )
    name = models.CharField(max_length=120, help_text='e.g. "Hall tablet"')

    token_hash = models.CharField(max_length=64, unique=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "trusted_devices"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        state = "revoked" if self.is_revoked else "active"
        return f"{self.name} ({self.user.username}, {state})"

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @classmethod
    def issue(cls, user: User, name: str) -> tuple[TrustedDevice, str]:
        """Enrol a device. Returns the record and the raw token.

        The raw token is the caller's only chance to see it — it is not
        recoverable afterwards, which is the point of storing a hash.
        """
        raw_token = secrets.token_urlsafe(32)
        device = cls.objects.create(
            user=user, name=name, token_hash=_hash_device_token(raw_token)
        )
        return device, raw_token

    @classmethod
    def authenticate(cls, user: User, raw_token: str | None) -> TrustedDevice | None:
        """Return the matching active device for this user, or None.

        Looked up by hash rather than by iterating and comparing, so the cost
        does not grow with the number of enrolled devices and there is no
        timing signal from the ordering.
        """
        if not raw_token:
            return None
        device = cls.objects.filter(
            user=user, token_hash=_hash_device_token(raw_token), revoked_at__isnull=True
        ).first()
        if device is not None:
            device.last_seen_at = timezone.now()
            device.save(update_fields=["last_seen_at"])
        return device

    def revoke(self) -> None:
        """Retire a device. Kept rather than deleted, so the enrolment remains
        auditable after a tablet is lost."""
        if self.revoked_at is None:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at"])
