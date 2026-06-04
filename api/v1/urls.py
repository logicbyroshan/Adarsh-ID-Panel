from django.urls import path, include
from .health import HealthCheckView, ReadinessCheckView, LivenessCheckView

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='health'),
    path('health/ready/', ReadinessCheckView.as_view(), name='ready'),
    path('health/live/', LivenessCheckView.as_view(), name='live'),
    
    path('', include('apps.users.urls')),
    path('', include('apps.organizations.urls')),
    path('', include('apps.permissions.urls')),
    path('', include('apps.impersonation.urls')),
    path('', include('apps.tables.urls')),
    path('', include('apps.fields.urls')),
    path('', include('apps.cards.urls')),
]