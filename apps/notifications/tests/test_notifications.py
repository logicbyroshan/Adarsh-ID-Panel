from django.test import TestCase, override_settings
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.organizations.models import Organization
from shared.constants import Role
from apps.desktop_sync.models import DesktopApiKey
from apps.notifications.models import (
    NotificationLevel, TargetType, ReadState,
    NotificationTemplate, NotificationEvent, Notification, NotificationDelivery, NotificationPreference
)
from apps.notifications.services import NotificationService
from apps.auditlogs.models import AuditLog, AuditEvent

User = get_user_model()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class NotificationBaseTest(TestCase):

    def setUp(self):
        super().setUp()
        cache.clear()
        
        # Create Owner first
        self.owner = User.objects.create_user(
            username="notif_owner",
            password="password123",
            role=Role.CLIENT
        )
        
        self.org = Organization.objects.create(
            name="Notification Org",
            owner_client=self.owner
        )
        
        self.owner.organization_id = self.org.id
        self.owner.save()
        
        self.admin = User.objects.create_user(
            username="notif_admin",
            password="password123",
            role=Role.ADMIN,
            organization=self.org
        )
        self.client_user = User.objects.create_user(
            username="notif_client",
            password="password123",
            role=Role.CLIENT,
            organization=self.org
        )
        self.pro_user = User.objects.create_user(
            username="notif_pro",
            password="password123",
            role=Role.PRO_USER
        )
        
        # Setup templates
        NotificationTemplate.objects.create(
            event_type='IMPORT_COMPLETE',
            title_template='Import Completed for {org_name}',
            message_template='Session {session_id} succeeded.',
            level=NotificationLevel.SUCCESS
        )
        NotificationTemplate.objects.create(
            event_type='IMPORT_FAIL',
            title_template='Import Failed',
            message_template='Session {session_id} failed with errors.',
            level=NotificationLevel.ERROR
        )


class NotificationCreationAndPreferenceTests(NotificationBaseTest):

    def test_notification_creation_from_event(self):
        """Verify that creating a notification from an event generates the correct entities."""
        notif = NotificationService.create_notification_from_event(
            event_type='IMPORT_COMPLETE',
            source_user=self.admin,
            source_org=self.org,
            data={'org_name': self.org.name, 'session_id': 'import-123'}
        )
        
        self.assertEqual(notif.title, f"Import Completed for {self.org.name}")
        self.assertEqual(notif.message, "Session import-123 succeeded.")
        self.assertEqual(notif.level, NotificationLevel.SUCCESS)
        self.assertEqual(notif.target_type, TargetType.ORGANIZATION)
        self.assertEqual(notif.target_id, str(self.org.id))
        
        # Verify Delivery
        deliveries = NotificationDelivery.objects.filter(notification=notif)
        self.assertTrue(deliveries.exists())
        # admin, client_user and owner are in the org
        self.assertEqual(deliveries.count(), 3)

    def test_notification_preferences_respected(self):
        """Verify that user notification preferences are respected during delivery."""
        # Client user opts out of import notifications
        pref, _ = NotificationPreference.objects.get_or_create(user=self.client_user)
        pref.import_notifications = False
        pref.save()
        
        notif = NotificationService.create_notification_from_event(
            event_type='IMPORT_COMPLETE',
            source_user=self.admin,
            source_org=self.org,
            data={'org_name': self.org.name, 'session_id': 'import-123'}
        )
        
        # Admin should receive delivery, but client user should not
        self.assertTrue(NotificationDelivery.objects.filter(notification=notif, user=self.admin).exists())
        self.assertFalse(NotificationDelivery.objects.filter(notification=notif, user=self.client_user).exists())


class ExpiryAndRetentionTests(NotificationBaseTest):

    def test_archiving_expired_notifications(self):
        """Verify expired notifications are automatically archived."""
        # Create a notification expiring in the past
        notif = Notification.objects.create(
            title="Expired Alert",
            message="This alert has expired.",
            level=NotificationLevel.INFO,
            target_type=TargetType.GLOBAL,
            visible_from=timezone.now() - timedelta(days=2),
            visible_until=timezone.now() - timedelta(days=1)
        )
        
        delivery = NotificationDelivery.objects.create(
            notification=notif,
            user=self.admin,
            read_state=ReadState.UNREAD
        )
        
        count = NotificationService.archive_expired_notifications()
        self.assertEqual(count, 1)
        
        notif.refresh_from_db()
        delivery.refresh_from_db()
        self.assertTrue(notif.is_archived)
        self.assertEqual(delivery.read_state, ReadState.ARCHIVED)

    def test_purging_retention_period(self):
        """Verify notifications older than retention days are permanently purged."""
        notif = Notification.objects.create(
            title="Old Archived Alert",
            message="Archived long ago.",
            level=NotificationLevel.INFO,
            target_type=TargetType.GLOBAL,
            visible_from=timezone.now() - timedelta(days=40),
            visible_until=timezone.now() - timedelta(days=35),
            is_archived=True
        )
        
        delivery = NotificationDelivery.objects.create(
            notification=notif,
            user=self.admin,
            read_state=ReadState.ARCHIVED
        )
        
        count = NotificationService.purge_expired_notifications(retention_days=30)
        self.assertEqual(count, 1)
        self.assertFalse(Notification.objects.filter(id=notif.id).exists())


class WebsocketTests(NotificationBaseTest):

    def test_websocket_realtime_push(self):
        """Verify WebSocket pushes are stashed only for active mock connections."""
        # 1. Connect admin to websocket
        NotificationService.simulate_websocket_connection(str(self.admin.id), active=True)
        
        # 2. Trigger notification
        notif = NotificationService.create_notification_from_event(
            event_type='IMPORT_COMPLETE',
            source_user=self.admin,
            source_org=self.org,
            data={'org_name': self.org.name, 'session_id': 'import-555'}
        )
        
        # Admin is active, check pushed key in cache
        pushes_key = f"ws_pushes:{self.admin.id}"
        pushes = cache.get(pushes_key)
        self.assertIsNotNone(pushes)
        self.assertEqual(len(pushes), 1)
        self.assertEqual(pushes[0]['title'], f"Import Completed for {self.org.name}")
        
        # Client user was offline, check no cache key generated
        client_pushes = cache.get(f"ws_pushes:{self.client_user.id}")
        self.assertIsNone(client_pushes)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class NotificationAPITests(APITestCase):

    def setUp(self):
        super().setUp()
        cache.clear()
        
        # Create Owner first
        self.owner = User.objects.create_user(
            username="api_owner",
            password="password123",
            role=Role.CLIENT
        )
        
        self.org = Organization.objects.create(
            name="API Org",
            owner_client=self.owner
        )
        
        self.owner.organization_id = self.org.id
        self.owner.save()
        
        self.admin = User.objects.create_user(
            username="api_admin",
            password="password123",
            role=Role.ADMIN,
            organization=self.org
        )
        self.client_user = User.objects.create_user(
            username="api_client",
            password="password123",
            role=Role.CLIENT,
            organization=self.org
        )
        
        # Create deliveries
        self.notif = Notification.objects.create(
            title="General Notification",
            message="Regular updates.",
            level=NotificationLevel.INFO,
            target_type=TargetType.ORGANIZATION,
            target_id=str(self.org.id),
            visible_from=timezone.now()
        )
        self.critical_notif = Notification.objects.create(
            title="Critical Notification",
            message="Server Down!",
            level=NotificationLevel.CRITICAL,
            target_type=TargetType.ORGANIZATION,
            target_id=str(self.org.id),
            visible_from=timezone.now()
        )
        
        self.deliv1 = NotificationDelivery.objects.create(
            notification=self.notif,
            user=self.client_user,
            read_state=ReadState.UNREAD,
            channels=["WEB", "MOBILE", "DESKTOP"]
        )
        self.deliv2 = NotificationDelivery.objects.create(
            notification=self.critical_notif,
            user=self.client_user,
            read_state=ReadState.UNREAD,
            channels=["WEB", "MOBILE", "DESKTOP"]
        )

    def test_web_endpoints(self):
        """Test web notifications views."""
        self.client.force_authenticate(user=self.client_user)
        
        # Unread Count
        response = self.client.get('/api/v1/notifications/unread-count/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['unread_count'], 2)
        
        # List
        response = self.client.get('/api/v1/notifications/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        
        # Mark Read
        response = self.client.post(f'/api/v1/notifications/{self.deliv1.id}/read/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['read_state'], ReadState.READ)
        
        # Preferences update
        response = self.client.patch('/api/v1/notifications/preferences/', {'import_notifications': False})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['import_notifications'])

    def test_mobile_endpoints(self):
        """Test mobile notifications views."""
        self.client.force_authenticate(user=self.client_user)
        
        # Unread Count
        response = self.client.get('/api/v1/notifications/mobile/unread-count/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['unread_count'], 2)
        
        # Mark All Read
        response = self.client.post('/api/v1/notifications/mobile/mark-all-read/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['marked_count'], 2)

    def test_desktop_endpoints(self):
        """Test desktop notifications views (API Key authenticated)."""
        # Create Desktop API key
        key_instance, raw_key = DesktopApiKey.create_key(self.org, "Test PC", self.admin)
        
        # List without key (401)
        response = self.client.get('/api/v1/notifications/desktop/')
        self.assertEqual(response.status_code, 401)
        
        # List with key
        self.client.credentials(HTTP_X_DESKTOP_KEY=raw_key)
        response = self.client.get('/api/v1/notifications/desktop/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        
        # Acknowledge Critical
        response = self.client.post(f'/api/v1/notifications/desktop/{self.deliv2.id}/acknowledge/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'acknowledged')
