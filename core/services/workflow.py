from typing import List, Dict
from django.db import transaction
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from core.models import CardRecord, WorkflowLog

class WorkflowService:
    """
    Enforces status transitions, audit logs, and status locks.
    """
    
    # Allowed state movements (ANY -> DELETED is handled dynamically)
    TRANSITION_MATRIX = {
        'PENDING': ['VERIFIED', 'DELETED'],
        'VERIFIED': ['APPROVED', 'DELETED'],
        'APPROVED': ['DOWNLOADED', 'DELETED'],
        'DOWNLOADED': ['DELETED'],
        'DELETED': ['PENDING'],  # Restoring resets to pending status
    }

    @classmethod
    def can_transition(cls, current_status: str, target_status: str) -> bool:
        """
        Checks if a status transition is valid.
        """
        if current_status == target_status:
            return True
        return target_status in cls.TRANSITION_MATRIX.get(current_status, [])

    @transaction.atomic
    def execute_transition(self, record_id: str, target_status: str, user: User, reason: str = None) -> CardRecord:
        """
        Attempts to update the state of a single card record.
        """
        record = CardRecord.objects.select_for_update().get(id=record_id)
        current_status = record.status
        
        if not self.can_transition(current_status, target_status):
            raise ValidationError(
                f"Invalid status transition: Cannot change status from {current_status} to {target_status}."
            )
            
        record.status = target_status
        record.version += 1
        record.save()
        
        # Log to transition audit history
        WorkflowLog.objects.create(
            record=record,
            from_status=current_status,
            to_status=target_status,
            user=user,
            reason=reason
        )
        
        return record

    @transaction.atomic
    def bulk_transition(self, record_ids: List[str], target_status: str, user: User) -> Dict[str, List[str]]:
        """
        Transitions multiple records in a single transactional batch.
        Returns keys for successful transitions and failures.
        """
        records = CardRecord.objects.select_for_update().filter(id__in=record_ids)
        successes = []
        failures = []
        
        for record in records:
            current_status = record.status
            if self.can_transition(current_status, target_status):
                record.status = target_status
                record.version += 1
                record.save()
                
                WorkflowLog.objects.create(
                    record=record,
                    from_status=current_status,
                    to_status=target_status,
                    user=user,
                    reason="Bulk operation transition"
                )
                successes.append(str(record.id))
            else:
                failures.append(str(record.id))
                
        return {"success_ids": successes, "failed_ids": failures}
