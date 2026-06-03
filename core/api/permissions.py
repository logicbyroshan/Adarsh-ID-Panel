from rest_framework import permissions
from core.services.permission import PermissionService
from core.models import UserProfile, DynamicTable, CardRecord

class HasHierarchicalRolePermission(permissions.BasePermission):
    """
    Implements multi-tenant isolation and enforces granular API access boundaries
    based on hierarchical roles.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        # Ensure UserProfile exists
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            return False
            
        # PRO_USER bypasses all permission layers
        if profile.role == 'PRO_USER':
            return True
            
        # Restrict tenant boundaries
        tenant_pk = view.kwargs.get('tenant_pk')
        if tenant_pk and str(profile.tenant_id) != tenant_pk:
            return False

        # Role-based action scoping
        if view.basename == 'tenant-tables':
            # Only ADMIN and CLIENT users can mutate Table schemas
            if request.method in permissions.SAFE_METHODS:
                return profile.role in ['ADMIN', 'CLIENT', 'OPERATOR', 'ASSISTANT', 'GUEST']
            return profile.role in ['ADMIN', 'CLIENT']
            
        if view.basename == 'table-fields':
            # Schema fields modification is restricted to ADMIN and CLIENT
            if request.method in permissions.SAFE_METHODS:
                return profile.role in ['ADMIN', 'CLIENT', 'OPERATOR', 'ASSISTANT', 'GUEST']
            return profile.role in ['ADMIN', 'CLIENT']

        if view.basename == 'table-cards':
            # Card mutations are allowed by all roles with custom obj permissions
            return True
            
        if view.basename == 'operator-assignments':
            # Only Tenant ADMINs can assign operators to clients
            return profile.role == 'ADMIN'
            
        return True

    def has_object_permission(self, request, view, obj):
        profile = request.user.profile
        
        if profile.role == 'PRO_USER':
            return True
            
        # 1. Enforce Tenant Isolation
        if hasattr(obj, 'tenant') and obj.tenant != profile.tenant:
            return False
            
        # 2. Check objects for nested child structures
        if isinstance(obj, DynamicTable):
            return PermissionService.has_table_access(profile, obj)
            
        if isinstance(obj, CardRecord):
            action = 'READ' if request.method in permissions.SAFE_METHODS else 'WRITE'
            # Map workflow status changes to TRANSITION action
            if view.action in ['transition', 'bulk_transition']:
                action = 'TRANSITION'
            elif request.method == 'DELETE':
                action = 'DELETE'
            return PermissionService.has_record_access(profile, obj, action)
            
        return True
