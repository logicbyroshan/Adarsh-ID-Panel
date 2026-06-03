from typing import List, Dict, Any
from django.db import transaction
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from core.models import Tenant, UserProfile, DynamicTable, TableField

class TableService:
    """
    Manages DynamicTable creations and modifications.
    """
    
    @staticmethod
    @transaction.atomic
    def create_table(tenant: Tenant, client: UserProfile, name: str, fields_schema: List[Dict[str, Any]]) -> DynamicTable:
        """
        Initializes a table schema and its fields.
        """
        slug = slugify(name)
        if DynamicTable.objects.filter(tenant=tenant, slug=slug).exists():
            raise ValidationError(f"Table with name '{name}' already exists in this tenant.")
            
        table = DynamicTable.objects.create(
            tenant=tenant,
            client=client,
            name=name,
            slug=slug
        )
        
        # Build schema definitions
        for order, field in enumerate(fields_schema):
            TableField.objects.create(
                table=table,
                name=field['name'],
                key=field['key'],
                type=field['type'],
                config=field.get('config', {}),
                is_required=field.get('is_required', False),
                order=order
            )
            
        return table

    @staticmethod
    @transaction.atomic
    def update_table_fields(table: DynamicTable, fields_schema: List[Dict[str, Any]]) -> None:
        """
        Updates the table columns schema.
        Note: Existing fields not in the schema are deleted, and new fields are added.
        """
        existing_fields = {f.key: f for f in table.fields.all()}
        new_keys = {f['key'] for f in fields_schema}
        
        # 1. Delete fields that were removed
        fields_to_delete = [f for key, f in existing_fields.items() if key not in new_keys]
        for field in fields_to_delete:
            field.delete()
            
        # 2. Add or update fields
        for order, f_data in enumerate(fields_schema):
            key = f_data['key']
            if key in existing_fields:
                # Update configuration details
                field = existing_fields[key]
                field.name = f_data['name']
                field.type = f_data['type']
                field.config = f_data.get('config', {})
                field.is_required = f_data.get('is_required', False)
                field.order = order
                field.save()
            else:
                # Create a new column definition
                TableField.objects.create(
                    table=table,
                    name=f_data['name'],
                    key=key,
                    type=f_data['type'],
                    config=f_data.get('config', {}),
                    is_required=f_data.get('is_required', False),
                    order=order
                )
