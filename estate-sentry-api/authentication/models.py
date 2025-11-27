from django.contrib.auth.models import AbstractUser
from django.db import models
import secrets


class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    Supports multiple authentication methods: username-only, PIN, or password.
    """

    AUTH_METHOD_CHOICES = [
        ('username', 'Username Only'),
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
        max_length=4,
        null=True,
        blank=True,
        help_text='4-digit PIN for PIN-based authentication'
    )

    # Additional fields beyond AbstractUser
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    notification_enabled = models.BooleanField(default=True)

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.username} ({self.get_auth_method_display()})"

    def generate_secure_token(self):
        """
        Generate a secure random token for API authentication.
        This is handled by Django REST Framework's token system.
        """
        return secrets.token_urlsafe(64)
