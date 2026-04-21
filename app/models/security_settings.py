from sqlmodel import SQLModel, Field
from typing import Optional, List
from datetime import datetime, UTC
from sqlalchemy import Column, JSON

class SecuritySettings(SQLModel, table=True):
    __tablename__ = "security_settings"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Section A: Password Policy
    password_min_length: int = Field(default=8)
    password_require_uppercase: bool = Field(default=True)
    password_require_number: bool = Field(default=True)
    password_require_special_char: bool = Field(default=True)
    password_expiry_days: int = Field(default=90) # 0 for Never
    password_prevent_reuse_count: int = Field(default=3)
    
    # Section B: 2FA
    enforce_2fa_super_admins: bool = Field(default=True)
    enforce_2fa_all_admins: bool = Field(default=False)
    enforce_2fa_dealers: bool = Field(default=False)
    allowed_2fa_methods: List[str] = Field(default=["TOTP"], sa_column=Column(JSON)) # TOTP, SMS, EMAIL
    two_fa_grace_period_days: int = Field(default=0)
    
    # Section C: Session Management
    admin_session_timeout_minutes: int = Field(default=30)
    max_concurrent_sessions: int = Field(default=1)
    remember_me_days: int = Field(default=7)
    
    # Section D: IP Whitelist
    ip_whitelist_enabled: bool = Field(default=False)
    # Whitelisted IPs stored as a list of dicts: [{"ip": "1.2.3.4", "label": "Office", "added_by": 1, "added_at": "..."}]
    whitelisted_ips: List[dict] = Field(default=[], sa_column=Column(JSON))
    
    # Section E: Login Controls
    max_failed_login_attempts: int = Field(default=5)
    account_lockout_duration_minutes: int = Field(default=30)
    captcha_policy: str = Field(default="AFTER_3_FAILED") # DISABLED, ALWAYS, AFTER_3_FAILED
    send_email_on_suspicious_login: bool = Field(default=True)
    notify_on_new_device_login: bool = Field(default=True)
    
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_by_id: Optional[int] = Field(default=None, foreign_key="users.id")
