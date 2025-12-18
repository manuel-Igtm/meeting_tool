"""
Custom exception handler for consistent API error responses.
"""

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """
    Custom exception handler that returns consistent error responses.
    """
    response = exception_handler(exc, context)
    
    if response is not None:
        custom_response_data = {
            'success': False,
            'error': {
                'code': response.status_code,
                'message': get_error_message(response.data),
                'details': response.data
            }
        }
        response.data = custom_response_data
    
    return response


def get_error_message(data):
    """
    Extract a human-readable error message from the response data.
    """
    if isinstance(data, dict):
        if 'detail' in data:
            return str(data['detail'])
        # Get first error message
        for key, value in data.items():
            if isinstance(value, list) and value:
                return f"{key}: {value[0]}"
            elif isinstance(value, str):
                return f"{key}: {value}"
    elif isinstance(data, list) and data:
        return str(data[0])
    return "An error occurred"


class MeetingConflictError(Exception):
    """Raised when a meeting time conflicts with existing meetings."""
    pass


class AvailabilityError(Exception):
    """Raised when a user is not available at the requested time."""
    pass


class NotificationError(Exception):
    """Raised when notification delivery fails."""
    pass
