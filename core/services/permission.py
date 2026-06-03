from typing import Union
from django.core.exceptions import PermissionDenied
from core.models import UserProfile, DynamicTable, CardRecord, OperatorAssignment

class PermissionService:
    """
    Service responsible for enforcing security and authorization boundaries
    across the hierarchical tenant structures.
    """
    
    @staticmethod
    def has_table_access(user_profile: UserProfile, table: DynamicTable) -> bool:
        """
        Validates access to dynamic tables based on roles and hierarchies.
        """
        role = user_profile.role
        
        # 1. System Super Admin has universal access
        if role == 'PRO_USER':
            return True
            
        # 2. Check tenant isolation boundaries
        if table.tenant != user_profile.tenant:
            return False
            
        # 3. Tenant Admin can access all tables in their tenant
        if role == 'ADMIN':
            return True
            
        # 4. Client owns the tables they create
        if role == 'CLIENT':
            return table.client == user_profile
            
        # 5. Assistant has access to their managing Client's tables
        if role in ['ASSISTANT', 'GUEST']:
            return table.client == user_profile.managed_by
            
        # 6. Operator has access to tables belonging to clients assigned to them
        if role == 'OPERATOR':
            is_assigned = OperatorAssignment.objects.filter(
                operator=user_profile, 
                client=table.client
            ).exists()
            return is_assigned

        return False

    @staticmethod
    def has_record_access(user_profile: UserProfile, record: CardRecord, action: str) -> bool:
        """
        Validates access permissions for specific record actions (READ, WRITE, DELETE, TRANSITION).
        """
        # First ensure the user has table-level access
        if not PermissionService.has_table_access(user_profile, record.table):
            return False
            
        role = user_profile.role
        
        if role in ['PRO_USER', 'ADMIN', 'CLIENT']:
            return True
            
        if role == 'ASSISTANT':
            # Assistants can read and write, but cannot permanently delete records
            if action in ['READ', 'WRITE', 'TRANSITION']:
                return True
            return False
            
        if role == 'GUEST':
            # Guests work strictly inside their sandbox delta session
            return action in ['READ', 'WRITE']
            
        if role == 'OPERATOR':
            # Operators can read and update status transitions
            if action in ['READ', 'TRANSITION']:
                return True
            # Operators can write but cannot delete
            if action == 'WRITE':
                return True
            return False
            
        return False

    @staticmethod
    def can_manage_operator(admin_profile: UserProfile, operator_profile: UserProfile) -> bool:
        """
        Verifies if an Admin can manage a specific Operator.
        """
        if admin_profile.role == 'PRO_USER':
            return True
            
        if admin_profile.role != 'ADMIN':
            return False
            
        # Ensure they belong to the same tenant and Operator is managed by this admin
        return (operator_profile.tenant == admin_profile.tenant and 
                operator_profile.managed_by == admin_profile)
