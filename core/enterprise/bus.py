import json
from typing import Dict, Any
from django.db import transaction
from django.core.cache import cache
from core.enterprise.models import EventLog, IntegrationWebhook

class EventBusService:
    """
    Unified Event Bus and Audit Event Architecture.
    Handles event recording, transactional bus emits, and webhook scheduling.
    """

    @staticmethod
    def emit(tenant_id: str, event_type: str, payload: Dict[str, Any]) -> EventLog:
        """
        Emits an event on the bus. Writes to EventLog (Audit Event Architecture)
        and schedules webhook propagation.
        """
        # Save to database (Audit Event Architecture)
        event_log = EventLog.objects.create(
            tenant_id=tenant_id,
            event_type=event_type,
            payload=payload
        )

        # Redis usage: Publish event to Redis Pub/Sub for realtime listeners
        from django.core.cache import cache
        try:
            # We also log event keys to Redis lists for fast realtime dashboard streams
            redis_client = cache.client.get_client()
            redis_client.publish(f"bus:tenant:{tenant_id}", json.dumps({
                "event_id": str(event_log.id),
                "event_type": event_type,
                "payload": payload,
                "timestamp": event_log.created_at.isoformat() if hasattr(event_log.created_at, 'isoformat') else str(event_log.created_at)
            }))
        except Exception:
            pass # Graceful fallback when Redis is absent

        # Dispatch Webhooks through Celery tasks (delayed until transaction commits)
        transaction.on_commit(
            lambda: EventBusService.dispatch_webhooks_task.delay(str(event_log.id))
        )

        return event_log

    @staticmethod
    def register_webhook(tenant_id: str, target_url: str, events: list, secret: str) -> IntegrationWebhook:
        """
        Registers a webhook subscriber for specific events.
        """
        return IntegrationWebhook.objects.create(
            tenant_id=tenant_id,
            target_url=target_url,
            event_subscriptions=events,
            secret_token=secret,
            is_active=True
        )

    # Worker integration task (imported inside tasks.py)
    @staticmethod
    def trigger_webhook_dispatch(event_log_id: str):
        """
        Internal dispatcher executed by Celery workers to POST webhooks.
        """
        import hmac
        import hashlib
        import requests
        
        event_log = EventLog.objects.get(id=event_log_id)
        tenant = event_log.tenant
        
        # Query active webhook targets subscribed to this event_type
        subscribers = IntegrationWebhook.objects.filter(
            tenant=tenant,
            is_active=True,
            event_subscriptions__contains=[event_log.event_type]
        )
        
        payload_bytes = json.dumps(event_log.payload).encode('utf-8')
        
        for webhook in subscribers:
            # Sign payload using HMAC SHA256 (prevents spoofing)
            signature = hmac.new(
                webhook.secret_token.encode('utf-8'),
                payload_bytes,
                hashlib.sha256
            ).hexdigest()
            
            headers = {
                'Content-Type': 'application/json',
                'X-Event-Signature': signature,
                'X-Event-Type': event_log.event_type
            }
            
            try:
                requests.post(webhook.target_url, data=payload_bytes, headers=headers, timeout=5)
            except requests.RequestException:
                # In production, schedule retry attempts
                pass

# Expose as Celery task hook placeholder
from celery import shared_task

@shared_task
def dispatch_webhooks_task_wrapper(event_log_id: str):
    EventBusService.trigger_webhook_dispatch(event_log_id)

EventBusService.dispatch_webhooks_task = dispatch_webhooks_task_wrapper
