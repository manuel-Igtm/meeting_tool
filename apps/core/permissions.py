"""
Shared permissions for the Meeting Tool API.
"""

from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only for the owner
        if hasattr(obj, 'user'):
            return obj.user == request.user
        if hasattr(obj, 'organizer'):
            return obj.organizer == request.user
        return False


class IsOrganizer(permissions.BasePermission):
    """
    Permission to check if user is the meeting organizer.
    """
    
    def has_object_permission(self, request, view, obj):
        return obj.organizer == request.user


class IsOrganizerOrParticipant(permissions.BasePermission):
    """
    Permission for organizers and participants to view meeting details.
    """
    
    def has_object_permission(self, request, view, obj):
        if obj.organizer == request.user:
            return True
        return obj.participants.filter(id=request.user.id).exists()


class IsAdminUser(permissions.BasePermission):
    """
    Permission to check if user has admin role.
    """
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'
