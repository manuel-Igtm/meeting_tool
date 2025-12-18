"""
Serializers for User management and authentication.
"""

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User
from .managers import UserManager


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile information.
    """
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'phone_number', 'full_name', 'organization',
            'job_title', 'timezone', 'role', 'avatar', 'is_verified',
            'email_notifications', 'sms_notifications', 'created_at'
        ]
        read_only_fields = ['id', 'is_verified', 'role', 'created_at']


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.
    Supports registration with email or phone number.
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = [
            'email', 'phone_number', 'full_name', 'organization',
            'job_title', 'timezone', 'password', 'password_confirm',
            'email_notifications', 'sms_notifications'
        ]
        extra_kwargs = {
            'email': {'required': False},
            'phone_number': {'required': False},
            'timezone': {'default': 'Africa/Nairobi'},
        }
    
    def validate(self, attrs):
        """
        Validate registration data.
        """
        # Check that at least one identifier is provided
        if not attrs.get('email') and not attrs.get('phone_number'):
            raise serializers.ValidationError({
                'identifier': 'Please provide either an email address or phone number.'
            })
        
        # Check passwords match
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': 'Passwords do not match.'
            })
        
        # Normalize phone number if provided
        if attrs.get('phone_number'):
            attrs['phone_number'] = UserManager.normalize_phone_number(
                attrs['phone_number']
            )
        
        return attrs
    
    def create(self, validated_data):
        """
        Create new user with validated data.
        """
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        user = User.objects.create_user(
            password=password,
            **validated_data
        )
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user profile.
    """
    
    class Meta:
        model = User
        fields = [
            'full_name', 'organization', 'job_title', 'timezone',
            'avatar', 'email_notifications', 'sms_notifications'
        ]


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for password change.
    """
    old_password = serializers.CharField(
        required=True,
        style={'input_type': 'password'}
    )
    new_password = serializers.CharField(
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    new_password_confirm = serializers.CharField(
        required=True,
        style={'input_type': 'password'}
    )
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': 'New passwords do not match.'
            })
        return attrs
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT token serializer that includes user info in response.
    Supports authentication with email or phone number.
    """
    username_field = 'identifier'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove default username field
        self.fields.pop('email', None)
        # Add flexible identifier field
        self.fields['identifier'] = serializers.CharField(
            help_text='Email or phone number'
        )
    
    def validate(self, attrs):
        identifier = attrs.get('identifier')
        password = attrs.get('password')
        
        # Try to find user by email or phone
        user = None
        
        # Check if identifier looks like email
        if '@' in identifier:
            user = User.objects.filter(email=identifier).first()
        else:
            # Normalize and try phone number
            normalized_phone = UserManager.normalize_phone_number(identifier)
            user = User.objects.filter(phone_number=normalized_phone).first()
            
            # Fallback: try as email anyway
            if not user:
                user = User.objects.filter(email=identifier).first()
        
        if not user:
            raise serializers.ValidationError({
                'identifier': 'No account found with this email or phone number.'
            })
        
        if not user.check_password(password):
            raise serializers.ValidationError({
                'password': 'Incorrect password.'
            })
        
        if not user.is_active:
            raise serializers.ValidationError({
                'identifier': 'This account has been deactivated.'
            })
        
        # Generate tokens
        refresh = self.get_token(user)
        
        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data
        }
        
        return data
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Add custom claims
        token['full_name'] = user.full_name
        token['role'] = user.role
        token['timezone'] = user.timezone
        
        return token


class UserListSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for user lists (e.g., participant selection).
    """
    
    class Meta:
        model = User
        fields = ['id', 'email', 'phone_number', 'full_name', 'organization', 'avatar']
