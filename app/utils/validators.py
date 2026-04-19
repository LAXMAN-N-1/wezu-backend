from __future__ import annotations
import re
from typing import Optional

def validate_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))

def validate_phone(phone: str) -> bool:
    # Basic validation for Indian phone numbers (can be expanded)
    pattern = r"^[6-9]\d{9}$" 
    return bool(re.match(pattern, phone))

def validate_password_strength(password: str) -> bool:
    """
    Min 8 chars, at least one uppercase, one lowercase, one number, one special char
    """
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False
    return True
