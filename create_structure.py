import os
import shutil

base_dir = r"c:\Users\iamro\Desktop\Adarsh-ID Panel"

# Clean up existing generated structure
for d in ['apps', 'api', 'contracts', 'infrastructure', 'integrations', 'commands', 'shared', 'workers', 'scripts', 'docs', 'tests', 'storage', 'config']:
    path = os.path.join(base_dir, d)
    if os.path.exists(path):
        shutil.rmtree(path)

structure = [
    "manage.py",
    "requirements.txt",
    "requirements-dev.txt",
    "config/__init__.py",
    "config/urls.py",
    "config/asgi.py",
    "config/wsgi.py",
    "config/settings/__init__.py",
    "config/settings/base.py",
    "config/settings/local.py",
    "config/settings/production.py",
    "config/settings/staging.py",
    "api/__init__.py",
    "api/v1/__init__.py",
    "api/v1/urls.py",
    "api/v2/__init__.py",
    "api/v2/urls.py",
    "contracts/__init__.py",
    "contracts/storage.py",
    "contracts/search.py",
    "contracts/notifications.py",
    "infrastructure/__init__.py",
    "infrastructure/cache/__init__.py",
    "infrastructure/queue/__init__.py",
    "infrastructure/storage/__init__.py",
    "infrastructure/search/__init__.py",
    "integrations/__init__.py",
    "integrations/r2/__init__.py",
    "integrations/minio/__init__.py",
    "integrations/email/__init__.py",
    "integrations/whatsapp/__init__.py",
    "commands/__init__.py",
    "shared/__init__.py",
    "shared/exceptions/__init__.py",
    "shared/constants/__init__.py",
    "shared/validators/__init__.py",
    "shared/utils/__init__.py",
    "shared/mixins/__init__.py",
    "shared/typing/__init__.py",
    "workers/__init__.py",
    "workers/celery_app.py",
    "workers/imports/__init__.py",
    "workers/imports/tasks.py",
    "workers/exports/__init__.py",
    "workers/exports/tasks.py",
    "workers/images/__init__.py",
    "workers/images/tasks.py",
    "workers/notifications/__init__.py",
    "workers/notifications/tasks.py",
    "scripts/setup.sh",
    "scripts/deploy.sh",
    "docs/index.md",
    "tests/__init__.py",
    "tests/conftest.py"
]

apps = [
    'users', 'organizations', 'permissions', 'features', 'licenses', 
    'versions', 'impersonation', 'tables', 'fields', 'cards', 
    'workflow', 'imports', 'exports', 'mediafiles', 'jobs', 
    'notifications', 'search', 'sandbox', 'auditlogs', 'settings', 
    'desktop_sync'
]

# NO admin.py, NO signals.py, views is a directory
app_files = [
    "__init__.py", "models.py", "apps.py", "urls.py", "constants.py", "validators.py",
    "selectors/__init__.py", "repositories/__init__.py", "services/__init__.py", 
    "tasks/__init__.py", "policies/__init__.py", "events/__init__.py",
    "migrations/__init__.py", "tests/__init__.py", "serializers/__init__.py",
    "views/__init__.py", "schemas/__init__.py", "dto/__init__.py"
]

for app in apps:
    for f in app_files:
        structure.append(f"apps/{app}/{f}")

for path in structure:
    full_path = os.path.join(base_dir, os.path.normpath(path))
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w') as file:
        pass

print("New enterprise structure created successfully.")
