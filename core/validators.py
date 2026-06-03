import datetime
from django.core.exceptions import ValidationError
from core.models import DynamicTable, TableField

class DynamicSchemaValidator:
    """
    Validates dynamic JSONB record data against the schema defined in TableField.
    """
    
    @staticmethod
    def validate(data: dict, table: DynamicTable) -> None:
        fields = table.fields.all()
        errors = {}
        
        # Track defined keys to detect extra fields that are not in schema
        schema_keys = {field.key for field in fields}
        
        for field in fields:
            value = data.get(field.key)
            
            # Check is_required constraint
            if field.is_required:
                if value is None or str(value).strip() == "":
                    errors[field.key] = f"Field '{field.name}' is required."
                    continue
            
            # Skip validation if value is empty/null and not required
            if value is None or str(value).strip() == "":
                continue
                
            # Type validations
            if field.type == 'NUMBER':
                try:
                    float(value)
                except (ValueError, TypeError):
                    errors[field.key] = f"Value '{value}' must be a valid number."
                    
            elif field.type == 'DATE':
                # Check for standard YYYY-MM-DD
                try:
                    if isinstance(value, str):
                        datetime.date.fromisoformat(value)
                    elif not isinstance(value, (datetime.date, datetime.datetime)):
                        raise ValueError()
                except ValueError:
                    errors[field.key] = f"Value '{value}' must be a valid date in YYYY-MM-DD format."
                    
            elif field.type == 'SELECT':
                choices = field.config.get('choices', [])
                if value not in choices:
                    errors[field.key] = f"Value '{value}' must be one of the permitted choices: {choices}."
                    
            elif field.type == 'BOOLEAN':
                # Check if parseable boolean
                if str(value).lower() not in ['true', 'false', '1', '0', 'yes', 'no']:
                    errors[field.key] = f"Value '{value}' must be a boolean (True/False)."
        
        # Optional: check for fields not in schema
        for key in data.keys():
            if key not in schema_keys:
                errors[key] = f"Field '{key}' is not defined in this table's schema."
                
        if errors:
            raise ValidationError(errors)
