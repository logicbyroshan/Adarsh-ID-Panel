from rest_framework import serializers
from django.contrib.auth.models import User
from core.enterprise.models import (
    FeatureFlag, TenantFeatureOverride, License, SoftwareRelease,
    ImpersonationSession, MediaFile, Notification, SavedSearchQuery,
    BulkOperation, TableTemplate, ImportSession, ExportSession,
    SystemSettings, DesktopDevice, SyncChangeLog, IntegrationWebhook, EventLog
)

class FeatureFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureFlag
        fields = '__all__'


class TenantFeatureOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantFeatureOverride
        fields = '__all__'


class LicenseSerializer(serializers.ModelSerializer):
    is_valid = serializers.SerializerMethodField()

    class Meta:
        model = License
        fields = ['id', 'tenant', 'tier', 'max_users', 'max_tables', 'starts_at', 'expires_at', 'is_valid']
        read_only_fields = ['cryptographic_signature']

    def get_is_valid(self, obj) -> bool:
        from core.enterprise.services import LicenseService
        return LicenseService.verify_license_integrity(obj)


class SoftwareReleaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = SoftwareRelease
        fields = '__all__'


class ImpersonationSessionSerializer(serializers.ModelSerializer):
    impersonator_username = serializers.CharField(source='impersonator.username', read_only=True)
    impersonated_username = serializers.CharField(source='impersonated.username', read_only=True)

    class Meta:
        model = ImpersonationSession
        fields = ['id', 'impersonator_username', 'impersonated_username', 'reason', 'started_at', 'ended_at', 'ip_address']


class MediaFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = MediaFile
        fields = '__all__'


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'recipient', 'title', 'body', 'notification_type', 'is_read', 'created_at']


class SavedSearchQuerySerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedSearchQuery
        fields = '__all__'


class BulkOperationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BulkOperation
        fields = ['id', 'tenant', 'action_type', 'status', 'total_records', 'processed_records', 'payload', 'error_message', 'created_at']
        read_only_fields = ['status', 'total_records', 'processed_records', 'error_message']


class TableTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TableTemplate
        fields = '__all__'


class ImportSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportSession
        fields = '__all__'


class ExportSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExportSession
        fields = '__all__'


class SystemSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSettings
        fields = '__all__'


class DesktopDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DesktopDevice
        fields = '__all__'


class SyncChangeLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyncChangeLog
        fields = '__all__'


class IntegrationWebhookSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationWebhook
        fields = ['id', 'tenant', 'target_url', 'event_subscriptions', 'is_active', 'created_at']
        read_only_fields = ['secret_token']


class EventLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventLog
        fields = '__all__'
