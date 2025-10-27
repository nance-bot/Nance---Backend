# Render Deployment Setup Instructions

## Environment Variables Required in Render Dashboard

Go to **Environment → Environment Variables** in your Render dashboard and add:

| Name | Value | Description |
|------|-------|-------------|
| `DJANGO_SUPERUSER_EMAIL` | admin@example.com | Admin user email |
| `DJANGO_SUPERUSER_USERNAME` | admin | Admin username |
| `DJANGO_SUPERUSER_PASSWORD` | strongpassword123 | Admin password |
| `DEBUG` | False | Set to True for development |
| `DATABASE_URL` | (Auto-provided) | PostgreSQL connection string |
| `GOOGLE_CLIENT_ID` | (Your client ID) | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | (Your client secret) | Google OAuth secret |

## Deployment Process

1. **Migrate Database**: `python manage.py migrate`
2. **Create Superuser**: `python create_superuser.py` (uses environment variables)
3. **Start Server**: `gunicorn nance.wsgi`

## Access Admin Panel

After deployment, access the Django admin at:
- URL: `https://nance-backend.onrender.com/admin`
- Username: (from `DJANGO_SUPERUSER_USERNAME`)
- Password: (from `DJANGO_SUPERUSER_PASSWORD`)

## Security Notes

- ✅ All credentials are in environment variables
- ✅ No hardcoded secrets in code
- ✅ Superuser created only if it doesn't exist
- ✅ DEBUG mode controlled by environment variable

