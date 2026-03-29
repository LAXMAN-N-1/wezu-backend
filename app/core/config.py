from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "WEZU Energy"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/wezy_db"
    SQLALCHEMY_ECHO: bool = False
    DB_POOL_SIZE: int = 3
    DB_MAX_OVERFLOW: int = 3
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_POOL_PRE_PING: bool = True
    
    # Redis (Sessions & Caching)
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    REDIS_SESSION_DB: int = 1
    REDIS_CACHE_DB: int = 2
    
    # MongoDB (Audit Logs & Unstructured Data)
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "wezu_audit"
    
    # Security
    SECRET_KEY: str  # Must be loaded from env
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # Customer Authentication
    GOOGLE_OAUTH_CLIENT_ID: str = "14021620854-19a577mtevqnvelpijimv1n856f2llbq.apps.googleusercontent.com"
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
    DB_INIT_ON_STARTUP: bool = True
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_TIMEZONE: str = "Asia/Kolkata"
    
    # Monitoring & Logging
    LOG_LEVEL: str = "INFO"
    SENTRY_DSN: Optional[str] = None
    SENTRY_ENVIRONMENT: str = "production"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1
    
    # Application
    APP_NAME: str = "Wezu Battery App"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    
    # Customer Support
    SUPPORT_EMAIL: str = "support@wezu.com"
    SUPPORT_PHONE: str = "+91-1234567890"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False
    )

settings = Settings()
