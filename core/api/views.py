from rest_framework import viewsets, status, mixins
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from django.shortcuts import get_object_or_404
from django.db import transaction

class StandardResultsSetPagination(LimitOffsetPagination):
    default_limit = 100
    max_limit = 1000


from core.models import Tenant, DynamicTable, CardRecord, Job, OperatorAssignment
from core.api.serializers import (
    DynamicTableSerializer, CardRecordSerializer, 
    JobSerializer, OperatorAssignmentSerializer
)
from core.api.permissions import HasHierarchicalRolePermission
from core.services.card import CardService
from core.services.table import TableService
from core.services.workflow import WorkflowService
from core.services.presence import PresenceService

# ==========================================
# 1. DYNAMIC TABLE VIEWSET
# ==========================================

class DynamicTableViewSet(viewsets.ModelViewSet):
    serializer_class = DynamicTableSerializer
    permission_classes = [HasHierarchicalRolePermission]
    lookup_field = 'pk'

    def get_queryset(self):
        profile = self.request.user.profile
        if profile.role == 'PRO_USER':
            return DynamicTable.objects.all()
        return DynamicTable.objects.filter(tenant=profile.tenant)

    def perform_create(self, serializer):
        profile = self.request.user.profile
        # Tenant ADMIN creates table and assigns it to a client user
        client_id = self.request.data.get('client')
        if profile.role == 'ADMIN' and client_id:
            from core.models import UserProfile
            client = get_object_or_404(UserProfile, id=client_id, role='CLIENT')
        else:
            client = profile  # Defaults to Client profile creating their own table
            
        serializer.save(tenant=profile.tenant, client=client)


# ==========================================
# 2. CARD RECORDS VIEWSET
# ==========================================

class CardRecordViewSet(viewsets.ModelViewSet):
    serializer_class = CardRecordSerializer
    permission_classes = [HasHierarchicalRolePermission]
    pagination_class = StandardResultsSetPagination
    lookup_field = 'pk'

    def get_table(self):
        return get_object_or_404(DynamicTable, id=self.kwargs['table_pk'])

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['table'] = self.get_table()
        return context

    def get_queryset(self):
        table = self.get_table()
        profile = self.request.user.profile
        
        # sandbox read redirection for guest users
        if profile.role == 'GUEST':
            from core.services.sandbox import SandboxService, SandboxSession
            session, _ = SandboxSession.objects.get_or_create(user=self.request.user, is_active=True)
            sandbox = SandboxService(session)
            return sandbox.get_records(table)
            
        return CardRecord.objects.filter(table=table).exclude(status='DELETED')

    def perform_create(self, serializer):
        table = self.get_table()
        profile = self.request.user.profile
        
        # sandbox write redirection for guest users
        if profile.role == 'GUEST':
            from core.services.sandbox import SandboxService, SandboxSession
            session, _ = SandboxSession.objects.get_or_create(user=self.request.user, is_active=True)
            sandbox = SandboxService(session)
            sandbox.write_change('CREATE', table, data=serializer.validated_data['data'])
        else:
            CardService.create_record(table, serializer.validated_data['data'])

    def perform_update(self, serializer):
        record = self.get_object()
        profile = self.request.user.profile
        
        if profile.role == 'GUEST':
            from core.services.sandbox import SandboxService, SandboxSession
            session, _ = SandboxSession.objects.get_or_create(user=self.request.user, is_active=True)
            sandbox = SandboxService(session)
            sandbox.write_change('UPDATE', record.table, record_id=str(record.id), data=serializer.validated_data['data'])
        else:
            CardService.update_record(
                record_id=str(record.id),
                data=serializer.validated_data['data'],
                client_version=serializer.validated_data.get('version', record.version)
            )

    def perform_destroy(self, instance):
        profile = self.request.user.profile
        if profile.role == 'GUEST':
            from core.services.sandbox import SandboxService, SandboxSession
            session, _ = SandboxSession.objects.get_or_create(user=self.request.user, is_active=True)
            sandbox = SandboxService(session)
            sandbox.write_change('DELETE', instance.table, record_id=str(instance.id))
        else:
            CardService.soft_delete_record(str(instance.id))

    # Heartbeat presence monitoring endpoint
    @action(detail=False, methods=['post'], url_path='heartbeat')
    def heartbeat(self, request, tenant_pk=None, table_pk=None):
        user_id = str(request.user.id)
        PresenceService.enter_table(table_pk, user_id)
        active_users = PresenceService.get_table_users(table_pk)
        return Response({"active_users": active_users})

    # Cell lease locking endpoint
    @action(detail=True, methods=['post'], url_path='lock-cell')
    def lock_cell(self, request, tenant_pk=None, table_pk=None, pk=None):
        field_key = request.data.get('field_key')
        if not field_key:
            return Response({"error": "field_key is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        success = PresenceService.acquire_cell_lock(pk, field_key, str(request.user.id))
        if success:
            return Response({"status": "locked"})
        return Response({"status": "conflict", "message": "Cell is currently locked by another user"}, status=status.HTTP_409_CONFLICT)

    # Workflow status transitions
    @action(detail=True, methods=['post'], url_path='transition')
    def transition(self, request, tenant_pk=None, table_pk=None, pk=None):
        target_status = request.data.get('target_status')
        reason = request.data.get('reason')
        if not target_status:
            return Response({"error": "target_status is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        workflow = WorkflowService()
        record = workflow.execute_transition(pk, target_status, request.user, reason)
        return Response(CardRecordSerializer(record).data)

    # Bulk status transitions
    @action(detail=False, methods=['post'], url_path='bulk-transition')
    def bulk_transition(self, request, tenant_pk=None, table_pk=None):
        record_ids = request.data.get('record_ids', [])
        target_status = request.data.get('target_status')
        if not record_ids or not target_status:
            return Response({"error": "record_ids and target_status are required"}, status=status.HTTP_400_BAD_REQUEST)
            
        workflow = WorkflowService()
        result = workflow.bulk_transition(record_ids, target_status, request.user)
        return Response(result)


# ==========================================
# 3. BACKGROUND JOBS VIEWSET
# ==========================================

class JobViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = JobSerializer
    permission_classes = [HasHierarchicalRolePermission]

    def get_queryset(self):
        profile = self.request.user.profile
        return Job.objects.filter(tenant=profile.tenant)

    def perform_create(self, serializer):
        profile = self.request.user.profile
        job = serializer.save(tenant=profile.tenant, user=self.request.user)
        
        # Trigger Celery Worker tasks based on job types
        if job.job_type == 'IMPORT_XLSX_ZIP':
            from core.tasks.imports import import_xlsx_zip_task
            transaction.on_commit(lambda: import_xlsx_zip_task.delay(str(job.id)))
        elif job.job_type == 'EXPORT_PDF':
            from core.tasks.exports import run_export_pipeline_task
            transaction.on_commit(lambda: run_export_pipeline_task.delay(str(job.id)))
