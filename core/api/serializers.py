from rest_framework import serializers
from django.contrib.auth.models import User
from core.models import (
    Tenant, UserProfile, OperatorAssignment, DynamicTable, 
    TableField, CardRecord, WorkflowLog, Job, JobLog
)

# ==========================================
# 1. USER & PROFILE SERIALIZERS
# ==========================================

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = UserProfile
        fields = ['id', 'user', 'tenant', 'role', 'managed_by', 'created_at']


class OperatorAssignmentSerializer(serializers.ModelSerializer):
    operator_details = UserProfileSerializer(source='operator', read_only=True)
    client_details = UserProfileSerializer(source='client', read_only=True)

    class Meta:
        model = OperatorAssignment
        fields = ['id', 'operator', 'client', 'assigned_by', 'created_at', 'operator_details', 'client_details']
        read_only_fields = ['assigned_by']

    def validate(self, attrs):
        operator = attrs.get('operator')
        client = attrs.get('client')
        
        # Verify role constraints
        if operator.role != 'OPERATOR':
            raise serializers.ValidationError({"operator": "Assigned user must be an OPERATOR."})
        if client.role != 'CLIENT':
            raise serializers.ValidationError({"client": "Assigned user must be a CLIENT."})
        return attrs


# ==========================================
# 2. SCHEMA & TABLE SERIALIZERS
# ==========================================

class TableFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = TableField
        fields = ['id', 'name', 'key', 'type', 'config', 'is_required', 'order']


class DynamicTableSerializer(serializers.ModelSerializer):
    fields = TableFieldSerializer(many=True, read_only=True)
    client_details = UserProfileSerializer(source='client', read_only=True)

    class Meta:
        model = DynamicTable
        fields = ['id', 'tenant', 'client', 'name', 'slug', 'fields', 'client_details', 'created_at']
        read_only_fields = ['slug', 'tenant']


# ==========================================
# 3. CARD RECORD SERIALIZERS
# ==========================================

class CardRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = CardRecord
        fields = ['id', 'status', 'data', 'images', 'version', 'created_at', 'updated_at']
        read_only_fields = ['status', 'images', 'version']

    def validate_data(self, value):
        # Retrieve active table context from ViewSet
        table = self.context.get('table')
        if not table:
            raise serializers.ValidationError("Table context is missing.")
            
        # Run schema validations on JSONB data
        from core.validators import DynamicSchemaValidator
        from django.core.exceptions import ValidationError as DjangoValidationError
        
        try:
            DynamicSchemaValidator.validate(value, table)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message)
            
        return value


class WorkflowLogSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = WorkflowLog
        fields = ['id', 'from_status', 'to_status', 'user', 'reason', 'created_at']


# ==========================================
# 4. BACKGROUND JOB SERIALIZERS
# ==========================================

class JobLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobLog
        fields = ['id', 'message', 'level', 'timestamp']


class JobSerializer(serializers.ModelSerializer):
    logs = JobLogSerializer(many=True, read_only=True)

    class Meta:
        model = Job
        fields = ['id', 'tenant', 'user', 'job_type', 'status', 'progress', 'payload', 'result_url', 'error_message', 'logs', 'created_at']
        read_only_fields = ['user', 'tenant', 'status', 'progress', 'result_url', 'error_message']
