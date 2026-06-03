import uuid
from django.db import models
from django.contrib.auth.models import User
from django.db.models import JSONField
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError

# ==========================================
# 1. TENANT & USER HIERARCHY MODELS
# ==========================================

class Tenant(models.Model):
    """
    Represents an Organization tenant in the system.
    Subdomains are restricted to lowercase alphanumeric characters and hyphens.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    subdomain = models.CharField(
        max_length=63, 
        unique=True, 
        validators=[RegexValidator(r'^[a-z0-9\-]+$', message="Subdomain must be lowercase alphanumeric characters or hyphens.")]
    )
    is_active = models.BooleanField(default=True)
    features = JSONField(
        default=dict, 
        blank=True, 
        help_text="JSON mapping of enabled platform features: {'max_tables': 10, 'exports_enabled': true}"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tenant"
        verbose_name_plural = "Tenants"
        indexes = [
            models.Index(fields=['subdomain']),
        ]

    def __str__(self):
        return f"{self.name} ({self.subdomain})"


class UserProfile(models.Model):
    """
    Extension of the Django User model holding platform-specific roles
    and hierarchical relationship trees.
    """
    ROLE_CHOICES = [
        ('PRO_USER', 'System Super Admin'),
        ('ADMIN', 'Organization Admin'),
        ('OPERATOR', 'Assigned Operator'),
        ('CLIENT', 'Organization Owner'),
        ('ASSISTANT', 'Client Assistant'),
        ('GUEST', 'Guest Sandbox User')
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    tenant = models.ForeignKey(
        Tenant, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='user_profiles'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    
    # Hierarchical Parent Relationship:
    # - ADMINs manage OPERATORs
    # - CLIENTs manage ASSISTANTs & GUESTs
    managed_by = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='managed_users',
        help_text="Hierarchical supervisor: ADMIN manages OPERATORs, CLIENT manages ASSISTANTs."
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
        indexes = [
            models.Index(fields=['tenant', 'role']),
            models.Index(fields=['managed_by']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.role}"

    def clean(self):
        super().clean()
        if self.managed_by:
            # Prevent self-management
            if self.managed_by_id == self.id or self.managed_by == self:
                raise ValidationError("A user profile cannot manage itself.")
                
            supervisor_role = self.managed_by.role
            if self.role == 'OPERATOR' and supervisor_role != 'ADMIN':
                raise ValidationError("Operators can only be managed by Admins.")
            if self.role in ['ASSISTANT', 'GUEST'] and supervisor_role != 'CLIENT':
                raise ValidationError("Assistants and Guests can only be managed by Clients.")
            if self.role in ['PRO_USER', 'ADMIN', 'CLIENT']:
                raise ValidationError("Super Admins, Admins, and Clients cannot have managers.")


class OperatorAssignment(models.Model):
    """
    Maps Operators to specific Clients they are authorized to work for.
    Managed by Tenant Admins.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operator = models.ForeignKey(
        UserProfile, 
        on_delete=models.CASCADE, 
        limit_choices_to={'role': 'OPERATOR'},
        related_name='client_assignments'
    )
    client = models.ForeignKey(
        UserProfile, 
        on_delete=models.CASCADE, 
        limit_choices_to={'role': 'CLIENT'},
        related_name='operator_assignments'
    )
    assigned_by = models.ForeignKey(
        UserProfile, 
        on_delete=models.SET_NULL, 
        null=True, 
        limit_choices_to={'role': 'ADMIN'},
        related_name='created_operator_assignments'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Operator Assignment"
        verbose_name_plural = "Operator Assignments"
        unique_together = ('operator', 'client')
        indexes = [
            models.Index(fields=['operator', 'client']),
        ]

    def __str__(self):
        return f"Operator {self.operator.user.username} -> Client {self.client.user.username}"


# ==========================================
# 2. DYNAMIC TABLE & FIELDS SCHEMA
# ==========================================

class DynamicTable(models.Model):
    """
    Dynamic tables created inside tenants, belonging to specific client users.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='tables')
    client = models.ForeignKey(
        UserProfile, 
        on_delete=models.CASCADE, 
        limit_choices_to={'role': 'CLIENT'},
        related_name='tables'
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dynamic Table"
        verbose_name_plural = "Dynamic Tables"
        unique_together = ('tenant', 'slug')
        indexes = [
            models.Index(fields=['tenant', 'slug']),
            models.Index(fields=['client']),
        ]

    def __str__(self):
        return f"{self.name} (Tenant: {self.tenant.name})"


class TableField(models.Model):
    """
    Represents metadata for a column inside a DynamicTable.
    Key represents the key name stored in the CardRecord JSONB.
    """
    FIELD_TYPES = [
        ('TEXT', 'Text'),
        ('NUMBER', 'Number'),
        ('DATE', 'Date'),
        ('IMAGE', 'Image'),
        ('SELECT', 'Dropdown Select'),
        ('BOOLEAN', 'Boolean')
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    table = models.ForeignKey(DynamicTable, on_delete=models.CASCADE, related_name='fields')
    name = models.CharField(max_length=255, help_text="Friendly column name (e.g. Employee ID)")
    key = models.CharField(
        max_length=63, 
        validators=[RegexValidator(r'^[a-z0-9_]+$', message="Key must be alphanumeric and snake_case.")],
        help_text="Database key stored in the jsonb field (e.g. employee_id)"
    )
    type = models.CharField(max_length=15, choices=FIELD_TYPES)
    config = JSONField(
        default=dict, 
        blank=True, 
        help_text="Configuration values like select choices: {'choices': ['A', 'B']}, min/max validators"
    )
    is_required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0, help_text="Index order for UI grid display")

    class Meta:
        verbose_name = "Table Field"
        verbose_name_plural = "Table Fields"
        unique_together = ('table', 'key')
        ordering = ['order']

    def __str__(self):
        return f"{self.table.name} -> {self.name} ({self.type})"


# ==========================================
# 3. CARD RECORDS & WORKFLOW LOGS
# ==========================================

class CardRecord(models.Model):
    """
    Primary transactional table representing a dynamic card layout record.
    Dynamic column attributes are stored within the JSONB 'data' field.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('VERIFIED', 'Verified'),
        ('APPROVED', 'Approved'),
        ('DOWNLOADED', 'Downloaded'),
        ('DELETED', 'Deleted')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    table = models.ForeignKey(DynamicTable, on_delete=models.CASCADE, related_name='records')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    data = JSONField(default=dict, help_text="Stores dynamic fields matched with TableField.key")
    images = JSONField(
        default=dict, 
        blank=True, 
        help_text="Maps image TableField.key -> {'original_path': '...', 'thumbnail_path': '...'}"
    )
    version = models.PositiveIntegerField(default=1, help_text="Used for optimistic concurrency checks.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Card Record"
        verbose_name_plural = "Card Records"
        indexes = [
            models.Index(fields=['table', 'status']),
            models.Index(name='card_record_data_gin_idx', fields=['data'], opclasses=['jsonb_path_ops'])
        ]

    def __str__(self):
        return f"Card {self.id} Status: {self.status}"


class WorkflowLog(models.Model):
    """
    Tracks state transitions of CardRecords.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.ForeignKey(CardRecord, on_delete=models.CASCADE, related_name='workflow_logs')
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Workflow Log"
        verbose_name_plural = "Workflow Logs"
        ordering = ['-created_at']

    def clean(self):
        super().clean()
        if self.from_status == self.to_status:
            raise ValidationError("Status must change in a transition.")


# ==========================================
# 4. BACKGROUND JOBS SYSTEM
# ==========================================

class Job(models.Model):
    """
    Tracks background tasks orchestrated by Celery.
    Includes validation phases for uploads and JSON payloads for execution.
    """
    JOB_TYPES = [
        ('IMPORT_XLSX', 'Create Table From Excel'),
        ('IMPORT_XLSX_ZIP', 'Import Data + Zip Images'),
        ('REUPLOAD_IMAGES', 'Bulk Zip Image Re-upload'),
        ('EXPORT_PDF', 'Export PDF Collection'),
        ('EXPORT_DOCX', 'Export Word Files'),
        ('EXPORT_XLSX', 'Export Data Excel'),
        ('EXPORT_ZIP', 'Export Card Zip Bundle')
    ]
    
    STATUS_CHOICES = [
        ('QUEUED', 'Queued'),
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    job_type = models.CharField(max_length=30, choices=JOB_TYPES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='QUEUED')
    progress = models.PositiveIntegerField(default=0, help_text="Task progress percentage (0-100)")
    
    # Payload storing variable configurations for workers
    payload = JSONField(
        default=dict, 
        blank=True, 
        help_text="Task parameters. Example: {'table_id': '...', 'export_type': 'pdf'}"
    )
    
    result_url = models.URLField(max_length=512, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Job"
        verbose_name_plural = "Jobs"
        indexes = [
            models.Index(fields=['tenant', 'status']),
        ]

    def __str__(self):
        return f"Job {self.job_type} - {self.status}"


class JobLog(models.Model):
    """
    Logs generated during job phases.
    Useful for multi-phase validations (e.g. Phase 1: Validate XLSX, Phase 2: Validate ZIP).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='logs')
    message = models.CharField(max_length=512)
    level = models.CharField(max_length=10, default='INFO')  # INFO, WARNING, ERROR
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Job Log"
        verbose_name_plural = "Job Logs"
        ordering = ['timestamp']


# ==========================================
# 5. SANDBOX ENGINE MODELS (GUEST SESSIONS)
# ==========================================

class SandboxSession(models.Model):
    """
    Active sandboxed environment for GUEST users.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sandbox Session"
        verbose_name_plural = "Sandbox Sessions"
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]


class SandboxDelta(models.Model):
    """
    Aggregated writes/deltas buffered for a GUEST sandbox session.
    Keeps production clean until session commit.
    """
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(SandboxSession, on_delete=models.CASCADE, related_name='deltas')
    record = models.ForeignKey(CardRecord, on_delete=models.CASCADE, null=True, blank=True)
    table = models.ForeignKey(DynamicTable, on_delete=models.CASCADE)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    delta_data = JSONField(
        default=dict, 
        blank=True, 
        help_text="Key-value modifications to merge into CardRecord.data on commit"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sandbox Delta"
        verbose_name_plural = "Sandbox Deltas"


# ==========================================
# 6. SYSTEM AUDIT LOG MODEL
# ==========================================

class AuditLog(models.Model):
    """
    Write-only historical audit records for high-value operations.
    Supports impersonation tracking.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    impersonator = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='impersonated_audit_logs',
        help_text="PRO_USER acting on behalf of the organization user."
    )
    action = models.CharField(max_length=63)  # E.g. CARD_CREATE, EXPORT_PDF, IMPERSONATE_START
    target_model = models.CharField(max_length=63)
    target_id = models.UUIDField(null=True, blank=True)
    payload = JSONField(default=dict, blank=True, help_text="Log attributes excluding credentials")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'action']),
            models.Index(fields=['target_model', 'target_id']),
            models.Index(fields=['created_at']),
        ]
