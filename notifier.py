import os
import logging
from twilio.rest import Client

logger = logging.getLogger("uvicorn.error")

# Configure via environment variables (defaults used for testing)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "your_account_sid_here")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "your_auth_token_here")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "+1234567890")  
VWSC_TARGET_PHONE = os.getenv("VWSC_TARGET_PHONE", "+919876543210")   

def send_vwsc_alert(node_id: str, anomaly_type: str, severity: str, flow_rate: float, pressure: float, use_whatsapp: bool = False):
    """Sends an automated notification to the VWSC."""
    if "your_account_sid_here" in TWILIO_ACCOUNT_SID:
        logger.warning("Twilio credentials not set. Alert notification skipped, but database logged.")
        return False

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        message_body = (
            f"🚨 JJM WATER ALERT 🚨\n"
            f"Node ID: {node_id}\n"
            f"Status: {anomaly_type} ({severity})\n"
            f"Metrics: Flow={flow_rate} L/m, Pressure={pressure} bar\n"
            f"Action: Gram Panchayat / VWSC field team dispatched."
        )

        from_num = f"whatsapp:{TWILIO_FROM_NUMBER}" if use_whatsapp else TWILIO_FROM_NUMBER
        to_num = f"whatsapp:{VWSC_TARGET_PHONE}" if use_whatsapp else VWSC_TARGET_PHONE

        message = client.messages.create(
            body=message_body,
            from_=from_num,
            to=to_num
        )
        logger.info(f"Notification dispatched successfully to {to_num}. SID: {message.sid}")
        return True
    except Exception as exc:
        logger.error(f"Failed to dispatch Twilio alert: {exc}")
        return False