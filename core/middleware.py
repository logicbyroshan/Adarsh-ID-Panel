import contextvars
from django.utils.deprecation import MiddlewareMixin

_current_tenant_id = contextvars.ContextVar('current_tenant_id', default=None)

def get_current_tenant_id() -> str:
    return _current_tenant_id.get()

def set_current_tenant_id(tenant_id: str):
    _current_tenant_id.set(tenant_id)

class TenantIsolationMiddleware(MiddlewareMixin):
    """
    Middleware that captures active tenant context from user profile
    and sets it dynamically in context variable for query filtering.
    """
    def process_request(self, request):
        if request.user and request.user.is_authenticated:
            try:
                profile = request.user.profile
                if profile.tenant_id:
                    set_current_tenant_id(str(profile.tenant_id))
            except AttributeError:
                pass

    def process_response(self, request, response):
        # Prevent context leakage across requests
        set_current_tenant_id(None)
        return response
