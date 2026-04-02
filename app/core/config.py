import json
import re
from typing import Any, Optional
from urllib.parse import urlparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "WEZU Energy"
    API_V1_STR: str = "/api/v1"
    APP_VERSION: str = "1.0.0"
    
    # Database
    DATABASE_URL: str # No default allowed, must be provided in env
    SQLALCHEMY_ECHO: bool = False
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_POOL_PRE_PING: bool = True
    DB_POOL_USE_LIFO: bool = True
    
    # Redis (Sessions & Caching)
    REDIS_URL: str # No default allowed, must be provided in env
    REDIS_SESSION_DB: int = 1
    REDIS_CACHE_DB: int = 2
    
    # MongoDB (Audit Logs & Unstructured Data)
    MONGODB_URL: str # No default allowed, must be provided in env
    MONGODB_DB: str = "wezu_audit"
    
    # Security
    SECRET_KEY: str  # Must be loaded from env
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # Customer Authentication
    GOOGLE_OAUTH_CLIENT_ID: Optional[str] = None  # Must be provided via env var
    GOOGLE_OAUTH_CLIENT_SECRET: Optional[str] = None
    APPLE_CLIENT_ID: Optional[str] = None
    APPLE_TEAM_ID: Optional[str] = None
    APPLE_KEY_ID: Optional[str] = None
    APPLE_PRIVATE_KEY_PATH: Optional[str] = None
    
    # SMS/OTP Provider (for customer login)
    SMS_PROVIDER: str = "twilio"  # twilio, msg91, aws_sns
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    TWILIO_VERIFY_SERVICE_SID: Optional[str] = None
    TWILIO_API_KEY_SID: Optional[str] = None
    TWILIO_API_SECRET: Optional[str] = None
    MSG91_AUTH_KEY: Optional[str] = None
    MSG91_SENDER_ID: Optional[str] = None
    OTP_EXPIRY_MINUTES: int = 10
    OTP_LENGTH: int = 6
    
    # Push Notifications (FCM for customer app)
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None
    FCM_SERVER_KEY: Optional[str] = None
    
    # Payment Gateway (Razorpay for customer payments)
    RAZORPAY_KEY_ID: Optional[str] = None
    RAZORPAY_KEY_SECRET: Optional[str] = None
    RAZORPAY_WEBHOOK_SECRET: Optional[str] = None
    RAZORPAY_MERCHANT_NAME: str = "WEZU Energy"
    
    # Maps & Location (for customer station search)
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    MAPBOX_ACCESS_TOKEN: Optional[str] = None
    DEFAULT_MAP_PROVIDER: str = "google"  # google, mapbox
    
    # Video KYC (for customer verification)
    VIDEO_KYC_PROVIDER: str = "agora"  # agora, twilio, zoom
    AGORA_APP_ID: Optional[str] = None
    AGORA_APP_CERTIFICATE: Optional[str] = None
    VIDEO_KYC_SESSION_TIMEOUT_MINUTES: int = 30
    
    # IoT/MQTT (for customer battery tracking)
    MQTT_ENABLED: bool = True
    MQTT_BROKER_URL: str = "mqtt://127.0.0.1:1883"
    MQTT_USERNAME: Optional[str] = None
    MQTT_PASSWORD: Optional[str] = None
    MQTT_CLIENT_ID_PREFIX: str = "wezu_backend"
    MQTT_TOPIC_PREFIX: str = "wezu/batteries"
    
    # File Storage (for customer documents, profile pics)
    STORAGE_PROVIDER: str = "aws_s3"  # aws_s3, local
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_BUCKET_NAME: Optional[str] = None
    AWS_REGION: Optional[str] = "ap-south-1"
    AWS_S3_CUSTOM_DOMAIN: Optional[str] = None
    LOCAL_STORAGE_PATH: str = "/var/www/uploads"
    MAX_UPLOAD_SIZE_MB: int = 10
    
    # Email (for customer notifications)
    SENDGRID_API_KEY: Optional[str] = None
    SENDGRID_FROM_EMAIL: Optional[str] = None
    EMAILS_FROM_NAME: str = "WEZU Energy"
    EMAILS_ENABLED: bool = False
    
    # Customer App Settings
    MIN_BATTERY_SOC_FOR_RENTAL: int = 20
    MAX_ACTIVE_RENTALS_PER_USER: int = 1
    RENTAL_GRACE_PERIOD_HOURS: int = 2
    LATE_FEE_MULTIPLIER: float = 1.5
    SWAP_FEE_PERCENTAGE: float = 0.0  # Free swaps for customers
    
    # Geofencing
    GEOFENCE_CHECK_INTERVAL_MINUTES: int = 60
    GEOFENCE_ALERT_ENABLED: bool = True
    
    # Rate Limiting (for customer API)
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # Background Jobs
    RUN_BACKGROUND_TASKS: bool = True
    DB_INIT_ON_STARTUP: bool = False
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_TIMEZONE: str = "Asia/Kolkata"
    AUDIT_REQUEST_LOGGING_ENABLED: bool = False
    
    # Monitoring & Logging
    LOG_LEVEL: str = "INFO"
    LOG_ACCESS_LOGS: bool = True
    LOG_REQUESTS: bool = True
    LOG_HEALTHCHECKS: bool = False
    LOG_SLOW_REQUEST_THRESHOLD_MS: int = 2000
    ANALYTICS_CACHE_TTL_SECONDS: int = 30
    SENTRY_DSN: Optional[str] = None
    SENTRY_ENVIRONMENT: str = "production"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1
    
    # Application
    APP_NAME: str = "Wezu Battery App"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    CORS_ALLOW_LOCALHOST: bool = True
    CORS_LOCALHOST_ORIGIN_REGEX: str = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"
    ADMIN_FRONTEND_ORIGIN: Optional[str] = "https://admin.powerfrill.com"
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1", "[::1]", "testserver"]
    ENABLE_TRUSTED_HOST_MIDDLEWARE: bool = False
    TRUST_X_FORWARDED_HOST: bool = True
    FORWARDED_ALLOW_IPS: list[str] = ["127.0.0.1/32", "::1/128", "172.16.0.0/12"]
    API_PUBLIC_BASE_URL: Optional[str] = None
    MEDIA_BASE_URL: Optional[str] = None
    
    # Customer Support
    SUPPORT_EMAIL: str = "support@wezu.com"
    SUPPORT_PHONE: str = "+91-0000000000"  # Override via env
    
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False
    )

    @field_validator("CORS_ORIGINS", "ALLOWED_HOSTS", "FORWARDED_ALLOW_IPS", mode="before")
    @classmethod
    def _parse_list_env(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        return [item.strip() for item in text.split(",") if item.strip()]

    @model_validator(mode="after")
    def _normalize_public_urls(self) -> "Settings":
        if self.ADMIN_FRONTEND_ORIGIN:
            frontend_origin = self.ADMIN_FRONTEND_ORIGIN.rstrip("/")
            if frontend_origin and frontend_origin not in self.CORS_ORIGINS:
                self.CORS_ORIGINS.append(frontend_origin)
        self.CORS_ORIGINS = [origin.rstrip("/") for origin in self.CORS_ORIGINS if origin]
        if "*" in self.CORS_ORIGINS:
            raise ValueError(
                "CORS_ORIGINS cannot contain '*' when allow_credentials=True. "
                "Provide explicit frontend origins instead."
            )

        if self.API_PUBLIC_BASE_URL:
            parsed = urlparse(self.API_PUBLIC_BASE_URL)
            if parsed.hostname:
                host = parsed.hostname.lower()
                allowed_hosts = [entry.lower() for entry in self.ALLOWED_HOSTS]
                if host not in allowed_hosts:
                    self.ALLOWED_HOSTS.append(host)

        if not self.MEDIA_BASE_URL and self.API_PUBLIC_BASE_URL:
            self.MEDIA_BASE_URL = f"{self.API_PUBLIC_BASE_URL.rstrip('/')}/uploads"

        return self

    def is_origin_allowed(self, origin: str) -> bool:
        if not origin:
            return False
        normalized_origin = origin.rstrip("/")
        if not normalized_origin:
            return False
        if "*" in self.CORS_ORIGINS or normalized_origin in self.CORS_ORIGINS:
            return True
        if self.CORS_ALLOW_LOCALHOST:
            try:
                return re.match(self.CORS_LOCALHOST_ORIGIN_REGEX, normalized_origin) is not None
            except re.error:
                return False
        return False

    @property
    def cors_allow_origin_regex(self) -> Optional[str]:
        return self.CORS_LOCALHOST_ORIGIN_REGEX if self.CORS_ALLOW_LOCALHOST else None

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "Settings":
        """Fail fast if critical secrets are placeholder values."""
        _PLACEHOLDER_MARKERS = ["your-", "change-this", "CHANGEME", "xxxx", "placeholder"]

        if any(marker in self.SECRET_KEY.lower() for marker in _PLACEHOLDER_MARKERS):
            import warnings
            msg = (
                "SECRET_KEY contains a placeholder value! "
                "Generate a proper key: python -c 'import secrets; print(secrets.token_urlsafe(64))'"
            )
            if self.ENVIRONMENT == "production":
                raise ValueError(msg)
            warnings.warn(msg, stacklevel=2)

        return self

settings = Settings()
