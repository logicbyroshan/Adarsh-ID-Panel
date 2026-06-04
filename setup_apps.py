import os

base_dir = r"c:\Users\iamro\Desktop\Adarsh-ID Panel\apps"
apps = ['tables', 'fields', 'cards']
folders = ['', 'services', 'repositories', 'selectors', 'policies', 'serializers', 'views', 'tests']

for app in apps:
    for folder in folders:
        dir_path = os.path.join(base_dir, app, folder)
        os.makedirs(dir_path, exist_ok=True)
        init_file = os.path.join(dir_path, '__init__.py')
        if not os.path.exists(init_file):
            with open(init_file, 'w') as f:
                f.write('')
    
    # apps.py
    with open(os.path.join(base_dir, app, 'apps.py'), 'w') as f:
        f.write(f'''from django.apps import AppConfig

class {app.capitalize()}Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.{app}'
''')

    # urls.py
    with open(os.path.join(base_dir, app, 'urls.py'), 'w') as f:
        f.write('''from django.urls import path
urlpatterns = []
''')
