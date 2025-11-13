# Postman Testing Guide for Credit Cards App

## Prerequisites

1. Make sure Django server is running:
   ```bash
   cd nance
   python manage.py runserver
   ```
   Server should be at: `http://localhost:8000`

2. Complete database migrations:
   ```bash
   python manage.py makemigrations credit_cards
   python manage.py migrate
   ```

---

## Endpoint 1: Authorize Gmail (OAuth Flow)

### Setup
**Method:** `GET`  
**URL:** `http://localhost:8000/credit-cards/authorize/`

### Steps in Postman:

1. **Create a new GET request**
   - Method: `GET`
   - URL: `http://localhost:8000/credit-cards/authorize/`

2. **Send the request**
   - Click "Send"
   - You'll get a redirect response (302 or 307)
   - **Important:** OAuth flow requires a browser, so this won't work directly in Postman

### Alternative: Use Browser First

**For OAuth, you MUST use a browser first:**

1. Open browser and go to: `http://localhost:8000/credit-cards/authorize/`
2. Complete Google OAuth consent
3. You'll be redirected to: `http://localhost:8000/credit-cards/oauth2callback/`
4. You should see: "Gmail authorization successful! Tokens saved securely."
5. **Now you can use Postman for other endpoints**

---

## Endpoint 2: Extract All Recent Emails

### Setup
**Method:** `GET`  
**URL:** `http://localhost:8000/credit-cards/extract-emails/`

### Postman Configuration:

1. **Create a new GET request**
   - Method: `GET`
   - URL: `http://localhost:8000/credit-cards/extract-emails/`

2. **Headers (Optional - if authentication required):**
   ```
   Authorization: Bearer YOUR_JWT_TOKEN
   ```
   (Note: Currently the endpoint doesn't require auth, but you can add it)

3. **Send the request**

### Expected Response:
```json
{
    "status": "success",
    "emails_found": 15,
    "emails_saved": 10,
    "message": "Successfully processed 15 emails, saved 10 new emails"
}
```

### Error Response (if no token):
```json
{
    "status": "error",
    "message": "GmailToken matching query does not exist."
}
```
**Solution:** Complete OAuth flow in browser first (see Endpoint 1)

---

## Endpoint 3: Check New Emails

### Setup
**Method:** `GET`  
**URL:** `http://localhost:8000/credit-cards/check-new-emails/`

### Postman Configuration:

1. **Create a new GET request**
   - Method: `GET`
   - URL: `http://localhost:8000/credit-cards/check-new-emails/`

2. **Send the request**

### Expected Response:
```json
{
    "status": "success",
    "new_emails_found": 2,
    "new_emails_saved": 1,
    "new_emails": [
        {
            "message_id": "abc123",
            "subject": "Credit Card Transaction Alert",
            "sender": "alerts@bank.com",
            "date": "Mon, 15 Jan 2025 10:30:00 +0000",
            "category": "transaction",
            "subcategory": "debit_transaction",
            "confidence": 85,
            "is_transaction": true,
            "is_statement": false,
            "is_notification": false,
            "amount": "500.00",
            "merchant": "Amazon",
            "transaction_type": "debit",
            "payment_method": null,
            "gmail_labels": ["IMPORTANT", "INBOX"]
        }
    ],
    "message": "Found 2 new emails, saved 1 new emails"
}
```

---

## Postman Collection Setup

### Create a Collection:

1. Click "New" → "Collection"
2. Name it: "Credit Cards API"
3. Add base URL variable:
   - Click on collection → Variables tab
   - Add variable:
     - **Variable:** `base_url`
     - **Initial Value:** `http://localhost:8000`
     - **Current Value:** `http://localhost:8000`

4. Use in requests: `{{base_url}}/credit-cards/extract-emails/`

---

## Complete Postman Request Examples

### Request 1: Extract Emails
```
GET {{base_url}}/credit-cards/extract-emails/
```

### Request 2: Check New Emails
```
GET {{base_url}}/credit-cards/check-new-emails/
```

### Request 3: Authorize (Browser Only)
```
GET {{base_url}}/credit-cards/authorize/
```
**Note:** This redirects to Google, so use browser instead.

---

## Testing Workflow

### Step-by-Step:

1. **First Time Setup (Browser):**
   - Open: `http://localhost:8000/credit-cards/authorize/`
   - Complete OAuth
   - Verify token saved (check admin or database)

2. **In Postman - Test Extract:**
   - GET: `http://localhost:8000/credit-cards/extract-emails/`
   - Check response for success

3. **In Postman - Test Check New:**
   - GET: `http://localhost:8000/credit-cards/check-new-emails/`
   - Check response for new emails

4. **Verify in Admin:**
   - Go to: `http://localhost:8000/admin/credit_cards/gmailemail/`
   - See extracted emails

---

## Troubleshooting in Postman

### Issue: "GmailToken matching query does not exist"
**Solution:** 
- Complete OAuth in browser first
- Go to: `http://localhost:8000/credit-cards/authorize/`

### Issue: "Connection refused" or "Could not get response"
**Solution:**
- Make sure Django server is running
- Check URL is correct: `http://localhost:8000`
- Verify no firewall blocking

### Issue: "Invalid redirect URI" (during OAuth)
**Solution:**
- Update Google Cloud Console
- Add: `http://localhost:8000/credit-cards/oauth2callback/`

### Issue: Empty response or no emails
**Solution:**
- Check if you have financial emails in Gmail
- Try `/extract-emails/` (30 days) instead of `/check-new-emails/` (30 minutes)
- Check server logs for errors

---

## Postman Environment Variables (Optional)

Create a Postman Environment:

1. Click "Environments" → "New"
2. Add variables:
   - `base_url`: `http://localhost:8000`
   - `api_base`: `http://localhost:8000/credit-cards`

3. Use in requests:
   ```
   GET {{base_url}}/credit-cards/extract-emails/
   ```

---

## Quick Test Scripts

### Pre-request Script (Optional):
```javascript
// Set timestamp
pm.environment.set("timestamp", new Date().toISOString());
```

### Test Script (Optional):
```javascript
// Check response status
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

// Check response structure
pm.test("Response has status field", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData).to.have.property('status');
});
```

---

## Summary

| Endpoint | Method | Postman URL | Notes |
|----------|--------|-------------|-------|
| Authorize | GET | `http://localhost:8000/credit-cards/authorize/` | Use browser first time |
| Extract Emails | GET | `http://localhost:8000/credit-cards/extract-emails/` | Works in Postman |
| Check New | GET | `http://localhost:8000/credit-cards/check-new-emails/` | Works in Postman |

**Remember:** Complete OAuth flow in browser before testing other endpoints in Postman!

