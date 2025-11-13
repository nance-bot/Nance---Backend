from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import AAConsent, AADataSession, RawAATransaction, RawSMSTransaction, SMSMessage
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
        "timestamp": "2025-01-15T10:30:00",  # ISO format timestamp
        "status": "optional status string",
        "external_id": "optional external id string"
    }
    """
    
    sms_text = request.data.get("sms_text", "")
    raw_timestamp = request.data.get("timestamp")
    status = request.data.get("status", None)
    external_id = request.data.get("external_id", None)

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
        timestamp=parsed_timestamp,
        status=status,
        external_id=external_id
    )

    return Response({
        "result": "SMS message saved successfully",
        "sms_id": sms_message.id,
        "timestamp": sms_message.timestamp.isoformat(),
        "status": sms_message.status,
        "external_id": sms_message.external_id,
        "message": "SMS stored in database"
    })

