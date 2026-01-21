from app.core.config import settings
import requests

class SMSService:
    @staticmethod
    def send_sms(phone: str, message: str):
        # Implementation for MSG91 or Twilio
        # MOCK for now
        print(f"MOCK SMS to {phone}: {message}")
        return True

    @staticmethod
    def send_otp(phone: str, otp: str):
        message = f"Your Wezu verification code is {otp}. Do not share this with anyone."
        return SMSService.send_sms(phone, message)
