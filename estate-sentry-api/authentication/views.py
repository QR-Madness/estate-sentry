from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import TrustedDevice, User
from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    TrustedDeviceSerializer,
    UserSerializer,
)


class RegisterView(generics.CreateAPIView):
    """
    API endpoint for user registration.
    """
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth-register'

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Create auth token for the new user
        token, created = Token.objects.get_or_create(user=user)

        return Response({
            'message': 'User registered successfully',
            'token': token.key,
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """
    API endpoint for user login.
    Supports trusted-device, PIN, and password authentication methods.

    Throttled per client address. The account lockout in `User` bounds guessing
    against one account; this bounds one client's guessing across many. Both are
    needed — neither covers the other's case.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth-login'

    def post(self, request):
        # `context` matters: the serializer reads the device token from a header
        # as well as the body, so a kiosk can send it out of band.
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']

        # Get or create auth token
        token, created = Token.objects.get_or_create(user=user)

        return Response({
            'message': 'Login successful',
            'token': token.key,
            'user': UserSerializer(user).data
        })


class LogoutView(APIView):
    """
    API endpoint for user logout.
    Deletes the user's auth token.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Delete the user's token if it exists
        try:
            request.user.auth_token.delete()
        except Token.DoesNotExist:
            pass

        return Response({
            'message': 'Logout successful'
        }, status=status.HTTP_200_OK)


class UserDetailView(generics.RetrieveUpdateAPIView):
    """
    API endpoint for retrieving and updating user profile.
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class TrustedDeviceListView(generics.ListAPIView):
    """List the caller's enrolled devices, and enrol new ones.

    Enrolment requires an already-authenticated user by design: a device becomes
    trusted because someone who could already prove who they are said so. There
    is no path from "knows a username" to "holds a device token".
    """

    serializer_class = TrustedDeviceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TrustedDevice.objects.filter(user=self.request.user)

    def post(self, request):
        name = (request.data.get('name') or '').strip()
        if not name:
            return Response(
                {'name': 'A device name is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        device, raw_token = TrustedDevice.issue(request.user, name)
        return Response(
            {
                'device': TrustedDeviceSerializer(device).data,
                'device_token': raw_token,
                'message': (
                    'Store this token on the device now. It is not shown again '
                    'and cannot be recovered.'
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class TrustedDeviceRevokeView(APIView):
    """Revoke one device.

    Revoked rather than deleted, so a lost tablet leaves a record of having been
    enrolled and withdrawn instead of quietly disappearing from history.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, device_id):
        try:
            device = TrustedDevice.objects.get(id=device_id, user=request.user)
        except (TrustedDevice.DoesNotExist, ValueError, TypeError):
            return Response(
                {'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND
            )

        device.revoke()
        return Response(TrustedDeviceSerializer(device).data)
