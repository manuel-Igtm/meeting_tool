"""
URL configuration for Notifications app.
"""

from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='notification_list'),
    path('preferences/', views.NotificationPreferenceView.as_view(), name='preferences'),
    path('count/', views.NotificationCountView.as_view(), name='count'),
    path('test/', views.TestNotificationView.as_view(), name='test'),
]
