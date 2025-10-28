# create_superuser.py
import os
import sys
import time
import django
from django.db import OperationalError
from django.db.utils import IntegrityError

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nance.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')

def wait_for_db(max_tries=10, delay=3):
    for i in range(max_tries):
        try:
            # Try simple DB access
            from django.db import connections
            connections['default'].cursor()
            return True
        except Exception as e:
            print(f"[create_superuser] DB not ready (attempt {i+1}/{max_tries}): {e}")
            time.sleep(delay)
    return False

if not username or not password:
    print("Missing username or password. Superuser not created.")
    sys.exit(1)

if not wait_for_db():
    print("DB not reachable after retries. Aborting superuser creation.")
    sys.exit(1)

try:
    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(
            username=username,
            email=email if email else f'{username}@nance.local',
            password=password
        )
        print(f"Superuser '{username}' created successfully!")
    else:
        print(f"Superuser '{username}' already exists.")
    sys.exit(0)
except IntegrityError as e:
    print(f"Superuser creation failed (IntegrityError): {e}")
    sys.exit(1)
except Exception as e:
    print(f"Error creating superuser: {e}")
    sys.exit(1)
