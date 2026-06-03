from typing import Any, Dict, Optional
from django.db import transaction
from django.core.exceptions import ValidationError
from core.models import CardRecord, DynamicTable, UserProfile
from core.validators import DynamicSchemaValidator
from core.services.presence import PresenceService

class CardService:
    """
    Handles lifecycle operations for CardRecords, including dynamic validations,
    optimistic concurrency, and cell locks.
    """
    
    @staticmethod
    @transaction.atomic
    def create_record(table: DynamicTable, data: Dict[str, Any], images: Optional[Dict[str, Any]] = None) -> CardRecord:
        """
        Validates data against the table schema and creates a new CardRecord.
        """
        # Run dynamic schema validator
        DynamicSchemaValidator.validate(data, table)
        
        record = CardRecord.objects.create(
            table=table,
            data=data,
            images=images or {},
            status='PENDING'
        )
        return record

    @staticmethod
    @transaction.atomic
    def update_record(record_id: str, data: Dict[str, Any], client_version: int, images: Optional[Dict[str, Any]] = None) -> CardRecord:
        """
        Performs full update on CardRecord. Enforces optimistic concurrency locks.
        """
        record = CardRecord.objects.select_for_update().get(id=record_id)
        
        # Optimistic concurrency check
        if record.version != client_version:
            raise ValidationError(
                "Conflict detected: This record has been updated by another session. Please reload and try again."
            )
            
        # Validate merged payload
        merged_data = {**record.data, **data}
        DynamicSchemaValidator.validate(merged_data, record.table)
        
        record.data = merged_data
        if images:
            record.images.update(images)
        record.version += 1
        record.save()
        
        return record

    @staticmethod
    @transaction.atomic
    def update_cell(record_id: str, field_key: str, value: Any, client_version: int, user_id: str) -> CardRecord:
        """
        Updates a single cell. Validates lease cell locks inside Redis to prevent editing collisions.
        """
        # Verify if the user owns the editing lock inside Redis
        # Note: If no lock exists, try to acquire it first
        lock_acquired = PresenceService.acquire_cell_lock(record_id, field_key, user_id)
        if not lock_acquired:
            raise ValidationError("Collision block: Another user is currently editing this cell.")
            
        try:
            record = CardRecord.objects.select_for_update().get(id=record_id)
            
            if record.version != client_version:
                raise ValidationError("Conflict: This row has changed since you opened it.")
                
            # Perform schema lookup and type validation
            field = record.table.fields.filter(key=field_key).first()
            if not field:
                raise ValidationError(f"Field '{field_key}' does not exist.")
                
            # Run schema validator on candidate update
            temp_data = record.data.copy()
            temp_data[field_key] = value
            DynamicSchemaValidator.validate(temp_data, record.table)
            
            # Save cell edit
            record.data[field_key] = value
            record.version += 1
            record.save()
            
            return record
        finally:
            # Release lock in Redis
            PresenceService.release_cell_lock(record_id, field_key, user_id)

    @staticmethod
    @transaction.atomic
    def soft_delete_record(record_id: str) -> None:
        """
        Sets the status of a CardRecord to DELETED.
        """
        record = CardRecord.objects.select_for_update().get(id=record_id)
        record.status = 'DELETED'
        record.version += 1
        record.save()
