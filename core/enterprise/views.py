from rest_framework import viewsets, status, mixins
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.utils import timezone

from core.enterprise.models import (
    FeatureFlag, TenantFeatureOverride, License, SoftwareRelease,
    ImpersonationSession, MediaFile, Notification, SavedSearchQuery,
    BulkOperation, TableTemplate, ImportSession, ExportSession,
    SystemSettings, DesktopDevice, SyncChangeLog, IntegrationWebhook, EventLog
)
from core.enterprise.serializers import (
    FeatureFlagSerializer, TenantFeatureOverrideSerializer, LicenseSerializer,
    SoftwareReleaseSerializer, ImpersonationSessionSerializer, MediaFileSerializer,
    NotificationSerializer, SavedSearchQuerySerializer, BulkOperationSerializer,
    TableTemplateSerializer, ImportSessionSerializer, ExportSessionSerializer,
    SystemSettingsSerializer, DesktopDeviceSerializer, SyncChangeLogSerializer,
    IntegrationWebhookSerializer, EventLogSerializer
)
from core.enterprise.permissions import HasEnterpriseRolePermission
from core.enterprise.services import (
    FeatureService, LicenseService, ImpersonationService, BulkOperationService,
    SettingsService, DesktopSyncService, SearchService
)

# ==========================================
# 1. FEATURE VIEWSETS
# ==========================================

class FeatureFlagViewSet(viewsets.ModelViewSet):
    queryset = FeatureFlag.objects.all()
    serializer_class = FeatureFlagSerializer
    permission_classes = [HasEnterpriseRolePermission]


class TenantFeatureOverrideViewSet(viewsets.ModelViewSet):
    serializer_class = TenantFeatureOverrideSerializer
    permission_classes = [HasEnterpriseRolePermission]

    def get_queryset(self):
        profile = self.request.user.profile
        return TenantFeatureOverride.objects.filter(tenant=profile.tenant)


# ==========================================
# 2. LICENSE VIEWSET
# ==========================================

class LicenseViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LicenseSerializer
    permission_classes = [HasEnterpriseRolePermission]

    def get_queryset(self):
        profile = self.request.user.profile
        if profile.role == 'PRO_USER':
            return License.objects.all()
        return License.objects.filter(tenant=profile.tenant)


# ==========================================
# 3. IMPERSONATION SESSION VIEWSET
# ==========================================

class ImpersonationSessionViewSet(viewsets.ModelViewSet):
    serializer_class = ImpersonationSessionSerializer
    permission_classes = [HasEnterpriseRolePermission]
    queryset = ImpersonationSession.objects.all()

    def perform_create(self, serializer):
        # Call impersonation start service
        ImpersonationService.start_session(
            impersonator=self.request.user,
            impersonated_username=self.request.data.get('username'),
            reason=self.request.data.get('reason'),
            ip=self.request.META.get('REMOTE_ADDR')
        )

    @action(detail=True, methods=['post'], url_path='end')
    def end(self, request, pk=None):
        ImpersonationService.end_session(pk)
        return Response({"status": "session ended"})


# ==========================================
# 4. BULK OPERATIONS VIEWSET
# ==========================================

class BulkOperationViewSet(viewsets.ModelViewSet):
    serializer_class = BulkOperationSerializer
    permission_classes = [HasEnterpriseRolePermission]

    def get_queryset(self):
        profile = self.request.user.profile
        return BulkOperation.objects.filter(tenant=profile.tenant)

    def perform_create(self, serializer):
        profile = self.request.user.profile
        # Triggers bulk task pipelines via service layer
        BulkOperationService.trigger_bulk_operation(
            tenant=profile.tenant,
            user=self.request.user,
            action_type=serializer.validated_data['action_type'],
            filter_query=self.request.data.get('filter_query', {}),
            update_payload=self.request.data.get('update_payload', {})
        )


# ==========================================
# 5. SETTINGS VIEWSET
# ==========================================

class SystemSettingsViewSet(viewsets.ModelViewSet):
    serializer_class = SystemSettingsSerializer
    permission_classes = [HasEnterpriseRolePermission]

    def get_queryset(self):
        profile = self.request.user.profile
        return SystemSettings.objects.filter(tenant=profile.tenant)


# ==========================================
# 6. DESKTOP SYNC VIEWSET
# ==========================================

class DesktopDeviceViewSet(viewsets.ModelViewSet):
    serializer_class = DesktopDeviceSerializer
    permission_classes = [HasEnterpriseRolePermission]

    def get_queryset(self):
        profile = self.request.user.profile
        return DesktopDevice.objects.filter(tenant=profile.tenant)

    @action(detail=False, methods=['get'], url_path='pull-changes')
    def pull_changes(self, request):
        table_id = request.query_params.get('table_id')
        last_sync = request.query_params.get('last_sync')
        
        if not table_id or not last_sync:
            return Response({"error": "table_id and last_sync are required"}, status=status.HTTP_400_BAD_REQUEST)
            
        from core.models import DynamicTable
        table = get_object_or_404(DynamicTable, id=table_id)
        
        # Verify permissions
        self.check_object_permissions(request, table)
        
        last_sync_dt = timezone.datetime.fromisoformat(last_sync)
        changes = DesktopSyncService.fetch_sync_changes(table, last_sync_dt)
        return Response(changes)


# ==========================================
# 7. WEBHOOKS VIEWSET
# ==========================================

class IntegrationWebhookViewSet(viewsets.ModelViewSet):
    serializer_class = IntegrationWebhookSerializer
    permission_classes = [HasEnterpriseRolePermission]

    def get_queryset(self):
        profile = self.request.user.profile
        return IntegrationWebhook.objects.filter(tenant=profile.tenant)
