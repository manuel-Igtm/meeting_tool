"""
URL configuration for meeting_tool project.
"""

from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API v1 Endpoints
    path('api/v1/users/', include('apps.users.urls', namespace='users')),
    path('api/v1/meetings/', include('apps.meetings.urls', namespace='meetings')),
    path('api/v1/notifications/', include('apps.notifications.urls', namespace='notifications')),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# Custom Admin Site Header
admin.site.site_header = 'Meeting Tool Kenya Admin'
admin.site.site_title = 'Meeting Tool Kenya'
admin.site.index_title = 'Welcome to Meeting Tool Administration'
