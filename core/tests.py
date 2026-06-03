from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Tenant, UserProfile, OperatorAssignment, DynamicTable, TableField, CardRecord, SandboxSession, SandboxDelta
from core.services.permission import PermissionService
from core.services.card import CardService
from core.services.table import TableService
from core.services.workflow import WorkflowService
from core.services.presence import PresenceService
from core.services.sandbox import SandboxService
from core.validators import DynamicSchemaValidator

# =====================================================================
# 1. UNIT TESTS: MODELS, VALIDATION, AND PERMISSION HIERARCHY
# =====================================================================

class ModelAndValidationTestCase(TestCase):
    def setUp(self):
        # Setup tenant
        self.tenant = Tenant.objects.create(name="Acme Corp", subdomain="acme")
        
        # Setup users
        self.admin_user = User.objects.create_user(username="admin", password="password")
        self.client_user = User.objects.create_user(username="client", password="password")
        self.operator_user = User.objects.create_user(username="operator", password="password")
        self.assistant_user = User.objects.create_user(username="assistant", password="password")
        self.guest_user = User.objects.create_user(username="guest", password="password")
        
        # Setup profiles
        self.admin_profile = UserProfile.objects.create(user=self.admin_user, tenant=self.tenant, role='ADMIN')
        self.client_profile = UserProfile.objects.create(user=self.client_user, tenant=self.tenant, role='CLIENT', managed_by=self.admin_profile)
        self.operator_profile = UserProfile.objects.create(user=self.operator_user, tenant=self.tenant, role='OPERATOR', managed_by=self.admin_profile)
        self.assistant_profile = UserProfile.objects.create(user=self.assistant_user, tenant=self.tenant, role='ASSISTANT', managed_by=self.client_profile)
        self.guest_profile = UserProfile.objects.create(user=self.guest_user, tenant=self.tenant, role='GUEST', managed_by=self.client_profile)

        # Setup table schema
        self.table = DynamicTable.objects.create(tenant=self.tenant, client=self.client_profile, name="Employees", slug="employees")
        self.field_name = TableField.objects.create(table=self.table, name="Name", key="name", type="TEXT", is_required=True, order=0)
        self.field_age = TableField.objects.create(table=self.table, name="Age", key="age", type="NUMBER", is_required=False, order=1)
        self.field_joined = TableField.objects.create(table=self.table, name="Joined Date", key="joined_date", type="DATE", is_required=False, order=2)
        self.field_active = TableField.objects.create(table=self.table, name="Active", key="active", type="BOOLEAN", is_required=False, order=3)
        self.field_role = TableField.objects.create(table=self.table, name="Role", key="role", type="SELECT", config={"choices": ["Developer", "Designer"]}, is_required=False, order=4)

    def test_user_profile_hierarchy_validation(self):
        # Test OperatorManagedBy constraint: Operator managed by Client should fail clean() check
        invalid_operator = UserProfile(
            user=User.objects.create_user(username="invalid_op"),
            tenant=self.tenant,
            role='OPERATOR',
            managed_by=self.client_profile
        )
        with self.assertRaises(ValidationError):
            invalid_operator.clean()

    def test_dynamic_schema_validations(self):
        # Correct payload
        valid_data = {
            "name": "Alice Smith",
            "age": 28,
            "joined_date": "2026-06-03",
            "active": True,
            "role": "Developer"
        }
        # Should not raise exception
        DynamicSchemaValidator.validate(valid_data, self.table)

        # Missing required field
        invalid_missing = {"age": 28}
        with self.assertRaises(ValidationError):
            DynamicSchemaValidator.validate(invalid_missing, self.table)

        # Wrong type: Age is non-numeric
        invalid_type = {"name": "Alice", "age": "not-a-number"}
        with self.assertRaises(ValidationError):
            DynamicSchemaValidator.validate(invalid_type, self.table)

        # Wrong type: Invalid date format
        invalid_date = {"name": "Alice", "joined_date": "06/03/2026"}
        with self.assertRaises(ValidationError):
            DynamicSchemaValidator.validate(invalid_date, self.table)

        # Wrong select choice: Role not in permitted choices
        invalid_choice = {"name": "Alice", "role": "Manager"}
        with self.assertRaises(ValidationError):
            DynamicSchemaValidator.validate(invalid_choice, self.table)

    def test_permission_boundaries(self):
        # Client profile has access to their own tables
        self.assertTrue(PermissionService.has_table_access(self.client_profile, self.table))
        
        # Assistant managed by Client has access to Client's table
        self.assertTrue(PermissionService.has_table_access(self.assistant_profile, self.table))
        
        # Unassigned Operator does NOT have access
        self.assertFalse(PermissionService.has_table_access(self.operator_profile, self.table))
        
        # Assign Operator to Client
        OperatorAssignment.objects.create(
            operator=self.operator_profile,
            client=self.client_profile,
            assigned_by=self.admin_profile
        )
        # Operator should now have table access via assignment mappings
        self.assertTrue(PermissionService.has_table_access(self.operator_profile, self.table))


# =====================================================================
# 2. INTEGRATION TESTS: CONCURRENCY, WORKFLOWS, AND SANDBOX ENGINE
# =====================================================================

class IntegrationServicesTestCase(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Acme Corp", subdomain="acme")
        self.client_user = User.objects.create_user(username="client", password="password")
        self.client_profile = UserProfile.objects.create(user=self.client_user, tenant=self.tenant, role='CLIENT')
        self.table = DynamicTable.objects.create(tenant=self.tenant, client=self.client_profile, name="Employees", slug="employees")
        TableField.objects.create(table=self.table, name="Name", key="name", type="TEXT", is_required=True)
        
        # Create a card record
        self.record = CardService.create_record(self.table, {"name": "Alice"})

    def test_optimistic_concurrency_locking(self):
        # Success update
        updated_rec = CardService.update_record(
            str(self.record.id),
            {"name": "Alice Updated"},
            client_version=1
        )
        self.assertEqual(updated_rec.version, 2)
        
        # Failure: stale client version update
        with self.assertRaises(ValidationError):
            CardService.update_record(
                str(self.record.id),
                {"name": "Alice Stale"},
                client_version=1  # Version in database is now 2
            )

    def test_workflow_state_transitions(self):
        workflow = WorkflowService()
        
        # PENDING -> VERIFIED is permitted
        rec = workflow.execute_transition(str(self.record.id), "VERIFIED", self.client_user)
        self.assertEqual(rec.status, "VERIFIED")
        
        # VERIFIED -> DOWNLOADED is NOT permitted directly (must go via APPROVED)
        with self.assertRaises(ValidationError):
            workflow.execute_transition(str(self.record.id), "DOWNLOADED", self.client_user)

    def test_guest_sandbox_delta_isolation(self):
        # Create a Guest profile
        guest_user = User.objects.create_user(username="guest", password="password")
        guest_profile = UserProfile.objects.create(user=guest_user, tenant=self.tenant, role='GUEST', managed_by=self.client_profile)
        
        # Start sandbox session
        session = SandboxSession.objects.create(user=guest_user, is_active=True)
        sandbox = SandboxService(session)
        
        # Guest writes update change
        sandbox.write_change('UPDATE', self.table, record_id=str(self.record.id), data={"name": "Alice Sandboxed"})
        
        # Production record is still unchanged
        self.record.refresh_from_db()
        self.assertEqual(self.record.data["name"], "Alice")
        
        # Sandbox read returns the updated merged data
        records = sandbox.get_records(self.table)
        self.assertEqual(records[0].data["name"], "Alice Sandboxed")
        
        # Guest writes create record inside sandbox
        sandbox.write_change('CREATE', self.table, data={"name": "Bob Sandboxed"})
        
        # Read returns 2 records (1 production merged, 1 sandbox created)
        records = sandbox.get_records(self.table)
        self.assertEqual(len(records), 2)
        
        # Discard deletes all sandbox deltas
        sandbox.discard()
        self.assertEqual(len(sandbox.get_records(self.table)), 1)


# =====================================================================
# 3. API ENDPOINT CONTROLLER TESTS
# =====================================================================

class ApiControllersTestCase(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Acme Corp", subdomain="acme")
        self.client_user = User.objects.create_user(username="client", password="password")
        self.client_profile = UserProfile.objects.create(user=self.client_user, tenant=self.tenant, role='CLIENT')
        
        self.table = DynamicTable.objects.create(tenant=self.tenant, client=self.client_profile, name="Employees", slug="employees")
        TableField.objects.create(table=self.table, name="Name", key="name", type="TEXT", is_required=True)
        self.record = CardRecord.objects.create(table=self.table, data={"name": "Charlie"}, status='PENDING')
        
        # Authenticate client
        self.client.force_authenticate(user=self.client_user)

    def test_get_records(self):
        url = reverse('table-cards-list', kwargs={
            'tenant_pk': str(self.tenant.id),
            'table_pk': str(self.table.id)
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['data']['name'], 'Charlie')

    def test_heartbeat_presence_monitoring(self):
        url = reverse('table-cards-heartbeat', kwargs={
            'tenant_pk': str(self.tenant.id),
            'table_pk': str(self.table.id)
        })
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return active users currently viewing this table
        self.assertIn("active_users", response.data)
        self.assertIn(str(self.client_user.id), response.data["active_users"])

    def test_cell_lease_locking(self):
        url = reverse('table-cards-lock-cell', kwargs={
            'tenant_pk': str(self.tenant.id),
            'table_pk': str(self.table.id),
            'pk': str(self.record.id)
        })
        response = self.client.post(url, data={"field_key": "name"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "locked")
