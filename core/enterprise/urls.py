from django.urls import path, include
from rest_framework.routers import SimpleRouter
from core.enterprise.views import (
    FeatureFlagViewSet, TenantFeatureOverrideViewSet, LicenseViewSet,
    ImpersonationSessionViewSet, BulkOperationViewSet, SystemSettingsViewSet,
    DesktopDeviceViewSet, IntegrationWebhookViewSet
)

router = SimpleRouter()
router.register(r'features', FeatureFlagViewSet, basename='feature-flags')
router.register(r'overrides', TenantFeatureOverrideViewSet, basename='tenant-overrides')
router.register(r'licenses', LicenseViewSet, basename='licenses')
router.register(r'impersonate', ImpersonationSessionViewSet, basename='impersonations')
router.register(r'bulk', BulkOperationViewSet, basename='bulk-ops')
router.register(r'settings', SystemSettingsViewSet, basename='settings')
router.register(r'devices', DesktopDeviceViewSet, basename='desktop-devices')
router.register(r'webhooks', IntegrationWebhookViewSet, basename='webhooks')

urlpatterns = [
    path('', include(router.urls)),
]
