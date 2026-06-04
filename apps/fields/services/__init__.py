from apps.fields.models import Field

class FieldService:
    @staticmethod
    def create_field(table_id: str, name: str, type: str, is_unique: bool=False, is_required: bool=False, default_value=None, validation_rules=None, display_order: int=0, created_by=None) -> Field:
        if validation_rules is None:
            validation_rules = {}
            
        field = Field.objects.create(
            table_id=table_id,
            name=name,
            type=type,
            is_unique=is_unique,
            is_required=is_required,
            default_value=default_value,
            validation_rules=validation_rules,
            display_order=display_order
        )
        return field

    @staticmethod
    def update_field(field: Field, name: str=None, is_required: bool=None, display_order: int=None, updated_by=None) -> Field:
        # Note: Type changes are allowed. But let's assume we update basic fields.
        if name is not None:
            field.name = name
        if is_required is not None:
            field.is_required = is_required
        if display_order is not None:
            field.display_order = display_order
        field.save()
        return field

    @staticmethod
    def delete_field(field: Field, deleted_by=None):
        field.soft_delete()
