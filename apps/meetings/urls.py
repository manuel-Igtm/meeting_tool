"""
URL configuration for Meetings app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

app_name = 'meetings'

router = DefaultRouter()
router.register(r'', views.MeetingViewSet, basename='meeting')
router.register(r'availability', views.AvailabilityViewSet, basename='availability')
router.register(r'blocked-time', views.BlockedTimeViewSet, basename='blocked-time')

urlpatterns = [
    # Conflict & Suggestion endpoints
    path('check-conflicts/', views.ConflictCheckView.as_view(), name='check_conflicts'),
    path('suggest-slots/', views.SlotSuggestionView.as_view(), name='suggest_slots'),
    path('user-availability/<uuid:user_id>/', views.UserAvailabilityView.as_view(), name='user_availability'),
    
    # Router URLs
    path('', include(router.urls)),
]
