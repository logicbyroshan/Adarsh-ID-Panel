from django.urls import path
from .health import HealthCheckView, ReadinessCheckView, LivenessCheckView

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='health'),
    path('health/ready/', ReadinessCheckView.as_view(), name='ready'),
    path('health/live/', LivenessCheckView.as_view(), name='live'),
]\n