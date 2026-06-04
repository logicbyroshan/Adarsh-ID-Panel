import uuid
from django.db import models
from django.core.serializers.json import DjangoJSONEncoder

class AuditEvent(models.TextChoices):
    CREATE_CLIENT = 'CREATE_CLIENT', 'Create Client'
    DELETE_CLIENT = 'DELETE_CLIENT', 'Delete Client'
    CREATE_ASSISTANT = 'CREATE_ASSISTANT', 'Create Assistant'
    DELETE_ASSISTANT = 'DELETE_ASSISTANT', 'Delete Assistant'
    CREATE_OPERATOR = 'CREATE_OPERATOR', 'Create Operator'
    ASSIGN_OPERATOR = 'ASSIGN_OPERATOR', 'Assign Operator'
    PERMISSION_CHANGE = 'PERMISSION_CHANGE', 'Permission Change'
    IMPERSONATION = 'IMPERSONATION', 'Impersonation'

class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=50, choices=AuditEvent.choices)
    actor = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, related_name='audit_logs_created')
    target_user = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs_targeted')
    target_organization = models.ForeignKey('organizations.Organization', on_delete=models.SET_NULL, null=True, blank=True)
    details = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'auditlogs_audit_log'
        indexes = [
            models.Index(fields=['event_type']),
            models.Index(fields=['created_at']),
        ]
