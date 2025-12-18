"""
Admin configuration for Users app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom User admin with email/phone authentication.
    """
    list_display = [
        'id', 'email', 'phone_number', 'full_name', 
        'organization', 'role', 'is_active', 'is_verified', 'created_at'
    ]
    list_filter = ['role', 'is_active', 'is_verified', 'timezone', 'created_at']
    search_fields = ['email', 'phone_number', 'full_name', 'organization']
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {'fields': ('email', 'phone_number', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'organization', 'job_title', 'avatar')}),
        ('Settings', {'fields': ('timezone', 'role', 'email_notifications', 'sms_notifications')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'last_login']
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'phone_number', 'full_name', 'password1', 'password2'),
        }),
    )
    
    filter_horizontal = ()
