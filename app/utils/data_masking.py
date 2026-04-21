import re
from typing import Dict, Any, Union, Optional

# Keys to scrub entirely or partially stringify
SENSITIVE_KEYS = {
    "password", "hashed_password", "token", "access_token", 
    "refresh_token", "secret", "cvv", "credit_card", "pin", "otp",
    "authorization"
}

# Regex to detect JWTs in string fields like 'Authorization' header
JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*")


def mask_sensitive_value(key: str, value: Any) -> Any:
    key_lower = str(key).lower()
    
    if any(sensitive_key in key_lower for sensitive_key in SENSITIVE_KEYS):
        return "***MASKED***"
    
    if isinstance(value, str):
        # Mask any JWT-like strings in headers or values
        if JWT_PATTERN.search(value):
            return JWT_PATTERN.sub("***JWT_MASKED***", value)
        
        # Simple masking for emails (leave domain)
        if "email" in key_lower and "@" in value:
            parts = value.split("@")
            if len(parts[0]) > 2:
                masked_name = parts[0][:2] + "***" + parts[0][-1]
            else:
                masked_name = "***"
            return f"{masked_name}@{parts[1]}"
            
        # Mask phone numbers
        if "phone" in key_lower and len(value) > 4:
            return f"***-***-{value[-4:]}"
            
        # Mask bank accounts partially
        if "account" in key_lower and len(value) > 4:
            return f"***{value[-4:]}"
            
    return value

def mask_dict(data: Optional[Union[Dict[str, Any], list]]) -> Any:
    """Recursively parses a dictionary or list, applying masking rules to sensitive fields."""
    if not data:
        return data
        
    if isinstance(data, list):
        return [mask_dict(item) for item in data]
        
    if isinstance(data, dict):
        masked_data = {}
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                masked_data[k] = mask_dict(v)
            else:
                masked_data[k] = mask_sensitive_value(k, v)
        return masked_data
        
    return data
