import os
from django.shortcuts import redirect
from django.http import HttpResponse, JsonResponse
from google_auth_oauthlib.flow import Flow
from django.utils import timezone
from django.utils import timezone as tz
from datetime import datetime
import re
from .models import GmailToken, GmailEmail
from .gmail import check_for_new_credit_card_emails, get_all_recent_credit_card_emails

# Allow HTTP for local development (OAuth requires HTTPS by default)
# Only set this in development, never in production!
if not os.environ.get('RENDER') and not os.environ.get('PRODUCTION'):
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Absolute path to credentials
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOOGLE_OAUTH2_CLIENT_SECRETS_JSON = os.path.join(BASE_DIR, 'sms', 'credentials.json')

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Determine redirect URI based on environment
# In production (Render), use the production URL
# In local development, use localhost
import os
if os.environ.get('RENDER') or os.environ.get('PRODUCTION'):
    # Production URL
    REDIRECT_URI = 'https://nance-backend.onrender.com/credit-cards/oauth2callback/'
else:
    # Local development
    REDIRECT_URI = 'http://localhost:8000/credit-cards/oauth2callback/'

# Check if we should use environment variables instead of credentials.json
USE_ENV_VARS = os.environ.get('GOOGLE_CLIENT_ID') and os.environ.get('GOOGLE_CLIENT_SECRET')

# Step 1: Start OAuth flow
def authorize(request):
    try:
        from django.conf import settings
        
        # Check if using environment variables
        if USE_ENV_VARS:
            # Use environment variables
            client_config = {
                "web": {
                    "client_id": os.environ.get('GOOGLE_CLIENT_ID'),
                    "client_secret": os.environ.get('GOOGLE_CLIENT_SECRET'),
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [REDIRECT_URI]
                }
            }
            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=REDIRECT_URI,
            )
        else:
            # Use credentials.json file
            if not os.path.exists(GOOGLE_OAUTH2_CLIENT_SECRETS_JSON):
                return HttpResponse(
                    f"<h2>Error: credentials.json not found</h2>"
                    f"<p>File path: <code>{GOOGLE_OAUTH2_CLIENT_SECRETS_JSON}</code></p>"
                    f"<h3>Option 1: Download credentials.json</h3>"
                    f"<ol>"
                    f"<li>Go to <a href='https://console.cloud.google.com/'>Google Cloud Console</a></li>"
                    f"<li>Select your project → APIs & Services → Credentials</li>"
                    f"<li>Create OAuth 2.0 Client ID (if needed)</li>"
                    f"<li>Download JSON and save as: <code>{GOOGLE_OAUTH2_CLIENT_SECRETS_JSON}</code></li>"
                    f"</ol>"
                    f"<h3>Option 2: Use Environment Variables</h3>"
                    f"<p>Set these environment variables:</p>"
                    f"<ul>"
                    f"<li><code>GOOGLE_CLIENT_ID</code></li>"
                    f"<li><code>GOOGLE_CLIENT_SECRET</code></li>"
                    f"</ul>"
                    f"<p>Then restart the server.</p>",
                    status=400
                )
            
            flow = Flow.from_client_secrets_file(
                GOOGLE_OAUTH2_CLIENT_SECRETS_JSON,
                scopes=SCOPES,
                redirect_uri=REDIRECT_URI,
            )

        authorization_url, state = flow.authorization_url(
            access_type='offline',  # so we get refresh_token
            include_granted_scopes='true'
        )
        
        request.session['state'] = state
        return redirect(authorization_url)
    except FileNotFoundError as e:
        return HttpResponse(
            f"Error: credentials.json file not found.<br>"
            f"Path: {GOOGLE_OAUTH2_CLIENT_SECRETS_JSON}<br>"
            f"Error: {str(e)}",
            status=400
        )
    except Exception as e:
        return HttpResponse(
            f"Error during OAuth authorization:<br>{str(e)}<br><br>"
            f"Please check:<br>"
            f"1. credentials.json exists at: {GOOGLE_OAUTH2_CLIENT_SECRETS_JSON}<br>"
            f"2. File is valid JSON format<br>"
            f"3. Google OAuth credentials are correct",
            status=500
        )

# Step 2: OAuth callback
def oauth2callback(request):
    try:
        state = request.session.get('state')
        if not state:
            return HttpResponse(
                "Error: OAuth state not found in session. Please start authorization again.",
                status=400
            )

        # Check if using environment variables
        if USE_ENV_VARS:
            client_config = {
                "web": {
                    "client_id": os.environ.get('GOOGLE_CLIENT_ID'),
                    "client_secret": os.environ.get('GOOGLE_CLIENT_SECRET'),
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [REDIRECT_URI]
                }
            }
            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                state=state,
                redirect_uri=REDIRECT_URI
            )
        else:
            if not os.path.exists(GOOGLE_OAUTH2_CLIENT_SECRETS_JSON):
                return HttpResponse(
                    f"Error: credentials.json not found at {GOOGLE_OAUTH2_CLIENT_SECRETS_JSON}",
                    status=400
                )

            flow = Flow.from_client_secrets_file(
                GOOGLE_OAUTH2_CLIENT_SECRETS_JSON,
                scopes=SCOPES,
                state=state,
                redirect_uri=REDIRECT_URI
            )

        flow.fetch_token(authorization_response=request.build_absolute_uri())

        credentials = flow.credentials
        expiry = timezone.make_aware(credentials.expiry) if credentials.expiry else None

        GmailToken.objects.update_or_create(
            defaults={
                'access_token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_expiry': expiry
            }
        )

        # Return success message without exposing tokens
        return HttpResponse("Gmail authorization successful! Tokens saved securely.")
    except Exception as e:
        return HttpResponse(
            f"Error during OAuth callback:<br>{str(e)}<br><br>"
            f"Please try authorizing again.",
            status=500
        )

def check_setup(request):
    """Diagnostic endpoint to check OAuth setup."""
    checks = {
        'credentials_file_exists': os.path.exists(GOOGLE_OAUTH2_CLIENT_SECRETS_JSON),
        'credentials_file_path': GOOGLE_OAUTH2_CLIENT_SECRETS_JSON,
        'redirect_uri': REDIRECT_URI,
        'google_client_id_set': bool(os.environ.get('GOOGLE_CLIENT_ID')),
        'google_client_secret_set': bool(os.environ.get('GOOGLE_CLIENT_SECRET')),
    }
    
    # Try to read credentials file if it exists
    if checks['credentials_file_exists']:
        try:
            import json
            with open(GOOGLE_OAUTH2_CLIENT_SECRETS_JSON, 'r') as f:
                creds_data = json.load(f)
                checks['credentials_file_valid'] = True
                checks['credentials_type'] = creds_data.get('type', 'unknown')
        except Exception as e:
            checks['credentials_file_valid'] = False
            checks['credentials_file_error'] = str(e)
    else:
        checks['credentials_file_valid'] = False
    
    # Check if token exists
    from .models import GmailToken
    token_exists = GmailToken.objects.exists()
    checks['token_exists_in_db'] = token_exists
    
    return JsonResponse(checks)

def extract_credit_card_emails(request):
    """Extract ALL recent credit card spending emails from Gmail (last 30 days) and store in database."""
    try:
        # Get all recent emails from Gmail (last 30 days)
        extracted_emails = get_all_recent_credit_card_emails()
        
        saved_count = 0
        
        for email_data in extracted_emails:
            # Parse email date
            try:
                # Parse Gmail date format
                email_date = datetime.strptime(email_data['date'], '%a, %d %b %Y %H:%M:%S %z')
            except:
                email_date = tz.now()
            
            # Create or update GmailEmail record - just basic info and full text
            gmail_email, created = GmailEmail.objects.get_or_create(
                message_id=email_data['message_id'],
                defaults={
                    'user': request.user if hasattr(request, 'user') and request.user.is_authenticated else None,
                    'thread_id': email_data['thread_id'],
                    'subject': email_data['subject'],
                    'sender': email_data['sender'],
                    'email_date': email_date,
                    'body_text': email_data['body_text'],
                }
            )
            
            if created:
                saved_count += 1
        
        return JsonResponse({
            'status': 'success',
            'emails_found': len(extracted_emails),
            'emails_saved': saved_count,
            'message': f'Successfully processed {len(extracted_emails)} emails, saved {saved_count} new emails'
        })
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

def check_new_credit_card_emails(request):
    """Check for NEW credit card emails (last 30 minutes) - for real-time monitoring."""
    try:
        # Get only new emails from Gmail (last 30 minutes)
        extracted_emails = check_for_new_credit_card_emails()
        
        saved_count = 0
        new_emails = []
        
        for email_data in extracted_emails:
            # Parse email date
            try:
                # Parse Gmail date format
                email_date = datetime.strptime(email_data['date'], '%a, %d %b %Y %H:%M:%S %z')
            except:
                email_date = tz.now()
            
            # Create or update GmailEmail record - just basic info and full text
            gmail_email, created = GmailEmail.objects.get_or_create(
                message_id=email_data['message_id'],
                defaults={
                    'user': request.user if hasattr(request, 'user') and request.user.is_authenticated else None,
                    'thread_id': email_data['thread_id'],
                    'subject': email_data['subject'],
                    'sender': email_data['sender'],
                    'email_date': email_date,
                    'body_text': email_data['body_text'],
                }
            )
            
            if created:
                saved_count += 1
                
                # Add to new emails list - just basic info
                new_emails.append({
                    'message_id': email_data['message_id'],
                    'subject': email_data['subject'],
                    'sender': email_data['sender'],
                    'date': email_data['date'],
                    'body_text': email_data['body_text'],
                })
        
        return JsonResponse({
            'status': 'success',
            'new_emails_found': len(extracted_emails),
            'new_emails_saved': saved_count,
            'new_emails': new_emails,
            'message': f'Found {len(extracted_emails)} new emails, saved {saved_count} new emails'
        })
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


