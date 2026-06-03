from rest_framework import permissions

class HasEnterpriseRolePermission(permissions.BasePermission):
    """
    Enforces role scoping for enterprise domain resources.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        try:
            profile = request.user.profile
        except AttributeError:
            return False

        # PRO_USER has universal rights
        if profile.role == 'PRO_USER':
            return True

        role = profile.role

        # Enforce resource specific permissions
        if view.basename == 'feature-flags':
            # Global feature flags are viewable by Admins but editable only by PRO_USERs
            return request.method in permissions.SAFE_METHODS and role == 'ADMIN'

        if view.basename == 'tenant-overrides':
            return role == 'ADMIN'

        if view.basename == 'licenses':
            # Licenses are read-only for organization admins
            return request.method in permissions.SAFE_METHODS and role == 'ADMIN'

        if view.basename == 'impersonations':
            # Impersonation sessions can only be controlled by PRO_USERs
            return False

        if view.basename in ['webhooks', 'bulk-ops', 'settings']:
            # Integrations, bulk tasks, and branding setup are restricted to Admins & Clients
            return role in ['ADMIN', 'CLIENT']

        if view.basename in ['desktop-devices', 'sync-logs']:
            # Device registration is allowed for Clients and their assistants
            return role in ['CLIENT', 'ASSISTANT']

        return True

    def has_object_permission(self, request, view, obj):
        profile = request.user.profile
        if profile.role == 'PRO_USER':
            return True

        # Assert Tenant isolation bounds
        if hasattr(obj, 'tenant') and obj.tenant != profile.tenant:
            return False

        return True
