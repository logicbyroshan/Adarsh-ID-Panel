from typing import List
from django.db import transaction
from core.models import SandboxSession, SandboxDelta, CardRecord, DynamicTable

class SandboxService:
    """
    Manages isolated guest user operations. Write operations are buffered
    as delta records and merged into query lists on read.
    """

    def __init__(self, session: SandboxSession):
        self.session = session

    def get_records(self, table: DynamicTable) -> List[CardRecord]:
        """
        Retrieves all records for the given table merged with guest session deltas.
        """
        # Fetch base production database records
        base_records = list(CardRecord.objects.filter(table=table).exclude(status='DELETED'))
        
        # Fetch buffered sandbox changes for this session
        deltas = self.session.deltas.filter(table=table)
        
        # Build maps for processing
        deletes = set()
        updates = {}
        creates = []
        
        for delta in deltas:
            if delta.action == 'DELETE' and delta.record_id:
                deletes.add(delta.record_id)
            elif delta.action == 'UPDATE' and delta.record_id:
                updates[delta.record_id] = delta.delta_data
            elif delta.action == 'CREATE':
                creates.append(delta)
                
        # Merge changes into base record objects
        merged_records = []
        for r in base_records:
            if r.id in deletes:
                continue
                
            if r.id in updates:
                # Merge delta dictionary keys into record JSONB data
                merged_data = {**r.data, **updates[r.id]}
                r.data = merged_data
                
            merged_records.append(r)
            
        # Append mock records created inside this session
        for delta in creates:
            mock_record = CardRecord(
                id=delta.id,  # Map the sandbox ID as record primary key
                table=table,
                data=delta.delta_data,
                status='PENDING'
            )
            # Tag record to let frontend know it is a virtual sandbox record
            mock_record._is_sandbox_virtual = True
            merged_records.append(mock_record)
            
        return merged_records

    @transaction.atomic
    def write_change(self, action: str, table: DynamicTable, record_id: str = None, data: dict = None) -> SandboxDelta:
        """
        Buffers a create, update, or delete action inside the guest session.
        """
        if action == 'CREATE':
            return SandboxDelta.objects.create(
                session=self.session,
                table=table,
                action='CREATE',
                delta_data=data or {}
            )
            
        record = CardRecord.objects.get(id=record_id)
        
        if action == 'DELETE':
            # Remove any existing updates for this record to prevent clutter
            self.session.deltas.filter(record=record, action='UPDATE').delete()
            return SandboxDelta.objects.create(
                session=self.session,
                table=table,
                record=record,
                action='DELETE'
            )
            
        if action == 'UPDATE':
            # Check if there is an existing update delta
            delta, created = SandboxDelta.objects.get_or_create(
                session=self.session,
                table=table,
                record=record,
                action='UPDATE'
            )
            merged_data = {**delta.delta_data, **(data or {})}
            delta.delta_data = merged_data
            delta.save()
            return delta

    @transaction.atomic
    def commit(self) -> None:
        """
        Applies all buffered sandbox deltas to the master tables.
        """
        deltas = self.session.deltas.all().order_index('created_at')
        for delta in deltas:
            if delta.action == 'CREATE':
                CardRecord.objects.create(
                    table=delta.table,
                    data=delta.delta_data,
                    status='PENDING'
                )
            elif delta.action == 'UPDATE' and delta.record:
                record = delta.record
                record.data.update(delta.delta_data)
                record.version += 1
                record.save()
            elif delta.action == 'DELETE' and delta.record:
                record = delta.record
                record.status = 'DELETED'
                record.version += 1
                record.save()
                
        # Clear buffer
        self.session.deltas.all().delete()

    @transaction.atomic
    def discard(self) -> None:
        """
        Wipes out all buffered operations without committing.
        """
        self.session.deltas.all().delete()
