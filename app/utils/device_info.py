from typing import Dict, Any
import re

def parse_user_agent(ua_string: str) -> Dict[str, Any]:
    """
    Very basic user agent parser to extract OS, Browser, and Device Type.
    In a real production app, use a dedicated library like 'user-agents' or 'ua-parser'.
    """
    if not ua_string:
        return {"os": "Unknown", "browser": "Unknown", "device_type": "Unknown"}

    ua_string = ua_string.lower()
    
    # 1. Device Type
    device_type = "Desktop"
    if any(m in ua_string for m in ["mobi", "android", "iphone", "ipod"]):
        device_type = "Mobile"
    elif "tablet" in ua_string or "ipad" in ua_string:
        device_type = "Tablet"

    # 2. OS
    os = "Unknown"
    if "windows" in ua_string:
        os = "Windows"
    elif "android" in ua_string:
        os = "Android"
    elif "iphone" in ua_string or "ipad" in ua_string:
        os = "iOS"
    elif "macintosh" in ua_string or "mac os x" in ua_string:
        os = "macOS"
    elif "linux" in ua_string:
        os = "Linux"

    # 3. Browser
    browser = "Other"
    if "edg/" in ua_string:
        browser = "Edge"
    elif "chrome/" in ua_string and "safari/" in ua_string:
        browser = "Chrome"
    elif "safari/" in ua_string and "chrome/" not in ua_string:
        browser = "Safari"
    elif "firefox/" in ua_string:
        browser = "Firefox"
    elif "trident/" in ua_string or "msie " in ua_string:
        browser = "IE"

    return {
        "os": os,
        "browser": browser,
        "device_type": device_type,
        "raw": ua_string
    }
