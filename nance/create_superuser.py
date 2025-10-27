from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError

User = get_user_model()

username = "admin"
email = "admin@example.com"
password = "admin123"

try:
    User.objects.create_superuser(username=username, email=email, password=password)
    print("✅ Superuser created successfully!")
except IntegrityError:
    print("⚠️ Superuser already exists.")
