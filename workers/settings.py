from .queues import task_queues
from .task_routes import task_routes

CELERY_CONFIG = {
    'task_queues': task_queues,
    'task_routes': task_routes,
    'task_default_queue': 'default',
    'task_serializer': 'json',
    'result_serializer': 'json',
    'accept_content': ['json'],
    'worker_prefetch_multiplier': 1,
    'task_acks_late': True,
    'task_reject_on_worker_lost': True,
    'task_publish_retry': True,
    'task_publish_retry_policy': {
        'max_retries': 3,
        'interval_start': 0,
        'interval_step': 0.2,
        'interval_max': 0.5,
    },
}\n