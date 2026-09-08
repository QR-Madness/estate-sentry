from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import TrustedDevice, User

#: One message for every failure mode. Which credential was wrong, and whether
#: the username existed at all, are both things an attacker would like to know
#: and a legitimate user does not need told apart.
INVALID = "Invalid credentials"

#: Said plainly, because a locked-out owner needs to understand why their PIN
#: stopped working. It leaks only that an account exists and is locked, which is
#: a fair trade against the alternative of someone concluding their alarm is
#: broken.
LOCKED = "Too many failed attempts. Try again later."


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'auth_method', 'phone_number', 'notification_enabled', 'date_joined']
        read_only_fields = ['id', 'date_joined']


class TrustedDeviceSerializer(serializers.ModelSerializer):
    """Read view of an enrolled device. Never exposes the token."""

    class Meta:
        model = TrustedDevice
        fields = ['id', 'name', 'created_at', 'last_seen_at', 'revoked_at']
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""

    password = serializers.CharField(write_only=True, required=False)
    pin = serializers.CharField(write_only=True, required=False, max_length=4)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'first_name', 'last_name',
                  'auth_method', 'pin', 'phone_number']

    def validate(self, data):
        """Validate that the required auth fields are present based on auth_method."""
        auth_method = data.get('auth_method', 'password')

        if auth_method == 'password' and not data.get('password'):
            raise serializers.ValidationError({"password": "Password is required for password authentication"})

        if auth_method == 'pin' and not data.get('pin'):
            raise serializers.ValidationError({"pin": "PIN is required for PIN authentication"})

        if auth_method == 'pin':
            pin = data.get('pin', '')
            if not pin.isdigit() or len(pin) != 4:
                raise serializers.ValidationError({"pin": "PIN must be exactly 4 digits"})

        return data

    def create(self, validated_data):
        """Create a new user with the validated data."""
        password = validated_data.pop('password', None)
        pin = validated_data.pop('pin', None)

        user = User.objects.create(**validated_data)

        if password:
            user.set_password(password)

        if pin:
            user.set_pin(pin)

        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for user login.

    Every path through this ends in one of two places: an authenticated user, or
    the same opaque error. Failures are counted against the account, because a
    four-digit PIN is only meaningful if guessing is bounded.
    """

    username = serializers.CharField()
    password = serializers.CharField(write_only=True, required=False)
    pin = serializers.CharField(write_only=True, required=False)
    device_token = serializers.CharField(write_only=True, required=False)

    def validate(self, data):
        username = data.get('username')
        if not username:
            raise serializers.ValidationError({"username": "Username is required"})

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # The same message whether or not the account exists, so the
            # response cannot be used to enumerate usernames.
            raise serializers.ValidationError({"username": INVALID}) from None

        if user.is_locked_out:
            # Checked before the credential, so a locked account costs an
            # attacker nothing to discover but also gives them no oracle: no
            # amount of guessing during the lockout tells them anything.
            raise serializers.ValidationError({"username": LOCKED})

        authenticated = self._verify(user, data)

        if authenticated is None:
            user.register_failed_auth()
            raise serializers.ValidationError({"username": INVALID})

        authenticated.register_successful_auth()
        data['user'] = authenticated
        return data

    def _verify(self, user: User, data) -> User | None:
        """Check the credential for this user's auth method. None means failure."""
        if user.auth_method == 'username':
            # Not "no credential" — the device holds one. The username alone is
            # an identifier, and identifiers are not secret.
            device = TrustedDevice.authenticate(
                user, data.get('device_token') or self._header_token()
            )
            return user if device is not None else None

        if user.auth_method == 'pin':
            return user if user.check_pin(data.get('pin')) else None

        if user.auth_method == 'password':
            password = data.get('password')
            if not password:
                return None
            # `authenticate` also enforces is_active, which a direct
            # check_password would skip.
            return authenticate(username=user.username, password=password)

        return None

    def _header_token(self) -> str | None:
        """Device token from a header, so a kiosk can send it out of band."""
        request = self.context.get('request')
        if request is None:
            return None
        return request.headers.get('X-Device-Token')
