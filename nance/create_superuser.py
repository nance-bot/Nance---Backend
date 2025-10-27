import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nance.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError

User = get_user_model()

# Get credentials from environment variables
username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')

# Only create superuser if all credentials are provided
if username and email and password:
    try:
        # Check if user already exists
        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username=username, email=email, password=password)
            print(f"Superuser '{username}' created successfully!")
        else:
            print(f"Superuser '{username}' already exists.")
    except IntegrityError:
        print(f"Superuser '{username}' already exists (IntegrityError).")
else:
    print("Missing environment variables. Superuser not created.")
