import hmac
import hashlib
from typing import Dict, Any, List
from django.db import transaction
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.auth.models import User

from core.models import Tenant, UserProfile, DynamicTable, CardRecord, TableField
from core.enterprise.models import (
    FeatureFlag, TenantFeatureOverride, License, SoftwareRelease,
    ImpersonationSession, MediaFile, Notification, SavedSearchQuery,
    BulkOperation, TableTemplate, ImportSession, ExportSession,
    SystemSettings, DesktopDevice, SyncChangeLog
)
from core.enterprise.bus import EventBusService

# =====================================================================
# 1. FEATURE MANAGEMENT SERVICE
# =====================================================================

class FeatureService:
    @staticmethod
    def is_feature_enabled(tenant: Tenant, feature_key: str) -> bool:
        """
        Calculates if a feature flag is enabled for the specified tenant.
        Loads from override cache or falls back to global flag.
        """
        # Attempt to locate Tenant specific override
        override = TenantFeatureOverride.objects.select_related('feature').filter(
            tenant=tenant, 
            feature__key=feature_key
        ).first()
        
        if override:
            return override.is_enabled
            
        # Fallback to global feature configuration
        feature = FeatureFlag.objects.filter(key=feature_key).first()
        return feature.is_active if feature else False

    @staticmethod
    def set_override(tenant: Tenant, feature_key: str, enabled: bool, config: dict = None) -> TenantFeatureOverride:
        feature = FeatureFlag.objects.get(key=feature_key)
        override, created = TenantFeatureOverride.objects.update_or_create(
            tenant=tenant,
            feature=feature,
            defaults={'is_enabled': enabled, 'config_override': config or {}}
        )
        return override


# =====================================================================
# 2. LICENSE MANAGEMENT SERVICE
# =====================================================================

class LicenseService:
    @staticmethod
    def generate_signature(tenant_id: str, tier: str, max_users: int, max_tables: int, expires_at: str) -> str:
        """Generates tampering verification signature."""
        secret = settings.SECRET_KEY.encode('utf-8')
        payload = f"{tenant_id}:{tier}:{max_users}:{max_tables}:{expires_at}".encode('utf-8')
        return hmac.new(secret, payload, hashlib.sha256).hexdigest()

    @classmethod
    @transaction.atomic
    def provision_license(cls, tenant: Tenant, tier: str, max_users: int, max_tables: int, expires_at: timezone.datetime) -> License:
        signature = cls.generate_signature(
            str(tenant.id), tier, max_users, max_tables, expires_at.isoformat()
        )
        license_obj, created = License.objects.update_or_create(
            tenant=tenant,
            defaults={
                'tier': tier,
                'max_users': max_users,
                'max_tables': max_tables,
                'starts_at': timezone.now(),
                'expires_at': expires_at,
                'cryptographic_signature': signature
            }
        )
        EventBusService.emit(str(tenant.id), "license.provisioned", {"tier": tier})
        return license_obj

    @classmethod
    def verify_license_integrity(cls, license_obj: License) -> bool:
        """Checks signature cryptographic matching to detect tampering."""
        expected = cls.generate_signature(
            str(license_obj.tenant_id),
            license_obj.tier,
            license_obj.max_users,
            license_obj.max_tables,
            license_obj.expires_at.isoformat() if hasattr(license_obj.expires_at, 'isoformat') else str(license_obj.expires_at)
        )
        return hmac.compare_digest(license_obj.cryptographic_signature, expected)


# =====================================================================
# 3. SOFTWARE VERSION MANAGEMENT SERVICE
# =====================================================================

class VersionService:
    @staticmethod
    def is_client_compatible(client_type: str, client_version: str) -> bool:
        """Checks version compatibilities from release ledger."""
        latest_release = SoftwareRelease.objects.filter(is_active=True).first()
        if not latest_release:
            return True
            
        def parse_version(v_str):
            return tuple(map(int, (v_str.split('.'))))
            
        try:
            current = parse_version(client_version)
            if client_type == 'desktop':
                required = parse_version(latest_release.min_desktop_version)
            else:
                required = parse_version(latest_release.min_mobile_version)
            return current >= required
        except ValueError:
            return False


# =====================================================================
# 4. IMPERSONATION SERVICE
# =====================================================================

class ImpersonationService:
    @staticmethod
    @transaction.atomic
    def start_session(impersonator: User, impersonated_username: str, reason: str, ip: str = None) -> ImpersonationSession:
        if not impersonator.profile.role == 'PRO_USER':
            raise PermissionDenied("Only PRO_USERs can initiate impersonation sessions.")
            
        impersonated_user = User.objects.get(username=impersonated_username)
        
        # End any dangling active sessions for this impersonator
        ImpersonationSession.objects.filter(impersonator=impersonator, ended_at__isnull=True).update(
            ended_at=timezone.now()
        )
        
        session = ImpersonationSession.objects.create(
            impersonator=impersonator,
            impersonated=impersonated_user,
            reason=reason,
            ip_address=ip
        )
        
        # Emit Impersonation Start Event
        EventBusService.emit(
            str(impersonated_user.profile.tenant_id or ""), 
            "security.impersonation_started", 
            {"impersonator": impersonator.username, "impersonated": impersonated_username}
        )
        return session

    @staticmethod
    def end_session(session_id: str) -> None:
        session = ImpersonationSession.objects.get(id=session_id)
        session.ended_at = timezone.now()
        session.save()


# =====================================================================
# 5. MEDIAFILE DOMAIN SERVICE
# =====================================================================

class MediaFileService:
    @staticmethod
    def register_asset(tenant: Tenant, uploader: User, name: str, size: int, mime: str, path: str, url: str) -> MediaFile:
        return MediaFile.objects.create(
            tenant=tenant,
            uploaded_by=uploader,
            file_name=name,
            file_size=size,
            mime_type=mime,
            storage_path=path,
            public_url=url
        )


# =====================================================================
# 6. NOTIFICATION DOMAIN SERVICE
# =====================================================================

class NotificationService:
    @staticmethod
    def send_direct_notification(recipient: User, title: str, body: str, msg_type: str = 'SYSTEM') -> Notification:
        notif = Notification.objects.create(
            recipient=recipient,
            title=title,
            body=body,
            notification_type=msg_type
        )
        
        # Publish notification using Redis Pub/Sub for realtime toast notification delivery
        from django.core.cache import cache
        try:
            r = cache.client.get_client()
            r.publish(f"notifications:user:{recipient.id}", json.dumps({
                "id": str(notif.id),
                "title": title,
                "body": body,
                "type": msg_type
            }))
        except Exception:
            pass
            
        return notif


# =====================================================================
# 7. SEARCH DOMAIN SERVICE
# =====================================================================

class SearchService:
    @staticmethod
    def execute_query(table: DynamicTable, filter_payload: dict) -> List[CardRecord]:
        """
        Performs optimized key searches using PostgreSQL JSONB filters on table records.
        """
        queryset = CardRecord.objects.filter(table=table).exclude(status='DELETED')
        
        # Matches keys directly via JSONB containment lookup
        if filter_payload:
            queryset = queryset.filter(data__contains=filter_payload)
            
        return list(queryset)


# =====================================================================
# 8. BULK OPERATIONS DOMAIN SERVICE
# =====================================================================

class BulkOperationService:
    @staticmethod
    @transaction.atomic
    def trigger_bulk_operation(tenant: Tenant, user: User, action_type: str, filter_query: dict, update_payload: dict = None) -> BulkOperation:
        # Check license limits before executing massive writes
        license_obj = getattr(tenant, 'license', None)
        if license_obj and timezone.now() > license_obj.expires_at:
            raise ValidationError("License is expired. Action blocked.")
            
        bulk_op = BulkOperation.objects.create(
            tenant=tenant,
            user=user,
            action_type=action_type,
            status='PENDING',
            payload={
                "filter_query": filter_query,
                "update_payload": update_payload or {}
            }
        )
        
        # Schedule background execution task
        transaction.on_commit(
            lambda: BulkOperationService.run_bulk_op_task.delay(str(bulk_op.id))
        )
        return bulk_op

    @staticmethod
    @transaction.atomic
    def process_operation(bulk_op_id: str):
        bulk_op = BulkOperation.objects.select_for_update().get(id=bulk_op_id)
        bulk_op.status = 'RUNNING'
        bulk_op.save()
        
        try:
            filter_query = bulk_op.payload.get('filter_query', {})
            update_payload = bulk_op.payload.get('update_payload', {})
            
            # Database vendor check for SQLite compatibility
            from django.db import connection
            if connection.vendor == 'sqlite':
                # Fetch candidate records and filter in python memory
                candidates = CardRecord.objects.select_for_update().filter(
                    table__tenant=bulk_op.tenant
                ).exclude(status='DELETED')
                matching_ids = []
                for rec in candidates:
                    if all(rec.data.get(k) == v for k, v in filter_query.items()):
                        matching_ids.append(rec.id)
                records = CardRecord.objects.select_for_update().filter(id__in=matching_ids)
            else:
                # Optimized PG JSONB GIN query
                records = CardRecord.objects.select_for_update().filter(
                    table__tenant=bulk_op.tenant,
                    data__contains=filter_query
                ).exclude(status='DELETED')
            
            bulk_op.total_records = records.count()
            bulk_op.save()
            
            processed = 0
            for record in records:
                if bulk_op.action_type == 'BULK_DELETE':
                    record.status = 'DELETED'
                elif bulk_op.action_type == 'BULK_STATUS_CHANGE':
                    record.status = update_payload.get('status', 'PENDING')
                elif bulk_op.action_type == 'BULK_FIELD_UPDATE':
                    record.data.update(update_payload.get('data', {}))
                    
                record.version += 1
                record.save()
                
                # Write to replication changelog for desktop clients sync
                SyncChangeLog.objects.create(
                    table=record.table,
                    record_id=record.id,
                    change_type='UPDATE' if bulk_op.action_type != 'BULK_DELETE' else 'DELETE',
                    version=record.version
                )
                
                processed += 1
                if processed % 50 == 0:
                    bulk_op.processed_records = processed
                    bulk_op.save()
                    
            bulk_op.status = 'COMPLETED'
            bulk_op.processed_records = processed
            bulk_op.save()
            
            # Notify owner user
            NotificationService.send_direct_notification(
                bulk_op.user, 
                "Bulk action complete", 
                f"Successfully updated {processed} records."
            )
            
        except Exception as e:
            bulk_op.status = 'FAILED'
            bulk_op.error_message = str(e)
            bulk_op.save()

# Task hook bindings
from celery import shared_task
@shared_task
def run_bulk_op_task_wrapper(bulk_op_id: str):
    BulkOperationService.process_operation(bulk_op_id)

BulkOperationService.run_bulk_op_task = run_bulk_op_task_wrapper


# =====================================================================
# 9. TABLE TEMPLATE DOMAIN SERVICE
# =====================================================================

class TemplateService:
    @staticmethod
    @transaction.atomic
    def instantiate_table(tenant: Tenant, client: UserProfile, template_id: str, table_name: str) -> DynamicTable:
        template = TableTemplate.objects.get(id=template_id)
        
        # Instantiate table via TableService
        from core.services.table import TableService
        table = TableService.create_table(
            tenant=tenant,
            client=client,
            name=table_name,
            fields_schema=template.fields_schema
        )
        return table


# =====================================================================
# 10. IMPORT SESSION DOMAIN SERVICE
# =====================================================================

class ImportSessionService:
    @staticmethod
    def initiate_import(tenant: Tenant, table: DynamicTable, user: User, xlsx_file: MediaFile, zip_file: MediaFile = None) -> ImportSession:
        return ImportSession.objects.create(
            tenant=tenant,
            table=table,
            user=user,
            xlsx_file=xlsx_file,
            zip_file=zip_file,
            status='INIT'
        )


# =====================================================================
# 11. EXPORT SESSION DOMAIN SERVICE
# =====================================================================

class ExportSessionService:
    @staticmethod
    def initiate_export(tenant: Tenant, table: DynamicTable, user: User, format_type: str) -> ExportSession:
        return ExportSession.objects.create(
            tenant=tenant,
            table=table,
            user=user,
            format=format_type,
            status='PENDING'
        )


# =====================================================================
# 12. SETTINGS DOMAIN SERVICE
# =====================================================================

class SettingsService:
    @staticmethod
    def check_ip_allowed(tenant: Tenant, client_ip: str) -> bool:
        settings_obj = SystemSettings.objects.filter(tenant=tenant).first()
        if not settings_obj or not settings_obj.allowed_ip_ranges:
            return True
            
        import ipaddress
        for cidr in settings_obj.allowed_ip_ranges:
            try:
                if ipaddress.ip_address(client_ip) in ipaddress.ip_network(cidr):
                    return True
            except ValueError:
                continue
        return False


# =====================================================================
# 13. DESKTOP SYNC DOMAIN SERVICE
# =====================================================================

class DesktopSyncService:
    @staticmethod
    def register_device(tenant: Tenant, user: User, dev_uid: str, platform: str, app_ver: str) -> DesktopDevice:
        device, created = DesktopDevice.objects.update_or_create(
            device_identifier=dev_uid,
            defaults={
                'tenant': tenant,
                'user': user,
                'os_platform': platform,
                'app_version': app_ver,
                'last_sync_at': timezone.now()
            }
        )
        return device

    @staticmethod
    def fetch_sync_changes(table: DynamicTable, last_sync_time: timezone.datetime) -> List[Dict[str, Any]]:
        """
        Fetches database edits logs since client's last sync event timestamp.
        """
        logs = SyncChangeLog.objects.filter(
            table=table,
            modified_at__gt=last_sync_time
        ).order_by('modified_at')
        
        results = []
        for log in logs:
            results.append({
                "record_id": str(log.record_id),
                "change_type": log.change_type,
                "version": log.version,
                "timestamp": log.modified_at.isoformat()
            })
        return results
