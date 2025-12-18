"""
API Views for User management and authentication.
"""

from django.contrib.auth import update_session_auth_hash
from django.db import models as db_models
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, OpenApiExample

from .models import User
from .serializers import (
    UserSerializer,
    UserRegistrationSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
    UserListSerializer,
)


class RegisterView(generics.CreateAPIView):
    """
    Register a new user account.
    
    Supports registration with either email or phone number.
    Default timezone is set to Africa/Nairobi (Kenya).
    """
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = UserRegistrationSerializer
    
    @extend_schema(
        summary="Register new user",
        description="Create a new user account with email or phone number",
        examples=[
            OpenApiExample(
                "Email Registration",
                value={
                    "email": "john@example.co.ke",
                    "full_name": "John Kamau",
                    "organization": "Tech Startup Nairobi",
                    "password": "securepassword123",
                    "password_confirm": "securepassword123"
                }
            ),
            OpenApiExample(
                "Phone Registration",
                value={
                    "phone_number": "0712345678",
                    "full_name": "Jane Wanjiku",
                    "organization": "University of Nairobi",
                    "password": "securepassword123",
                    "password_confirm": "securepassword123"
                }
            ),
        ]
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate tokens for immediate login
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'success': True,
            'message': 'Account created successfully. Karibu!',
            'data': {
                'user': UserSerializer(user).data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            }
        }, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    """
    Authenticate user and obtain JWT tokens.
    
    Accepts email or phone number as identifier.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = CustomTokenObtainPairSerializer
    
    @extend_schema(
        summary="Login",
        description="Authenticate with email or phone number",
        examples=[
            OpenApiExample(
                "Email Login",
                value={
                    "identifier": "john@example.co.ke",
                    "password": "securepassword123"
                }
            ),
            OpenApiExample(
                "Phone Login",
                value={
                    "identifier": "0712345678",
                    "password": "securepassword123"
                }
            ),
        ]
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class LogoutView(APIView):
    """
    Logout user by blacklisting the refresh token.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(summary="Logout", description="Invalidate refresh token")
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            
            return Response({
                'success': True,
                'message': 'Successfully logged out. Kwaheri!'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'message': 'Invalid token.'
            }, status=status.HTTP_400_BAD_REQUEST)


class ProfileView(generics.RetrieveUpdateAPIView):
    """
    Get or update the authenticated user's profile.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return UserUpdateSerializer
        return UserSerializer
    
    @extend_schema(summary="Get profile", description="Retrieve current user's profile")
    def get(self, request, *args, **kwargs):
        serializer = UserSerializer(request.user)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    @extend_schema(summary="Update profile", description="Update current user's profile")
    def patch(self, request, *args, **kwargs):
        serializer = UserUpdateSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'success': True,
            'message': 'Profile updated successfully.',
            'data': UserSerializer(request.user).data
        })


class ChangePasswordView(APIView):
    """
    Change the authenticated user's password.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="Change password",
        description="Update user's password",
        request=ChangePasswordSerializer
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        # Keep user logged in after password change
        update_session_auth_hash(request, user)
        
        return Response({
            'success': True,
            'message': 'Password changed successfully.'
        }, status=status.HTTP_200_OK)


class UserListView(generics.ListAPIView):
    """
    List users for participant selection.
    
    Searchable by name, email, or organization.
    """
    serializer_class = UserListSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = User.objects.filter(is_active=True)
        
        # Search functionality
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                db_models.Q(full_name__icontains=search) |
                db_models.Q(email__icontains=search) |
                db_models.Q(organization__icontains=search)
            )
        
        # Exclude current user from results
        queryset = queryset.exclude(id=self.request.user.id)
        
        return queryset.order_by('full_name')[:50]
    
    @extend_schema(
        summary="Search users",
        description="Search for users to add as meeting participants"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class UserDetailView(generics.RetrieveAPIView):
    """
    Get details of a specific user (public profile).
    """
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserListSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
