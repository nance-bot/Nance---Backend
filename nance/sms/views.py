from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import AAConsent, AADataSession, RawAATransaction, RawSMSTransaction, GmailToken, SMSMessage
from django.conf import settings
from django.core.cache import cache
import requests

import random
from rest_framework_simplejwt.tokens import RefreshToken
from .models import OTPRequest, CustomUser
from django.utils import timezone

def generate_otp():
    return str(random.randint(100000, 999999))

@api_view(['POST'])
def request_otp(request):
    mobile = request.data.get("mobile")
    if not mobile:
        return Response({"error": "Mobile number required"}, status=400)

    otp = generate_otp()

    # Save OTP
    OTPRequest.objects.create(mobile=mobile, otp=otp)

    # (Optional) Send OTP via SMS/email here
    print(f"OTP for {mobile}: {otp}")

    return Response({
        "message": "OTP sent successfully",
        "otp": otp
    })

@api_view(['POST'])
def verify_otp(request):
    mobile = request.data.get("mobile")
    otp = request.data.get("otp")

    if not mobile or not otp:
        return Response({"error": "Mobile and OTP required"}, status=400)

    try:
        otp_obj = OTPRequest.objects.filter(mobile=mobile, otp=otp).latest("created_at")
    except OTPRequest.DoesNotExist:
        return Response({"error": "Invalid OTP"}, status=400)

    if otp_obj.is_expired():
        return Response({"error": "OTP expired"}, status=400)

    # Create user if not exists
    user, created = CustomUser.objects.get_or_create(mobile=mobile, username=mobile)

    # Generate JWT
    refresh = RefreshToken.for_user(user)
    return Response({
        "refresh": str(refresh),
        "access": str(refresh.access_token)
    })

# Helper: get auth headers
def get_setu_headers():
    token = cache.get("setu_token")
    if not token:
        res = requests.post(
            "https://orgservice-prod.setu.co/v1/users/login",
            headers={"client": "bridge"},
            json={
                "clientID": settings.SETU_CLIENT_ID,
                "grant_type": "client_credentials",
                "secret": settings.SETU_CLIENT_SECRET,
            },
        )
        token = res.json().get("access_token")
        cache.set("setu_token", token, 60 * 14)  # cache for 14 min
    return {
        "Authorization": f"Bearer {token}",
        "x-client-id": settings.SETU_CLIENT_ID,
        "x-client-secret": settings.SETU_CLIENT_SECRET,
        "x-product-instance-id": settings.SETU_PRODUCT_INSTANCE_ID,
        "Content-Type": "application/json",
    }

# 🔹 1. Create Consent
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_consent(request):
    user = request.user
    vua = request.data["vua"]
    payload = {
        "consentDuration": {"unit": "MONTH", "value": "12"},
        "vua": vua,
        "dataRange": {
            "from": "2024-01-01T00:00:00Z",
            "to": "2025-12-31T23:59:59Z"
        },
        "context": []
    }
    headers = get_setu_headers()
    res = requests.post("https://fiu-sandbox.setu.co/v2/consents", json=payload, headers=headers)
    data = res.json()
    AAConsent.objects.create(user=user, vua=vua, consent_id=data["id"])
    return Response({"setu_full_response": data})

# 🔹 2. Poll Consent Status
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def poll_consent_status(request, consent_id):
    user = request.user
    print(f"Polling consent status for user: {user} (username: {user.username}), consent_id: {consent_id}")
    print(f"Full request path: {request.get_full_path()}")
    print(f"consent_id parameter: {consent_id}")

    headers = get_setu_headers()
    res = requests.get(f"https://fiu-sandbox.setu.co/v2/consents/{consent_id}", headers=headers)
    data = res.json()
    consent = AAConsent.objects.get(user=user,consent_id=consent_id)
    if data["status"] == "ACTIVE":
        consent.status = "ACTIVE"
        consent.vua = data.get("vua", consent.vua)
        consent.save()
    return Response({"status": consent.status, "vua": consent.vua , "setu_full_response": data})

# 🔹 3. Create Session (Only if consent ACTIVE)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_session(request):
    consent_id = request.data["consent_id"]
    consent = AAConsent.objects.get(consent_id=consent_id)
    if consent.status != "ACTIVE":
        return Response({"error": "Consent is not ACTIVE"}, status=400)
    
    payload = {
        "consentId": consent_id,
        "dataRange": {
            "from": "2025-08-01T00:00:00Z",
            "to": "2025-08-11T23:59:59Z"
        },
        "format": "json"
    }
    headers = get_setu_headers()
    res = requests.post("https://fiu-sandbox.setu.co/v2/sessions", json=payload, headers=headers)
    data = res.json()
    AADataSession.objects.create(consent=consent, session_id=data["id"], status="PENDING")
    return Response(data)

# 🔹 4. Fetch Transactions
    
from .utils import call_ml_model_util

@api_view(["POST"])
def call_ml_model(request):
    narration = request.data.get("narration")
    if not narration:
        return Response({"error": "Narration is required."}, status=400)

    try:
        result = call_ml_model_util(narration)
        return Response(result)
    except Exception as e:
        return Response({"error": str(e)}, status=500)

from pytz import timezone
from datetime import datetime
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def fetch_transactions(request, session_id):
    user = request.user
    headers = get_setu_headers()

    # Fetch session data from Setu
    res = requests.get(f"https://fiu-sandbox.setu.co/v2/sessions/{session_id}", headers=headers)
    data = res.json()

    # Update session status
    session = AADataSession.objects.get(session_id=session_id)
    session.status = data.get("status", "UNKNOWN")
    session.save()

    saved_count = 0

    fips = data.get("fips", [])
    for fip in fips:
        for acc in fip.get("accounts", []):
            txn_data = acc.get("data", {}).get("account", {}).get("transactions", {})
            for txn in txn_data.get("transaction", []):
                txn_id = txn.get("txnId")
                
                narration = txn.get("narration", "")
                # Clean and display narration safely
                clean_narration = str(narration).encode('utf-8', errors='ignore').decode('utf-8')
                print(f"Narration: {repr(clean_narration)}")

                # Skip if txn_id missing
                if not txn_id:
                    continue

                # ML parsing
                # parsed = call_ml_model_util(narration, source_type="Narration")
                # parsed_result = parsed.get("result", {})
                # is_transaction = parsed_result.get("is_transaction", False)

                # if not is_transaction:
                #     continue  # skip non-transactions

                # Use transactionTimestamp from raw txn and convert to IST
                parsed_date = None
                raw_txn_timestamp = txn.get("transactionTimestamp")
                if raw_txn_timestamp:
                    try:
                        # Parse the UTC datetime string
                        utc_time = datetime.fromisoformat(raw_txn_timestamp.replace("Z", "+00:00"))
                        # Convert to IST
                        ist_time = utc_time.astimezone(timezone("Asia/Kolkata"))
                        parsed_date = ist_time
                    except ValueError:
                        pass

                # Select parsed_merchant_name or normalized_account_name based on is_business
                # is_business = parsed_result.get("is_business", True)
                # merchant_or_account_name = (
                # parsed_result.get("merchant_name") if is_business
                # else parsed_result.get("normalized_account_name")
                # )

                _, created = RawAATransaction.objects.get_or_create(
                    txn_id=txn_id,
                    defaults={
                        "user": session.consent.user,
                        "consent": session.consent, 
                        "raw_payload": txn,
                        "narration": narration, 
                        # "parsed_amount": parsed_result.get("amount"),
                        "parsed_date": parsed_date,
                        # "parsed_merchant_name": parsed_result.get("merchant_name"),
                        #  "parsed_merchant_name": merchant_or_account_name,
                        "parsed_payment_mode": txn.get("mode"), #like UPI 
                        # "parsed_account_name": parsed_result.get("normalized_account_name"),
                        "parsed_transaction_type": txn.get("type"), #like debit , credit
                        # "parsed_received_content": parsed.get("received_content", narration), # storing the narration again to cross check whether the sended narration and the received narration to the model is same or not
                        # "aa_fetched_at": session.created_at,
                        # "main_category": parsed_result.get("main_category"),  
                        # "sub_category": parsed_result.get("sub_category"),  
                    }
                )

                if created:
                    saved_count += 1
                    # match_sms_transaction_for_aa(_)  # _ is the saved AA txn instance

    return Response({
        "saved_txns": saved_count,
        "setu_full_response": data
    })


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from datetime import datetime
import uuid

@api_view(["POST"])
# @permission_classes([IsAuthenticated])
def receive_sms_transaction(request):
    """
    Endpoint to receive raw SMS from frontend (Flutter)
    Expected payload:
    {
        "sms_text": "Payment of Rs. 500.00 made to XYZ via UPI",
        "timestamp": "2025-09-03T17:34:56"  # Mandatory - should be IST
    }
    """
    
    sms_text = request.data.get("sms_text", "")
    raw_timestamp = request.data.get("timestamp")

    if not sms_text or not raw_timestamp:
        return Response({"error": "sms_text and timestamp are required"}, status=400)

    # Parse timestamp (assumed to be IST)
    try:
        parsed_date = datetime.fromisoformat(raw_timestamp)
    except ValueError:
        return Response({"error": "Invalid timestamp format"}, status=400)

    # ML parsing
    parsed = call_ml_model_util(sms_text, source_type="SMS")
    parsed_result = parsed.get("result", {})
    is_transaction = parsed_result.get("is_transaction", False)

    if not is_transaction:
        return Response({"status": "Not a transaction"}, status=200)

    # Generate unique txn_id
    txn_id = f"sms-{uuid.uuid4()}"

    # Save to RawAATransaction
    RawSMSTransaction.objects.create(
        txn_id=txn_id,
        
        consent=None,  # No AA consent
        raw_payload={"source": "sms", "original_text": sms_text},
        narration=sms_text,
        parsed_amount=parsed_result.get("amount"),
        parsed_date=parsed_date,
        parsed_merchant_name=parsed_result.get("merchant_name"),
        parsed_payment_mode=parsed_result.get("payment_mode"),
        parsed_transaction_type=parsed_result.get("transaction_type"),
        parsed_received_content=parsed.get("received_content", sms_text),
        # aa_fetched_at=parsed_date,  # Assuming sms receive time is txn time
        main_category=parsed_result.get("main_category"),
        sub_category=parsed_result.get("sub_category"),
    )

    return Response({
        "status": "Transaction saved",
        # "txn_id": txn_id,
        # "parsed": parsed_result
    })

from difflib import SequenceMatcher
from django.utils.timezone import timedelta

def match_sms_transaction_for_aa(aa_txn, time_window_minutes=5):
    """
    Attempts to reconcile a single Account Aggregator (AA) transaction with a matching
    SMS-based transaction for the same user.

    This function is designed to help deduplicate or verify transaction data by matching
    real-time SMS transaction records with more reliable data fetched from AA sources.

    Matching Strategy:
        1. Anchors the AA transaction's timestamp (`parsed_date`) as the ground truth.
        2. Searches for SMS transactions within ±`time_window_minutes` of the AA timestamp.
        3. Applies the following matching criteria:
            - Required: Amount must match exactly.
            - Required: Transaction type (debit/credit) must match.
            - Optional: Payment mode should match if present in both.
            - Optional: Merchant name
    Parameters:
        aa_txn (RawAATransaction): The AA transaction instance (must already be saved to DB).
        time_window_minutes (int): Time window (in minutes) around the AA timestamp to consider SMS matches.

    Returns:
        RawSMSTransaction or None:
            - Returns the matched SMS transaction if found.
            - Returns None if no match is found.

    Side Effects:
        - If a match is found, both the AA and SMS transaction objects are updated:
            - `aa_txn.matched_sms_txn` is set.
            - `sms.matched_aa_txn` is set.
        - The updated objects are saved to the database.

    Assumptions:
        - Both AA and SMS transactions have `parsed_date` and `parsed_amount` populated.
        - Only unmatched SMS transactions are considered (i.e., `matched_aa_txn__isnull=True`).
        - Timezones are handled and normalized before calling this function.

    Limitations:
        - SMS merchant name parsing may be inconsistent; fuzzy matching may give false negatives/positives.
        - Assumes amount and type are strong indicators of match — which may not be sufficient in rare edge cases.

    Example:
        match_sms_transaction_for_aa(aa_txn, time_window_minutes=5)
    """


    # Sanity check: transaction must have timestamp and amount
    if not aa_txn.parsed_date or not aa_txn.parsed_amount:
        return None

    start_time = aa_txn.parsed_date - timedelta(minutes=time_window_minutes)
    end_time = aa_txn.parsed_date + timedelta(minutes=time_window_minutes)

    candidates = RawSMSTransaction.objects.filter(
        user=aa_txn.user,
        parsed_date__range=(start_time, end_time),
        matched_aa_txn__isnull=True  # only unmatched ones
    )

    for sms in candidates:
        # Core matching fields
        if sms.parsed_amount != aa_txn.parsed_amount:
            continue
        if sms.parsed_transaction_type != aa_txn.parsed_transaction_type:
            continue

        # Optional: check payment mode if available
        if sms.parsed_payment_mode and aa_txn.parsed_payment_mode:
            if sms.parsed_payment_mode != aa_txn.parsed_payment_mode:
                continue

        # Optional: fuzzy match merchant name
        if sms.parsed_merchant_name and aa_txn.parsed_merchant_name:
            if sms.parsed_merchant_name != aa_txn.parsed_merchant_name:
                continue

        # MATCH FOUND
        sms.matched_aa_txn = aa_txn
        aa_txn.matched_sms_txn = sms
        sms.save()
        aa_txn.save()

        return sms  # return the matched sms

    return None  # no match found


@api_view(["POST"])
def receive_sms_message(request):
    """
    Endpoint to receive raw SMS messages from frontend
    Expected payload:
    {
        "sms_text": "Your SMS message content here",
        "timestamp": "2025-01-15T10:30:00"  # ISO format timestamp
    }
    """
    
    sms_text = request.data.get("sms_text", "")
    raw_timestamp = request.data.get("timestamp")

    if not sms_text or not raw_timestamp:
        return Response({"error": "sms_text and timestamp are required"}, status=400)

    # Parse timestamp
    try:
        parsed_timestamp = datetime.fromisoformat(raw_timestamp)
    except ValueError:
        return Response({"error": "Invalid timestamp format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"}, status=400)

    # Create SMS message record
    sms_message = SMSMessage.objects.create(
        user=request.user if hasattr(request, 'user') and request.user.is_authenticated else None,
        sms_text=sms_text,
        timestamp=parsed_timestamp
    )

    return Response({
        "status": "SMS message saved successfully",
        "sms_id": sms_message.id,
        "timestamp": sms_message.timestamp.isoformat(),
        "message": "SMS stored in database"
    })


# ---------------------------------------------------

# Gmail OAuth Integration Logic


# gmail_auth/views.py
import os
import json
from django.shortcuts import redirect
from django.http import HttpResponse
from google_auth_oauthlib.flow import Flow
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
# set OAUTHLIB_INSECURE_TRANSPORT=1

# Absolute path to credentials
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOOGLE_OAUTH2_CLIENT_SECRETS_JSON = os.path.join(BASE_DIR, 'sms', 'credentials.json')

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
REDIRECT_URI = 'http://localhost:8000/oauth2callback/'  # must match Google config

# Step 1: Start OAuth flow
def authorize(request):
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

# Step 2: OAuth callback
def oauth2callback(request):
    state = request.session['state']

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
        # user=user,
        defaults={
            'access_token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_expiry': expiry
        }
    )

    # Return success message without exposing tokens
    return HttpResponse("Gmail authorization successful! Tokens saved securely.")

# import os
# from django.shortcuts import redirect, HttpResponse
# from django.utils import timezone
# from google_auth_oauthlib.flow import Flow
# from google.oauth2.credentials import Credentials
# from googleapiclient.discovery import build
# from .models import GmailToken
# from django.contrib.auth.models import User
# from datetime import timedelta
# from google.auth.transport.requests import Request
# # Allow HTTP for dev
# os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, 'sms', 'credentials.json')
# SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
# REDIRECT_URI = 'http://localhost:8000/oauth2callback/'

# def authorize(request):
#     flow = Flow.from_client_secrets_file(
#         CLIENT_SECRETS_FILE,
#         scopes=SCOPES,
#         redirect_uri=REDIRECT_URI
#     )
#     auth_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
#     request.session['state'] = state
#     return redirect(auth_url)

# def oauth2callback(request):
#     state = request.session.get('state')
#     flow = Flow.from_client_secrets_file(
#         CLIENT_SECRETS_FILE,
#         scopes=SCOPES,
#         state=state,
#         redirect_uri=REDIRECT_URI
#     )
#     try:
#         flow.fetch_token(authorization_response=request.build_absolute_uri())
#     except Exception as e:
#         print(f"OAuth2 error: {str(e)}")
#         return HttpResponse(f"OAuth2 error: {str(e)}", status=400)

#     creds = flow.credentials

#     expiry = timezone.make_aware(creds.expiry) if creds.expiry else None

#     # user_email = creds.id_token['email']
#     # user, _ = User.objects.get_or_create(username=user_email, email=user_email)

#     # Save token
#     GmailToken.objects.update_or_create(
#         # user=user,
#         defaults={
#             'access_token': creds.token,
#             'refresh_token': creds.refresh_token,
#             'token_expiry': expiry
#         }
#     )
#     return HttpResponse("Authorization successful!")

from django.http import JsonResponse
from .gmail import check_for_new_credit_card_emails, get_all_recent_credit_card_emails
from .models import GmailEmail
from django.utils import timezone
from datetime import datetime
import re

def extract_credit_card_emails(request):
    """Extract ALL recent credit card spending emails from Gmail (last 7 days) and store in database."""
    try:
        # Get all recent emails from Gmail (last 7 days)
        extracted_emails = get_all_recent_credit_card_emails()
        
        saved_count = 0
        
        for email_data in extracted_emails:
            # Parse email date
            try:
                # Parse Gmail date format
                email_date = datetime.strptime(email_data['date'], '%a, %d %b %Y %H:%M:%S %z')
            except:
                email_date = timezone.now()
            
            # Create or update GmailEmail record with Fold-like categorization
            gmail_email, created = GmailEmail.objects.get_or_create(
                message_id=email_data['message_id'],
                defaults={
                    'user': request.user if hasattr(request, 'user') and request.user.is_authenticated else None,
                    'thread_id': email_data['thread_id'],
                    'subject': email_data['subject'],
                    'sender': email_data['sender'],
                    'email_date': email_date,
                    'body_text': email_data['body_text'],
                    'category': email_data.get('category', 'unknown'),
                    'subcategory': email_data.get('subcategory', 'unknown'),
                    'confidence': email_data.get('confidence', 0),
                    'is_transaction': email_data.get('is_transaction', False),
                    'is_statement': email_data.get('is_statement', False),
                    'is_notification': email_data.get('is_notification', False),
                    'gmail_labels': email_data.get('labels', []),
                }
            )
            
            if created:
                saved_count += 1
                # Try to parse transaction details from email text
                parse_transaction_details(gmail_email)
        
        return JsonResponse({
            'status': 'success',
            'emails_found': len(extracted_emails),
            'emails_saved': saved_count,
            'message': f'Successfully processed {len(extracted_emails)} emails, saved {saved_count} new emails'
        })
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

def check_new_credit_card_emails(request):
    """Check for NEW credit card emails (last 1 hour) - for real-time monitoring."""
    try:
        # Get only new emails from Gmail (last 1 hour)
        extracted_emails = check_for_new_credit_card_emails()
        
        saved_count = 0
        new_emails = []
        
        for email_data in extracted_emails:
            # Parse email date
            try:
                # Parse Gmail date format
                email_date = datetime.strptime(email_data['date'], '%a, %d %b %Y %H:%M:%S %z')
            except:
                email_date = timezone.now()
            
            # Create or update GmailEmail record with Fold-like categorization
            gmail_email, created = GmailEmail.objects.get_or_create(
                message_id=email_data['message_id'],
                defaults={
                    'user': request.user if hasattr(request, 'user') and request.user.is_authenticated else None,
                    'thread_id': email_data['thread_id'],
                    'subject': email_data['subject'],
                    'sender': email_data['sender'],
                    'email_date': email_date,
                    'body_text': email_data['body_text'],
                    'category': email_data.get('category', 'unknown'),
                    'subcategory': email_data.get('subcategory', 'unknown'),
                    'confidence': email_data.get('confidence', 0),
                    'is_transaction': email_data.get('is_transaction', False),
                    'is_statement': email_data.get('is_statement', False),
                    'is_notification': email_data.get('is_notification', False),
                    'gmail_labels': email_data.get('labels', []),
                }
            )
            
            if created:
                saved_count += 1
                # Try to parse transaction details from email text
                parse_transaction_details(gmail_email)
                
                # Add to new emails list for response (Fold-like format)
                new_emails.append({
                    'message_id': email_data['message_id'],
                    'subject': email_data['subject'],
                    'sender': email_data['sender'],
                    'date': email_data['date'],
                    'category': gmail_email.category,
                    'subcategory': gmail_email.subcategory,
                    'confidence': gmail_email.confidence,
                    'is_transaction': gmail_email.is_transaction,
                    'is_statement': gmail_email.is_statement,
                    'is_notification': gmail_email.is_notification,
                    'amount': str(gmail_email.parsed_amount) if gmail_email.parsed_amount else None,
                    'merchant': gmail_email.parsed_merchant,
                    'transaction_type': gmail_email.parsed_transaction_type,
                    'payment_method': gmail_email.parsed_payment_method,
                    'gmail_labels': gmail_email.gmail_labels
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

def parse_transaction_details(gmail_email):
    """Parse transaction details from email text."""
    text = f"{gmail_email.subject} {gmail_email.body_text}".lower()
    
    # Extract amount (look for Rs., INR, ₹, etc.)
    amount_patterns = [
        r'rs\.?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
        r'inr\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
        r'₹\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
        r'amount\s*:?\s*rs\.?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
        r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*rupees?'
    ]
    
    for pattern in amount_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                amount_str = match.group(1).replace(',', '')
                gmail_email.parsed_amount = float(amount_str)
                break
            except:
                continue
    
    # Determine transaction type
    if any(word in text for word in ['debit', 'spent', 'purchase', 'payment', 'paid']):
        gmail_email.parsed_transaction_type = 'debit'
    elif any(word in text for word in ['credit', 'received', 'refund']):
        gmail_email.parsed_transaction_type = 'credit'
    
    # Extract merchant name (basic extraction)
    merchant_patterns = [
        r'at\s+([A-Za-z\s]+?)(?:\s+on|\s+for|\s+via|\s+using|$)',
        r'merchant\s*:?\s*([A-Za-z\s]+?)(?:\s+on|\s+for|\s+via|$)',
        r'to\s+([A-Za-z\s]+?)(?:\s+on|\s+for|\s+via|$)'
    ]
    
    for pattern in merchant_patterns:
        match = re.search(pattern, text)
        if match:
            merchant = match.group(1).strip()
            if len(merchant) > 2 and len(merchant) < 50:  # Reasonable merchant name length
                gmail_email.parsed_merchant = merchant.title()
                break
    
    gmail_email.save()
    

# Gmail-only approach for credit card statements




# set OAUTHLIB_INSECURE_TRANSPORT=1