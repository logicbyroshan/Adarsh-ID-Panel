from django.urls import path, include
from rest_framework_nested import routers
from core.api.views import DynamicTableViewSet, CardRecordViewSet, JobViewSet

router = routers.SimpleRouter()
# /api/v1/tenants/
router.register(r'tenants', DynamicTableViewSet, basename='tenant')

# /api/v1/tenants/<tenant_pk>/tables/
tables_router = routers.NestedSimpleRouter(router, r'tenants', lookup='tenant')
tables_router.register(r'tables', DynamicTableViewSet, basename='tenant-tables')

# /api/v1/tenants/<tenant_pk>/tables/<table_pk>/cards/
# /api/v1/tenants/<tenant_pk>/tables/<table_pk>/jobs/
cards_router = routers.NestedSimpleRouter(tables_router, r'tables', lookup='table')
cards_router.register(r'cards', CardRecordViewSet, basename='table-cards')
cards_router.register(r'jobs', JobViewSet, basename='table-jobs')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(tables_router.urls)),
    path('', include(cards_router.urls)),
]
