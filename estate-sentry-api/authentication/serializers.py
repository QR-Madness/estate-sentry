from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'auth_method', 'phone_number', 'notification_enabled', 'date_joined']
        read_only_fields = ['id', 'date_joined']


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
            user.pin = pin

        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""

    username = serializers.CharField()
    password = serializers.CharField(write_only=True, required=False)
    pin = serializers.CharField(write_only=True, required=False)

    def validate(self, data):
        """Validate login credentials based on user's auth_method."""
        username = data.get('username')
        password = data.get('password')
        pin = data.get('pin')

        if not username:
            raise serializers.ValidationError({"username": "Username is required"})

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise serializers.ValidationError({"username": "Invalid credentials"})

        # Validate based on auth method
        if user.auth_method == 'username':
            # Username-only authentication
            data['user'] = user
        elif user.auth_method == 'pin':
            if not pin:
                raise serializers.ValidationError({"pin": "PIN is required"})
            if user.pin != pin:
                raise serializers.ValidationError({"pin": "Invalid credentials"})
            data['user'] = user
        elif user.auth_method == 'password':
            if not password:
                raise serializers.ValidationError({"password": "Password is required"})
            user = authenticate(username=username, password=password)
            if not user:
                raise serializers.ValidationError({"password": "Invalid credentials"})
            data['user'] = user

        return data
