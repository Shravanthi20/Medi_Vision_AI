import os
import urllib.request
import urllib.parse
import json
import base64
from datetime import datetime

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER", "") # e.g. "whatsapp:+14155238886"

def send_whatsapp_receipt(bill_id: str, phone: str, message: str) -> dict:
    """
    Sends a WhatsApp message using Twilio's API.
    Returns a dictionary with 'status' and 'provider_message_id'.
    """
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_WHATSAPP_NUMBER:
        print(f"Twilio credentials not set. Mocking WhatsApp message to {phone}: {message}")
        return {
            "status": "sent",
            "provider_message_id": f"mock_msg_{int(datetime.now().timestamp())}"
        }

    # Ensure phone number format is correct (e.g., add +91 if missing, assuming India based on currency)
    formatted_phone = phone.strip()
    if not formatted_phone.startswith('+'):
        # Just an assumption, typically you'd want to validate this strictly
        if len(formatted_phone) == 10:
            formatted_phone = f"+91{formatted_phone}"
    
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    
    data = urllib.parse.urlencode({
        "To": f"whatsapp:{formatted_phone}",
        "From": TWILIO_WHATSAPP_NUMBER,
        "Body": message
    }).encode("utf-8")

    auth_string = f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}"
    base64_auth = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Basic {base64_auth}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req) as response:
            resp_data = json.loads(response.read().decode("utf-8"))
            return {
                "status": "sent",
                "provider_message_id": resp_data.get("sid", "")
            }
    except urllib.error.HTTPError as e:
        error_info = e.read().decode("utf-8")
        print(f"Twilio API Error: {error_info}")
        return {
            "status": "failed",
            "provider_message_id": ""
        }
    except Exception as e:
        print(f"Twilio Request Exception: {str(e)}")
        return {
            "status": "failed",
            "provider_message_id": ""
        }
