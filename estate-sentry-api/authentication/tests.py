from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from .models import User


class AuthenticationTestCase(TestCase):
    """Test cases for authentication endpoints."""

    def setUp(self):
        """Set up test client and test data."""
        self.client = APIClient()

    def test_register_user_password_auth(self):
        """Test user registration with password authentication."""
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpassword123',
            'auth_method': 'password',
            'first_name': 'Test',
            'last_name': 'User'
        }

        response = self.client.post('/api/auth/register/', data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['user']['username'], 'testuser')

        # Verify user was created in database
        user = User.objects.get(username='testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.auth_method, 'password')

    def test_register_user_pin_auth(self):
        """Test user registration with PIN authentication."""
        data = {
            'username': 'pinuser',
            'email': 'pin@example.com',
            'auth_method': 'pin',
            'pin': '1234'
        }

        response = self.client.post('/api/auth/register/', data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)

        user = User.objects.get(username='pinuser')
        self.assertEqual(user.pin, '1234')
        self.assertEqual(user.auth_method, 'pin')

    def test_login_with_password(self):
        """Test login with password authentication."""
        # Create a user
        user = User.objects.create_user(
            username='logintest',
            password='testpass123',
            auth_method='password'
        )

        # Login
        data = {
            'username': 'logintest',
            'password': 'testpass123'
        }

        response = self.client.post('/api/auth/login/', data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['user']['username'], 'logintest')

    def test_login_with_pin(self):
        """Test login with PIN authentication."""
        # Create a user with PIN
        user = User.objects.create(
            username='pinlogin',
            auth_method='pin',
            pin='5678'
        )

        # Login with PIN
        data = {
            'username': 'pinlogin',
            'pin': '5678'
        }

        response = self.client.post('/api/auth/login/', data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)

    def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        User.objects.create_user(
            username='testuser',
            password='correctpass',
            auth_method='password'
        )

        data = {
            'username': 'testuser',
            'password': 'wrongpass'
        }

        response = self.client.post('/api/auth/login/', data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout(self):
        """Test logout endpoint."""
        # Create and login user
        user = User.objects.create_user(
            username='logouttest',
            password='testpass',
            auth_method='password'
        )

        self.client.force_authenticate(user=user)

        response = self.client.post('/api/auth/logout/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Logout successful')
