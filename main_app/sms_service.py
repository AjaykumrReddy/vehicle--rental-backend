import os
from twilio.rest import Client
from .logging_config import get_logger, log_error

logger = get_logger(__name__)

class SMSService:
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = os.getenv("TWILIO_PHONE_NUMBER")
        
        if not all([self.account_sid, self.auth_token, self.from_number]):
            logger.warning("Twilio credentials not configured, SMS will be printed to console")
            self.client = None
        else:
            self.client = Client(self.account_sid, self.auth_token)
    
    def send_otp(self, phone_number: str, otp_code: str) -> bool:
        """Send OTP via SMS"""
        message = f"Your RediRental verification code is: {otp_code}. Valid for 5 minutes."
        
        try:
            if self.client:
                # Send actual SMS
                message_obj = self.client.messages.create(
                    body=message,
                    from_=self.from_number,
                    to=phone_number
                )
                logger.info(f"SMS sent successfully", extra={
                    "phone_number": phone_number,
                    "message_sid": message_obj.sid
                })
                return True
            else:
                # Development mode - print to console
                print(f"SMS to {phone_number}: {message}")
                logger.info(f"SMS printed to console (dev mode)", extra={"phone_number": phone_number})
                return True
                
        except Exception as e:
            log_error(logger, e, {"phone_number": phone_number}, "sms_send_error")
            return False

# Global SMS service instance
sms_service = SMSService()