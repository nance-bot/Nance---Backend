# Credit Cards App Setup & Testing Guide

## Step 1: Create Database Migrations

Run these commands in the `nance` directory:

```bash
cd nance
python manage.py makemigrations credit_cards
python manage.py migrate
```

This will create the `GmailToken` and `GmailEmail` tables in your database.

## Step 2: Set Up Google OAuth Credentials

### Option A: Using credentials.json file
1. Make sure `credentials.json` exists in `nance/sms/credentials.json`
2. The file should contain your OAuth 2.0 credentials from Google Cloud Console

### Option B: Using Environment Variables
Set these environment variables (or add them to your `.env` file):
```bash
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
```

**Important:** Update your Google OAuth redirect URI in Google Cloud Console to:
- `http://localhost:8000/credit-cards/oauth2callback/` (for local development)

## Step 3: Start the Django Server

```bash
cd nance
python manage.py runserver
```

The server will start at `http://localhost:8000`

## Step 4: Test the Endpoints

### 4.1 Authorize Gmail (First Time Setup)
Open in browser or use curl:
```
http://localhost:8000/credit-cards/authorize/
```

This will:
- Redirect you to Google OAuth consent screen
- After authorization, redirect back to `/credit-cards/oauth2callback/`
- Save the tokens to database

### 4.2 Extract All Recent Emails
After authorization, test extracting emails:

**Using curl:**
```bash
curl http://localhost:8000/credit-cards/extract-emails/
```

**Using browser:**
```
http://localhost:8000/credit-cards/extract-emails/
```

This will fetch emails from the last 30 days and save them to the database.

### 4.3 Check for New Emails
Check for new emails (last 30 minutes):

**Using curl:**
```bash
curl http://localhost:8000/credit-cards/check-new-emails/
```

**Using browser:**
```
http://localhost:8000/credit-cards/check-new-emails/
```

## Step 5: Verify in Django Admin

1. Go to: `http://localhost:8000/admin/`
2. Login with your superuser credentials
3. Check:
   - **Credit Cards → Gmail Tokens** - Should show your saved token
   - **Credit Cards → Gmail Emails** - Should show extracted emails

## Step 6: Check Database

You can also verify the data directly:

```bash
python manage.py shell
```

Then in the shell:
```python
from credit_cards.models import GmailToken, GmailEmail

# Check if token exists
token = GmailToken.objects.first()
print(f"Token exists: {token is not None}")

# Count emails
email_count = GmailEmail.objects.count()
print(f"Total emails: {email_count}")

# View recent emails
recent_emails = GmailEmail.objects.all()[:5]
for email in recent_emails:
    print(f"{email.subject[:50]}... - {email.category}")
```

## Troubleshooting

### Error: "GmailToken matching query does not exist"
- Make sure you've completed the OAuth flow by visiting `/credit-cards/authorize/` first

### Error: "GOOGLE_CLIENT_ID not found"
- Set the environment variables or ensure `credentials.json` exists

### Error: "Invalid redirect URI"
- Update your Google Cloud Console OAuth settings to include:
  `http://localhost:8000/credit-cards/oauth2callback/`

### No emails found
- Check if you have financial emails in your Gmail
- The search looks for emails from banks, credit cards, payment services
- Try the `/extract-emails/` endpoint (searches last 30 days) instead of `/check-new-emails/` (last 30 minutes)

## API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/credit-cards/authorize/` | GET | Start OAuth flow |
| `/credit-cards/oauth2callback/` | GET | OAuth callback (auto) |
| `/credit-cards/extract-emails/` | GET | Extract all recent emails (30 days) |
| `/credit-cards/check-new-emails/` | GET | Check for new emails (30 minutes) |


