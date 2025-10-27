# gmail_auth/gmail.py

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from .models import GmailToken
from django.utils import timezone
from django.conf import settings
import base64
import os
from .pdf_utils import extract_text_from_pdf

def get_gmail_service():
    token = GmailToken.objects.first()
    creds = Credentials(
        token=token.access_token,
        refresh_token=token.refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=['https://www.googleapis.com/auth/gmail.readonly']
    )

    if creds.expired and creds.refresh_token:
        creds.refresh()

        # Save new token
        token.access_token = creds.token
        token.token_expiry = timezone.now() + creds.expiry
        token.save()

    service = build('gmail', 'v1', credentials=creds)
    return service

def search_and_extract_credit_card_emails(check_new_only=True):
    """Search Gmail for credit card spending notification emails - Fold-like approach."""
    service = get_gmail_service()
    
    # Fold-like comprehensive search for financial emails
    # If check_new_only=True, search for emails from last 30 minutes
    # If check_new_only=False, search for emails from last 30 days
    time_filter = 'newer_than:30m' if check_new_only else 'newer_than:30d'
    
    # Comprehensive search query like Fold app
    query = f'{time_filter} (from:*bank.com OR from:*card.com OR from:*credit.com OR from:*financial.com OR from:*payment.com OR from:*wallet.com OR from:*upi.com OR subject:("credit card") OR subject:("debit card") OR subject:("transaction") OR subject:("payment") OR subject:("spent") OR subject:("purchase") OR subject:("billing") OR subject:("statement") OR subject:("receipt") OR subject:("invoice") OR subject:("refund") OR subject:("cashback") OR subject:("reward") OR subject:("balance") OR subject:("limit") OR subject:("due") OR subject:("overdue") OR subject:("minimum payment") OR subject:("auto pay") OR subject:("subscription") OR subject:("recurring") OR subject:("renewal"))'
    
    results = service.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])

    extracted_emails = []
    
    for msg in messages:
        msg_detail = service.users().messages().get(userId='me', id=msg['id']).execute()
        
        # Extract email metadata
        headers = msg_detail['payload'].get('headers', [])
        subject = ""
        sender = ""
        date = ""
        labels = []
        
        for header in headers:
            if header['name'] == 'Subject':
                subject = header['value']
            elif header['name'] == 'From':
                sender = header['value']
            elif header['name'] == 'Date':
                date = header['value']
        
        # Get Gmail labels (like Fold's categorization)
        if 'labelIds' in msg_detail:
            labels = msg_detail['labelIds']
        
        # Extract email body text
        email_text = extract_email_body(msg_detail['payload'])
        
        # Fold-like email categorization
        email_category = categorize_email_like_fold(subject, email_text, sender, labels)
        
        # Only process emails that are financial/credit card related
        if email_category['is_financial'] and email_category['category'] != 'non_financial':
            email_data = {
                'message_id': msg['id'],
                'subject': subject,
                'sender': sender,
                'date': date,
                'body_text': email_text,
                'thread_id': msg_detail.get('threadId'),
                'labels': labels,
                'category': email_category['category'],
                'subcategory': email_category['subcategory'],
                'confidence': email_category['confidence'],
                'is_transaction': email_category['is_transaction'],
                'is_statement': email_category['is_statement'],
                'is_notification': email_category['is_notification']
            }
            extracted_emails.append(email_data)
            
            print(f"Financial Email Found ({email_category['category']}):")
            print(f"   Subject: {subject}")
            print(f"   From: {sender}")
            print(f"   Category: {email_category['category']}")
            print(f"   Subcategory: {email_category['subcategory']}")
            print(f"   Confidence: {email_category['confidence']}%")
            # Show clean text preview
            clean_preview = email_text[:150].strip()
            if len(email_text) > 150:
                clean_preview += "..."
            print(f"   Text: {clean_preview}")
            print("-" * 50)
    
    return extracted_emails

def categorize_email_like_fold(subject, body_text, sender, labels):
    """Categorize emails like Fold app - comprehensive financial email classification."""
    text_to_analyze = f"{subject} {body_text}".lower()
    sender_lower = sender.lower()
    
    # Initialize categorization
    category = "unknown"
    subcategory = "unknown"
    confidence = 0
    is_financial = False
    is_transaction = False
    is_statement = False
    is_notification = False
    
    # Exclude non-financial emails (false positive prevention)
    non_financial_keywords = [
        'google cloud', 'verification', 'account verification', 'security verification',
        'two-factor', '2fa', 'password reset', 'login attempt', 'suspicious activity',
        'newsletter', 'marketing', 'promotion', 'offer', 'discount', 'sale',
        'social media', 'facebook', 'twitter', 'instagram', 'linkedin',
        'job application', 'interview', 'resume', 'career',
        'news', 'update', 'announcement', 'maintenance', 'downtime'
    ]
    
    # Check if email should be excluded
    if any(keyword in text_to_analyze for keyword in non_financial_keywords):
        return {
            'category': 'non_financial',
            'subcategory': 'excluded',
            'confidence': 0,
            'is_financial': False,
            'is_transaction': False,
            'is_statement': False,
            'is_notification': False
        }
    
    # Bank and financial institution detection (exclude Google services)
    bank_domains = [
        'hdfcbank.com', 'icicibank.com', 'sbi.co.in', 'axisbank.com', 'kotak.com',
        'yesbank.com', 'indianbank.com', 'pnb.com', 'bob.com', 'unionbank.com',
        'canarabank.com', 'syndicatebank.com', 'bankofbaroda.com', 'centralbank.com',
        'card.com', 'credit.com', 'financial.com', 'payment.com', 'wallet.com',
        'paytm.com', 'phonepe.com', 'gpay.com', 'amazonpay.com', 'mobikwik.com',
        # Add your personal Gmail for testing purposes (but exclude Google services)
        'm.rajkumarmaga8@gmail.com'
    ]
    
    # Exclude Google services from bank detection
    google_services = ['google.com', 'googleapis.com', 'gmail.com', 'googleusercontent.com']
    is_google_service = any(service in sender_lower for service in google_services)
    
    is_from_bank = any(domain in sender_lower for domain in bank_domains) and not is_google_service
    
    # Transaction detection patterns
    transaction_keywords = [
        'transaction', 'payment', 'purchase', 'spent', 'debit', 'credit',
        'paid', 'charged', 'billed', 'withdrawal', 'deposit', 'transfer',
        'upi', 'pos', 'atm', 'online', 'merchant', 'vendor'
    ]
    
    # Statement detection patterns
    statement_keywords = [
        'statement', 'bill', 'invoice', 'receipt', 'summary', 'monthly',
        'quarterly', 'annual', 'report', 'account summary'
    ]
    
    # Notification detection patterns
    notification_keywords = [
        'alert', 'notification', 'reminder', 'update', 'confirmation',
        'verification', 'security', 'fraud', 'suspicious', 'unusual'
    ]
    
    # Amount patterns
    amount_patterns = [
        r'rs\.?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
        r'inr\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
        r'₹\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
        r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*rupees?'
    ]
    
    # Calculate confidence based on various factors
    confidence_factors = []
    
    # Bank sender confidence
    if is_from_bank:
        confidence_factors.append(30)
        is_financial = True
    
    # Transaction keywords confidence
    transaction_count = sum(1 for keyword in transaction_keywords if keyword in text_to_analyze)
    if transaction_count > 0:
        confidence_factors.append(min(transaction_count * 15, 40))
        is_transaction = True
        is_financial = True
    
    # Statement keywords confidence
    statement_count = sum(1 for keyword in statement_keywords if keyword in text_to_analyze)
    if statement_count > 0:
        confidence_factors.append(min(statement_count * 20, 35))
        is_statement = True
        is_financial = True
    
    # Notification keywords confidence
    notification_count = sum(1 for keyword in notification_keywords if keyword in text_to_analyze)
    if notification_count > 0:
        confidence_factors.append(min(notification_count * 10, 25))
        is_notification = True
        is_financial = True
    
    # Amount detection confidence
    import re
    has_amount = any(re.search(pattern, text_to_analyze) for pattern in amount_patterns)
    if has_amount:
        confidence_factors.append(20)
        is_financial = True
    
    # Determine category based on highest confidence
    confidence = sum(confidence_factors)
    
    if is_transaction and confidence > 50:
        category = "transaction"
        if 'credit' in text_to_analyze or 'received' in text_to_analyze:
            subcategory = "credit_transaction"
        elif 'debit' in text_to_analyze or 'spent' in text_to_analyze:
            subcategory = "debit_transaction"
        elif 'refund' in text_to_analyze:
            subcategory = "refund_transaction"
        else:
            subcategory = "general_transaction"
    elif is_statement and confidence > 40:
        category = "statement"
        if 'monthly' in text_to_analyze:
            subcategory = "monthly_statement"
        elif 'credit card' in text_to_analyze:
            subcategory = "credit_card_statement"
        else:
            subcategory = "account_statement"
    elif is_notification and confidence > 30:
        category = "notification"
        if 'security' in text_to_analyze or 'fraud' in text_to_analyze:
            subcategory = "security_alert"
        elif 'balance' in text_to_analyze:
            subcategory = "balance_notification"
        else:
            subcategory = "general_notification"
    elif is_financial:
        category = "financial"
        subcategory = "general_financial"
    
    return {
        'category': category,
        'subcategory': subcategory,
        'confidence': min(confidence, 100),
        'is_financial': is_financial,
        'is_transaction': is_transaction,
        'is_statement': is_statement,
        'is_notification': is_notification
    }

def check_for_new_credit_card_emails():
    """Check for new credit card emails (last 30 minutes) - Fold-like real-time monitoring."""
    return search_and_extract_credit_card_emails(check_new_only=True)

def get_all_recent_credit_card_emails():
    """Get all recent credit card emails (last 30 days) - Fold-like initial setup."""
    return search_and_extract_credit_card_emails(check_new_only=False)

def extract_email_body(payload):
    """Extract text content from email payload."""
    body = ""
    
    try:
        if 'parts' in payload:
            # Multi-part message
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                        break
                elif part['mimeType'] == 'text/html':
                    if 'data' in part['body']:
                        # For HTML emails, we'll extract plain text
                        html_content = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                        # Simple HTML tag removal (you might want to use BeautifulSoup for better parsing)
                        import re
                        body = re.sub('<[^<]+?>', '', html_content)
                        break
        else:
            # Single part message
            if payload['mimeType'] == 'text/plain' and 'data' in payload['body']:
                body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
            elif payload['mimeType'] == 'text/html' and 'data' in payload['body']:
                html_content = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
                import re
                body = re.sub('<[^<]+?>', '', html_content)
    except Exception as e:
        print(f"Email body extraction error: {e}")
        body = ""
    
    # Clean the extracted text
    body = clean_email_text(body)
    return body.strip()

def clean_email_text(text):
    """Clean email text by removing unwanted characters and formatting."""
    import re
    
    if not text:
        return ""
    
    # Remove forwarded message headers
    text = re.sub(r'---------- Forwarded message ---------.*?From:', 'From:', text, flags=re.DOTALL)
    
    # Remove carriage returns and normalize line breaks
    text = text.replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ')
    
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Remove HTML comments
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    
    # Remove CSS media queries and styles
    text = re.sub(r'@media[^}]+}', '', text, flags=re.DOTALL)
    
    # Remove remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove special characters that don't add value
    text = re.sub(r'[^\w\s\.\,\:\!\?\@\#\$\%\₹\-\+\=\/]', '', text)
    
    # Clean up multiple spaces again
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def is_credit_card_email(subject, body_text, sender):
    """Check if email is related to credit card spending."""
    credit_card_keywords = [
        'credit card', 'debit card', 'card transaction', 'payment', 'spent', 'purchase',
        'transaction', 'rs.', 'rupee', 'inr', 'amount', 'balance', 'card ending',
        'merchant', 'pos', 'atm', 'online', 'upi', 'net banking'
    ]
    
    # Check subject and body for credit card related keywords
    text_to_check = f"{subject} {body_text}".lower()
    
    # Count how many keywords are found
    keyword_count = sum(1 for keyword in credit_card_keywords if keyword in text_to_check)
    
    # Also check if sender is from a bank or financial institution (exclude Google services)
    bank_domains = ['m.rajkumarmaga8@gmail.com','bank.com', 'bank.co.in', 'card.com', 'credit.com', 'hdfcbank.com', 'icicibank.com', 'sbi.co.in']
    google_services = ['google.com', 'googleapis.com', 'gmail.com', 'googleusercontent.com']
    is_google_service = any(service in sender.lower() for service in google_services)
    is_bank_email = any(domain in sender.lower() for domain in bank_domains) and not is_google_service
    
    # Return True if it has credit card keywords or is from a bank
    return keyword_count >= 2 or is_bank_email