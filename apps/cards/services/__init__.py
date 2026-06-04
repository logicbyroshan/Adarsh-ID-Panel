import hashlib
from typing import Dict, Any
from django.db import transaction, IntegrityError
from apps.cards.models import Card, CardUniqueValue
from apps.fields.models import Field
from rest_framework.exceptions import ValidationError

class StaleWriteError(Exception):
    pass

class CardService:
    @staticmethod
    def _enforce_unique_fields(table_id: str, card_id: str, data: Dict[str, Any]):
        unique_fields = Field.objects.filter(table_id=table_id, is_unique=True, is_deleted=False)
        for field in unique_fields:
            field_str_id = str(field.id)
            if field_str_id in data:
                value = data[field_str_id]
                if value is not None:
                    # Hash the value to ensure it fits in max_length=255 and index
                    value_hash = hashlib.sha256(str(value).encode('utf-8')).hexdigest()
                    try:
                        CardUniqueValue.objects.update_or_create(
                            card_id=card_id,
                            field_id=field.id,
                            defaults={'table_id': table_id, 'value_hash': value_hash}
                        )
                    except IntegrityError:
                        raise ValidationError(f"Unique constraint failed for field: {field.name}")

    @staticmethod
    @transaction.atomic
    def create_card(table, organization_id: str, data: Dict[str, Any], created_by=None) -> Card:
        # Generate a display ID (simple implementation)
        display_id = f"TBL-{Card.objects.filter(table=table).count() + 1}"
        
        card = Card.objects.create(
            table=table,
            organization_id=organization_id,
            display_id=display_id,
            data=data,
            created_by=created_by
        )
        
        CardService._enforce_unique_fields(str(table.id), str(card.id), data)
        return card

    @staticmethod
    @transaction.atomic
    def update_card(card: Card, data_update: Dict[str, Any], expected_version: int, updated_by=None) -> Card:
        if card.version != expected_version:
            raise StaleWriteError("Card has been modified by another user.")
            
        # Spreadsheet editing: targeted JSONB update (merge)
        new_data = dict(card.data)
        new_data.update(data_update)
        
        # Optimistic locking update
        updated_count = Card.objects.filter(id=card.id, version=expected_version).update(
            data=new_data,
            version=expected_version + 1,
            updated_by=updated_by
        )
        
        if updated_count == 0:
            raise StaleWriteError("Card has been modified by another user.")
            
        card.refresh_from_db()
        CardService._enforce_unique_fields(str(card.table_id), str(card.id), new_data)
        return card

    @staticmethod
    def delete_card(card: Card, deleted_by=None):
        card.soft_delete(user=deleted_by)
        # Remove unique values to free them up
        CardUniqueValue.objects.filter(card=card).delete()
