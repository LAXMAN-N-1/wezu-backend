from __future__ import annotations
from datetime import datetime, timedelta
import random
import string
from typing import Any

def generate_random_string(length: int = 10) -> str:
    """Generate a random string of fixed length"""
    letters = string.ascii_lowercase + string.digits
    return ''.join(random.choice(letters) for i in range(length))

def generate_otp(length: int = 6) -> str:
    """Generate a numeric OTP"""
    digits = string.digits
    return ''.join(random.choice(digits) for i in range(length))

def format_currency(amount: float, currency: str = "INR") -> str:
    return f"{currency} {amount:.2f}"

def mask_email(email: str) -> str:
    if not email or '@' not in email:
        return email
    user, domain = email.split('@')
    masked_user = user[0] + "*" * (len(user) - 2) + user[-1] if len(user) > 2 else user
    return f"{masked_user}@{domain}"
