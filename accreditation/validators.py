from rest_framework import serializers

def validate_custom_data(custom_data: dict, schema: dict) -> dict:
    """Validate custom_data against the event's schema"""
    if not schema or 'fields' not in schema:
        return custom_data
    
    errors = {}
    validated_data = {}
    
    for field_def in schema['fields']:
        key = field_def['key']
        label = field_def['label']
        field_type = field_def['type']
        required = field_def.get('required', False)
        
        value = custom_data.get(key)
        
        # Check required fields
        if required and (value is None or value == ''):
            errors[key] = f'{label} is required'
            continue
        
        # Skip if no value and not required
        if value is None or value == '':
            continue
        
        # Type validation
        try:
            if field_type == 'text':
                validated_data[key] = str(value)
            elif field_type == 'textarea':
                validated_data[key] = str(value)
            elif field_type == 'number':
                validated_data[key] = float(value)
            elif field_type == 'date':
                # Basic date validation (YYYY-MM-DD)
                from datetime import datetime
                datetime.strptime(str(value), '%Y-%m-%d')
                validated_data[key] = str(value)
            elif field_type == 'dropdown':
                options = field_def.get('options', [])
                if value not in options:
                    errors[key] = f'{label} must be one of: {", ".join(options)}'
                else:
                    validated_data[key] = value
            elif field_type == 'checkbox':
                validated_data[key] = bool(value)
            elif field_type == 'email':
                from django.core.validators import validate_email
                validate_email(value)
                validated_data[key] = str(value)
            elif field_type == 'phone':
                validated_data[key] = str(value)
        except (ValueError, serializers.ValidationError):
            errors[key] = f'{label} is invalid'
    
    if errors:
        raise serializers.ValidationError(errors)
    
    return validated_data