import uuid
from django.db import models
from django.contrib.auth.models import User
from django.db.models import JSONField
from django.core.validators import RegexValidator

# =====================================================================
# 1. FEATURE MANAGEMENT DOMAIN
# =====================================================================

class FeatureFlag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    key = models.CharField(
        max_length=100, 
        unique=True, 
        validators=[RegexValidator(r'^[a-z0-9_]+$')],
        help_text="Key name in snake_case (e.g. advanced_reports)"
    )
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Feature Flag"
        verbose_name_plural = "Feature Flags"

    def __str__(self):
        return f"{self.name} ({self.key})"


class TenantFeatureOverride(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='feature_overrides')
    feature = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE, related_name='tenant_overrides')
    is_enabled = models.BooleanField(default=True)
    config_override = JSONField(default=dict, blank=True, help_text="Custom settings overlay for this tenant")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tenant Feature Override"
        verbose_name_plural = "Tenant Feature Overrides"
        unique_together = ('tenant', 'feature')
        indexes = [
            models.Index(fields=['tenant', 'feature']),
        ]


# =====================================================================
# 2. LICENSE MANAGEMENT DOMAIN
# =====================================================================

class License(models.Model):
    TIER_CHOICES = [
        ('BASIC', 'Basic Edition'),
        ('PREMIUM', 'Premium Edition'),
        ('ENTERPRISE', 'Enterprise Edition')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.OneToOneField('core.Tenant', on_delete=models.CASCADE, related_name='license')
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default='BASIC')
    max_users = models.PositiveIntegerField(default=5)
    max_tables = models.PositiveIntegerField(default=3)
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    cryptographic_signature = models.CharField(
        max_length=256, 
        help_text="Sha256 hash hash signature validating payload to prevent manual db tampering"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "License"
        verbose_name_plural = "Licenses"
        indexes = [
            models.Index(fields=['tenant', 'expires_at']),
        ]


# =====================================================================
# 3. SOFTWARE VERSION MANAGEMENT DOMAIN
# =====================================================================

class SoftwareRelease(models.Model):
    RELEASE_CHOICES = [
        ('STABLE', 'Stable Build'),
        ('BETA', 'Beta Preview'),
        ('HOTFIX', 'Hotfix Patch')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version_code = models.CharField(max_length=32, unique=True, help_text="e.g. 1.2.74")
    release_type = models.CharField(max_length=15, choices=RELEASE_CHOICES, default='STABLE')
    changelog = models.TextField()
    min_desktop_version = models.CharField(max_length=32, default="1.0.0")
    min_mobile_version = models.CharField(max_length=32, default="1.0.0")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Software Release"
        verbose_name_plural = "Software Releases"
        ordering = ['-created_at']


# =====================================================================
# 4. IMPERSONATION DOMAIN
# =====================================================================

class ImpersonationSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    impersonator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='impersonations_started')
    impersonated = models.ForeignKey(User, on_delete=models.CASCADE, related_name='impersonations_received')
    reason = models.TextField()
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "Impersonation Session"
        verbose_name_plural = "Impersonation Sessions"
        indexes = [
            models.Index(fields=['impersonator', 'ended_at']),
        ]


# =====================================================================
# 5. MEDIAFILE DOMAIN
# =====================================================================

class MediaFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='media_files')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="In bytes")
    mime_type = models.CharField(max_length=127)
    storage_path = models.CharField(max_length=512, help_text="Relative storage driver locator path")
    public_url = models.URLField(max_length=1024)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Media File"
        verbose_name_plural = "Media Files"
        indexes = [
            models.Index(fields=['tenant', 'mime_type']),
        ]


# =====================================================================
# 6. NOTIFICATION DOMAIN
# =====================================================================

class Notification(models.Model):
    TYPE_CHOICES = [
        ('SYSTEM', 'System Message'),
        ('EXPORT_READY', 'Document Export Ready'),
        ('IMPORT_COMPLETE', 'Import Pipeline Complete'),
        ('SECURITY_ALERT', 'Security Notification')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    body = models.TextField()
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='SYSTEM')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
        ]


# =====================================================================
# 7. SEARCH DOMAIN
# =====================================================================

class SavedSearchQuery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_searches')
    table = models.ForeignKey('core.DynamicTable', on_delete=models.CASCADE, related_name='saved_searches')
    name = models.CharField(max_length=255)
    query_json = JSONField(help_text="Serialized representation of search criteria and sorting rules")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Saved Search Query"
        verbose_name_plural = "Saved Search Queries"
        unique_together = ('user', 'table', 'name')


# =====================================================================
# 8. BULK OPERATIONS DOMAIN
# =====================================================================

class BulkOperation(models.Model):
    ACTION_CHOICES = [
        ('BULK_DELETE', 'Bulk Delete Cards'),
        ('BULK_STATUS_CHANGE', 'Bulk Status Updates'),
        ('BULK_FIELD_UPDATE', 'Bulk Edit Fields')
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending Worker Execution'),
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Finished Successfully'),
        ('FAILED', 'Failed execution')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='bulk_operations')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action_type = models.CharField(max_length=25, choices=ACTION_CHOICES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    total_records = models.PositiveIntegerField(default=0)
    processed_records = models.PositiveIntegerField(default=0)
    payload = JSONField(default=dict, blank=True, help_text="Filter query, update parameters, or targets IDs")
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bulk Operation"
        verbose_name_plural = "Bulk Operations"
        indexes = [
            models.Index(fields=['tenant', 'status']),
        ]


# =====================================================================
# 9. TABLE TEMPLATE DOMAIN
# =====================================================================

class TableTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    fields_schema = JSONField(help_text="Serialized TableField array structure defining properties list")
    is_public = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Table Template"
        verbose_name_plural = "Table Templates"


# =====================================================================
# 10. IMPORT SESSION DOMAIN
# =====================================================================

class ImportSession(models.Model):
    STATUS_CHOICES = [
        ('INIT', 'Initialized'),
        ('UPLOADED', 'Spreadsheet Uploaded'),
        ('VALIDATING', 'Running Verification checks'),
        ('MERGING', 'Applying items to Database'),
        ('COMPLETED', 'Finished Successfully'),
        ('FAILED', 'Operation Terminated with errors')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='import_sessions')
    table = models.ForeignKey('core.DynamicTable', on_delete=models.CASCADE, related_name='import_sessions')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='INIT')
    xlsx_file = models.ForeignKey(MediaFile, on_delete=models.SET_NULL, null=True, blank=True, related_name='xlsx_imports')
    zip_file = models.ForeignKey(MediaFile, on_delete=models.SET_NULL, null=True, blank=True, related_name='zip_imports')
    mapping_config = JSONField(default=dict, blank=True, help_text="Maps headers to field snake_case keys")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Import Session"
        verbose_name_plural = "Import Sessions"


# =====================================================================
# 11. EXPORT SESSION DOMAIN
# =====================================================================

class ExportSession(models.Model):
    FORMAT_CHOICES = [
        ('PDF', 'PDF Print Document'),
        ('DOCX', 'Word Layout Template'),
        ('XLSX', 'Excel Table Grid'),
        ('ZIP', 'Images Bundle Package')
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending generation'),
        ('PROCESSING', 'Exporting assets'),
        ('COMPLETED', 'Upload complete'),
        ('FAILED', 'Generation failed')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='export_sessions')
    table = models.ForeignKey('core.DynamicTable', on_delete=models.CASCADE, related_name='export_sessions')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    result_file = models.ForeignKey(MediaFile, on_delete=models.SET_NULL, null=True, blank=True, related_name='exports')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Export Session"
        verbose_name_plural = "Export Sessions"


# =====================================================================
# 12. SETTINGS DOMAIN
# =====================================================================

class SystemSettings(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.OneToOneField('core.Tenant', on_delete=models.CASCADE, related_name='settings')
    allowed_ip_ranges = JSONField(default=list, blank=True, help_text="List of permitted CIDR blocks")
    password_policy = JSONField(
        default=dict, 
        blank=True, 
        help_text="Rules parameters: {'min_length': 8, 'require_uppercase': true}"
    )
    session_timeout_seconds = models.PositiveIntegerField(default=3600)
    custom_branding = JSONField(
        default=dict, 
        blank=True, 
        help_text="Styling themes: {'primary_color': '#4A90E2', 'logo_url': '...'}"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"


# =====================================================================
# 13. DESKTOP SYNC DOMAIN
# =====================================================================

class DesktopDevice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='sync_devices')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    device_identifier = models.CharField(max_length=255, unique=True, help_text="Unique hardware GUID hash")
    os_platform = models.CharField(max_length=50)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    app_version = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Desktop Device"
        verbose_name_plural = "Desktop Devices"


class SyncChangeLog(models.Model):
    ACTION_CHOICES = [
        ('INSERT', 'Create Row'),
        ('UPDATE', 'Modify Row'),
        ('DELETE', 'Soft Delete Row')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    table = models.ForeignKey('core.DynamicTable', on_delete=models.CASCADE, related_name='sync_changelogs')
    record_id = models.UUIDField()
    change_type = models.CharField(max_length=10, choices=ACTION_CHOICES)
    version = models.PositiveIntegerField()
    modified_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sync Change Log"
        verbose_name_plural = "Sync Change Logs"
        indexes = [
            models.Index(fields=['table', 'modified_at']),
        ]


# =====================================================================
# 14. EVENT BUS ARCHITECTURE & 15. AUDIT EVENT ARCHITECTURE
# =====================================================================

class IntegrationWebhook(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='webhooks')
    target_url = models.URLField(max_length=1024)
    event_subscriptions = JSONField(
        default=list, 
        help_text="E.g. ['card.created', 'card.deleted', 'export.ready']"
    )
    secret_token = models.CharField(max_length=128, help_text="HMAC key token signing post payloads")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Integration Webhook"
        verbose_name_plural = "Integration Webhooks"


class EventLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='event_logs')
    event_type = models.CharField(max_length=100)  # E.g. card.created, license.expired
    payload = JSONField(help_text="Detailed event data payload")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Event Log"
        verbose_name_plural = "Event Logs"
        indexes = [
            models.Index(fields=['tenant', 'event_type', 'created_at']),
            # GIN index for search inside payload
            models.Index(name='event_log_payload_gin', fields=['payload'], opclasses=['jsonb_path_ops'])
        ]
