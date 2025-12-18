"""
Custom User Manager for email/phone-based authentication.
"""

from django.contrib.auth.models import BaseUserManager


class UserManager(BaseUserManager):
    """
    Custom user manager for User model with email/phone as primary identifier.
    """
    
    def create_user(self, email=None, phone_number=None, password=None, **extra_fields):
        """
        Create and save a regular user with either email or phone number.
        """
        if not email and not phone_number:
            raise ValueError('User must have either an email address or phone number')
        
        if email:
            email = self.normalize_email(email)
        
        # Normalize Kenyan phone numbers
        if phone_number:
            phone_number = self.normalize_phone_number(phone_number)
        
        user = self.model(
            email=email,
            phone_number=phone_number,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email=None, phone_number=None, password=None, **extra_fields):
        """
        Create and save a superuser.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'admin')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, phone_number, password, **extra_fields)
    
    @staticmethod
    def normalize_phone_number(phone_number):
        """
        Normalize phone number to E.164 format for Kenya (+254...).
        
        Examples:
            0712345678 -> +254712345678
            254712345678 -> +254712345678
            +254712345678 -> +254712345678
        """
        if not phone_number:
            return None
        
        # Remove spaces, dashes, and parentheses
        phone_number = ''.join(filter(lambda x: x.isdigit() or x == '+', phone_number))
        
        # Handle Kenyan numbers
        if phone_number.startswith('0') and len(phone_number) == 10:
            phone_number = '+254' + phone_number[1:]
        elif phone_number.startswith('254') and len(phone_number) == 12:
            phone_number = '+' + phone_number
        elif phone_number.startswith('7') and len(phone_number) == 9:
            phone_number = '+254' + phone_number
        
        return phone_number
