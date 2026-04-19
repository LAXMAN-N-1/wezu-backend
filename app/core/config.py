from __future__ import annotations
import json
import re
from typing import Any, Literal, Optional
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlparse, urlsplit, urlunsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "WEZU Energy"
    API_V1_STR: str = "/api/v1"
    APP_VERSION: str = "2.0.3"

    # ── Database ───────────────────────────────────────────────────────────
    DATABASE_URL: str  # No default — must be provided in env
    SQLALCHEMY_ECHO: bool = False
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 60
    DB_POOL_RECYCLE: int = 1800
    DB_POOL_PRE_PING: bool = True
    DB_POOL_USE_LIFO: bool = True
    DATABASE_CONNECT_TIMEOUT_SECONDS: int = 20
    DATABASE_SSL_MODE: Optional[str] = None
    DATABASE_PREFER_IPV4: bool = False
    DATABASE_HOSTADDR: Optional[str] = None
    SQL_SLOW_QUERY_LOG_MS: int = 0
    SQL_SLOW_QUERY_WARN_COOLDOWN_SECONDS: int = 60
    SQL_SLOW_QUERY_IGNORE_PATTERNS: list[str] = ["from order_realtime_outbox"]
    STARTUP_DIAGNOSTICS_CACHE_TTL_SECONDS: float = 5.0

    # ── Redis (Sessions & Caching) ─────────────────────────────────────────
    REDIS_URL: str  # No default — must be provided in env
    REDIS_SESSION_DB: int = 1
    REDIS_CACHE_DB: int = 2
    REDIS_STREAM_MAXLEN: int = 10000
    REFERENCE_LIST_CACHE_TTL_SECONDS: int = 60
    REFERENCE_LIST_CACHE_TTL_JITTER_SECONDS: int = 5
    REFERENCE_LIST_CACHE_STALE_TTL_SECONDS: int = 180
    REFERENCE_LIST_CACHE_LOCK_WAIT_MS: int = 800
    REFERENCE_LIST_CACHE_LOCK_POLL_MS: int = 40
    ORDER_LIST_CACHE_TTL_SECONDS: int = 5
    ORDER_LIST_CACHE_LOCK_TTL_SECONDS: int = 5
    ORDER_LIST_COUNT_CACHE_TTL_SECONDS: int = 8
    ORDER_LIST_CACHE_TTL_JITTER_SECONDS: int = 2
    ORDER_LIST_CACHE_STALE_TTL_SECONDS: int = 30
    ORDER_LIST_CACHE_LOCK_WAIT_MS: int = 500
    ORDER_LIST_CACHE_LOCK_POLL_MS: int = 30
    ANALYTICS_DASHBOARD_CACHE_TTL_SECONDS: int = 8
    ANALYTICS_RECENT_ACTIVITY_CACHE_TTL_SECONDS: int = 12
    ANALYTICS_RECENT_ACTIVITY_DEFAULT_LOOKBACK_DAYS: int = 14
    ANALYTICS_RECENT_ACTIVITY_BOUNDED_PAGE_LIMIT: int = 50
    ANALYTICS_RECENT_ACTIVITY_SOURCE_MULTIPLIER: int = 12
    ANALYTICS_RECENT_ACTIVITY_MAX_SOURCE_ROWS: int = 1200
    ANALYTICS_LOW_INVENTORY_CACHE_TTL_SECONDS: int = 15
    ANALYTICS_CACHE_LOCK_TTL_SECONDS: int = 5
    ANALYTICS_CACHE_LOCK_WAIT_MS: int = 1200
    ANALYTICS_CACHE_LOCK_POLL_MS: int = 50
    ANALYTICS_CACHE_TTL_JITTER_SECONDS: int = 2
    ANALYTICS_CACHE_STALE_TTL_SECONDS: int = 90
    ANALYTICS_DASHBOARD_SNAPSHOT_REFRESH_ENABLED: bool = True
    ANALYTICS_DASHBOARD_SNAPSHOT_REFRESH_SECONDS: int = 60
    ANALYTICS_DASHBOARD_SNAPSHOT_TTL_SECONDS: int = 300
    ANALYTICS_DASHBOARD_SNAPSHOT_ACTIVE_WINDOW_SECONDS: int = 120
    ANALYTICS_DASHBOARD_SNAPSHOT_MIN_REFRESH_GAP_SECONDS: int = 180
    ANALYTICS_DASHBOARD_SNAPSHOT_MAX_TIMEZONES_PER_CYCLE: int = 1
    ANALYTICS_DASHBOARD_SNAPSHOT_TIMEZONES: str = "UTC,Asia/Kolkata"

    # ── MongoDB (Audit Logs) ──────────────────────────────────────────────
    MONGODB_URL: str = ""
    MONGODB_DB: str = "wezu_audit"

    # ── Security ───────────────────────────────────────────────────────────
    SECRET_KEY: str
    QR_SIGNING_KEY: Optional[str] = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    AUTH_PROVIDER: Literal["local", "supabase", "hybrid"] = "local"
    SUPABASE_URL: Optional[str] = None
    SUPABASE_JWKS_URL: Optional[str] = None
    SUPABASE_JWT_ISSUER: Optional[str] = None
    SUPABASE_JWT_AUDIENCE: Optional[str] = "authenticated"
    SUPABASE_ALLOWED_ALGORITHMS: list[str] = ["RS256"]
    SUPABASE_JWKS_CACHE_TTL_SECONDS: int = 300
    SUPABASE_JWKS_TIMEOUT_SECONDS: float = 5.0
    SUPABASE_ALLOW_ANON_ROLE: bool = False
    SUPABASE_ENFORCE_EMAIL_VERIFIED: bool = True
    SUPABASE_AUTO_PROVISION_USERS: bool = False
    SUPABASE_DEFAULT_ROLE_NAME: str = "customer"

    # ── Customer Authentication ────────────────────────────────────────────
    GOOGLE_OAUTH_CLIENT_ID: Optional[str] = None
    GOOGLE_OAUTH_CLIENT_SECRET: Optional[str] = None
    APPLE_CLIENT_ID: Optional[str] = None
    APPLE_TEAM_ID: Optional[str] = None
    APPLE_KEY_ID: Optional[str] = None
    APPLE_PRIVATE_KEY_PATH: Optional[str] = None

    # ── SMS/OTP Provider ───────────────────────────────────────────────────
    SMS_PROVIDER: str = "twilio"
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

    # ── Push Notifications (FCM) ──────────────────────────────────────────
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None
    FCM_SERVER_KEY: Optional[str] = None

    # ── Payment Gateway (Razorpay) ────────────────────────────────────────
    RAZORPAY_KEY_ID: Optional[str] = None
    RAZORPAY_KEY_SECRET: Optional[str] = None
    RAZORPAY_WEBHOOK_SECRET: Optional[str] = None
    RAZORPAY_MERCHANT_NAME: str = "WEZU Energy"
    RENTAL_PAYMENT_PENDING_TIMEOUT_MINUTES: int = 30

    # ── Maps & Location ───────────────────────────────────────────────────
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    MAPBOX_ACCESS_TOKEN: Optional[str] = None
    DEFAULT_MAP_PROVIDER: str = "google"

    # ── Video KYC ─────────────────────────────────────────────────────────
    VIDEO_KYC_PROVIDER: str = "agora"
    AGORA_APP_ID: Optional[str] = None
    AGORA_APP_CERTIFICATE: Optional[str] = None
    VIDEO_KYC_SESSION_TIMEOUT_MINUTES: int = 30

    # ── Fraud Verification (from Hardened) ────────────────────────────────
    PAN_API_KEY: Optional[str] = None
    PAN_API_BASE_URL: str = "https://api.panverification.io/v1"
    GST_API_KEY: Optional[str] = None
    GST_API_BASE_URL: str = "https://api.gstverify.io/v1"
    FRAUD_PROVIDER_TIMEOUT_SECONDS: int = 15
    FRAUD_COMPUTE_SERVICE_ENABLED: bool = False
    FRAUD_COMPUTE_SERVICE_URL: Optional[str] = None
    FRAUD_COMPUTE_SERVICE_API_KEY: Optional[str] = None
    FRAUD_COMPUTE_SERVICE_TIMEOUT_SECONDS: int = 2
    FRAUD_COMPUTE_FAILURE_THRESHOLD: int = 5
    FRAUD_COMPUTE_OPEN_SECONDS: int = 30

    # ── IoT/MQTT ──────────────────────────────────────────────────────────
    MQTT_ENABLED: bool = False
    MQTT_BROKER_URL: str = "mqtt://127.0.0.1:1883"
    MQTT_USERNAME: Optional[str] = None
    MQTT_PASSWORD: Optional[str] = None
    MQTT_CLIENT_ID_PREFIX: str = "wezu_backend"
    MQTT_TOPIC_PREFIX: str = "wezu/batteries"

    # ── Event Streams (from Hardened) ─────────────────────────────────────
    ENABLE_EVENT_STREAMS: bool = True
    EVENT_WORKER_CONSUMER_NAME: str = "worker"
    INTERNAL_SERVICE_TOKEN: Optional[str] = None
    TELEMATICS_STREAM_NAME: str = "wezu:stream:telematics_ingest"
    TELEMATICS_STREAM_GROUP: str = "telematics_ingest_group"
    TELEMATICS_STREAM_DLQ_NAME: str = "wezu:stream:telematics_ingest_dlq"
    TELEMATICS_STREAM_CONSUMER_BATCH_SIZE: int = 100
    TELEMATICS_STREAM_BLOCK_MS: int = 5000
    TELEMATICS_STREAM_MAX_RETRIES: int = 5
    TELEMATICS_QUEUE_ENABLED: bool = False
    TELEMATICS_DUAL_WRITE_SHADOW: bool = True
    TELEMATICS_QUEUE_REQUIRED: bool = False
    TELEMATICS_GO_WORKER_ENABLED: bool = False
    WEBHOOK_STREAM_NAME: str = "wezu:stream:webhook_events"
    WEBHOOK_STREAM_GROUP: str = "webhook_events_group"
    WEBHOOK_STREAM_DLQ_NAME: str = "wezu:stream:webhook_events_dlq"
    WEBHOOK_STREAM_CONSUMER_BATCH_SIZE: int = 100
    WEBHOOK_STREAM_BLOCK_MS: int = 5000
    WEBHOOK_STREAM_MAX_RETRIES: int = 5
    WEBHOOK_QUEUE_ENABLED: bool = False
    WEBHOOK_QUEUE_REQUIRED: bool = False
    NOTIFICATION_STREAM_NAME: str = "wezu:stream:notification_dispatch"
    NOTIFICATION_STREAM_GROUP: str = "notification_dispatch_group"
    NOTIFICATION_STREAM_DLQ_NAME: str = "wezu:stream:notification_dispatch_dlq"
    NOTIFICATION_STREAM_CONSUMER_BATCH_SIZE: int = 100
    NOTIFICATION_STREAM_BLOCK_MS: int = 5000
    NOTIFICATION_STREAM_MAX_RETRIES: int = 5
    NOTIFICATION_QUEUE_ENABLED: bool = False
    NOTIFICATION_QUEUE_REQUIRED: bool = False
    NOTIFICATION_OUTBOX_ENABLED: bool = True
    NOTIFICATION_OUTBOX_BATCH_SIZE: int = 200
    NOTIFICATION_OUTBOX_MAX_ATTEMPTS: int = 8
    NOTIFICATION_OUTBOX_MAX_RETRY_DELAY_SECONDS: int = 300
    NOTIFICATION_OUTBOX_SLO_MAX_PENDING_COUNT: int = 5000
    NOTIFICATION_OUTBOX_SLO_MAX_OLDEST_PENDING_AGE_SECONDS: int = 300
    ORDER_REALTIME_OUTBOX_ENABLED: bool = True
    ORDER_REALTIME_OUTBOX_BATCH_SIZE: int = 100
    ORDER_REALTIME_OUTBOX_POLL_INTERVAL_SECONDS: float = 1.5
    ORDER_REALTIME_OUTBOX_IDLE_BACKOFF_MAX_SECONDS: float = 10.0
    ORDER_REALTIME_OUTBOX_MAX_RETRY_DELAY_SECONDS: int = 300
    ORDER_REALTIME_OUTBOX_MAX_ATTEMPTS: int = 10
    ORDER_REALTIME_OUTBOX_USE_REDIS_DISPATCH_LOCK: bool = True
    ORDER_REALTIME_OUTBOX_DISPATCH_LOCK_TTL_SECONDS: int = 10
    ORDER_REALTIME_OUTBOX_ERROR_BACKOFF_BASE_SECONDS: float = 5.0
    ORDER_REALTIME_OUTBOX_ERROR_BACKOFF_MAX_SECONDS: float = 60.0
    ORDER_REALTIME_OUTBOX_LOCK_UNAVAILABLE_BACKOFF_SECONDS: float = 15.0

    # ── File Storage ──────────────────────────────────────────────────────
    STORAGE_PROVIDER: str = "aws_s3"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_BUCKET_NAME: Optional[str] = None
    AWS_REGION: Optional[str] = "ap-south-1"
    AWS_S3_CUSTOM_DOMAIN: Optional[str] = None
    LOCAL_STORAGE_PATH: str = "/var/www/uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    # ── Email ─────────────────────────────────────────────────────────────
    SENDGRID_API_KEY: Optional[str] = None
    SENDGRID_FROM_EMAIL: Optional[str] = None
    EMAILS_FROM_NAME: str = "WEZU Energy"
    EMAILS_ENABLED: bool = False

    # ── Customer App Settings ─────────────────────────────────────────────
    MIN_BATTERY_SOC_FOR_RENTAL: int = 20
    MAX_ACTIVE_RENTALS_PER_USER: int = 1
    RENTAL_GRACE_PERIOD_HOURS: int = 2
    LATE_FEE_MULTIPLIER: float = 1.5
    SWAP_FEE_PERCENTAGE: float = 0.0

    # ── Geofencing ────────────────────────────────────────────────────────
    GEOFENCE_CHECK_INTERVAL_MINUTES: int = 60
    GEOFENCE_ALERT_ENABLED: bool = True
    AUTOMATION_GEOFENCE_ALERT_COOLDOWN_MINUTES: int = 60

    # ── Rate Limiting ─────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    RATE_LIMIT_STORAGE_URL: Optional[str] = None

    # ── Background Jobs ───────────────────────────────────────────────────
    RUN_BACKGROUND_TASKS: bool = False
    DB_INIT_ON_STARTUP: bool = False
    SCHEDULER_ENABLED: bool = False
    RUN_SCHEDULER_IN_API: bool = True
    BACKGROUND_RUNTIME_MODE: str = "auto"
    BACKGROUND_RUNTIME_LEADER_LOCK_KEY: str = "wezu:background:runtime:leader"
    BACKGROUND_RUNTIME_LEADER_LOCK_TTL_SECONDS: int = 30
    BACKGROUND_RUNTIME_LOCK_REQUIRED: bool = True
    SCHEDULER_TIMEZONE: str = "Asia/Kolkata"
    SCHEDULER_LOCK_FILE: str = "/tmp/wezu_scheduler.lock"
    SCHEDULER_HEARTBEAT_KEY: str = "wezu:scheduler:heartbeat"
    SCHEDULER_HEARTBEAT_TTL_SECONDS: int = 30
    SCHEDULER_HEARTBEAT_INTERVAL_SECONDS: int = 10
    SCHEDULED_NOTIFICATION_DISPATCH_INTERVAL_SECONDS: int = 60
    ASYNC_WORKFLOW_NOTIFICATIONS: bool = True
    AUTOMATION_RENTAL_PAYMENT_REMINDER_LEAD_MINUTES: int = 10
    AUTOMATION_PENDING_REFUND_REMINDER_HOURS: int = 24
    AUTOMATION_PENDING_REFUND_ESCALATION_HOURS: int = 72
    AUTOMATION_PENDING_WITHDRAWAL_REMINDER_HOURS: int = 12
    AUTOMATION_PENDING_WITHDRAWAL_ESCALATION_HOURS: int = 36
    AUTOMATION_SUPPORT_SLA_HOURS: int = 4
    AUTOMATION_KYC_REMINDER_HOURS: int = 24
    AUTOMATION_KYC_ESCALATION_HOURS: int = 72
    AUDIT_REQUEST_LOGGING_ENABLED: bool = False
    AUDIT_REQUEST_QUEUE_MAXSIZE: int = 2000
    AUDIT_REQUEST_BATCH_SIZE: int = 50
    AUDIT_REQUEST_FLUSH_MS: int = 500
    AUDIT_REQUEST_DROP_WARN_EVERY: int = 100
    AUDIT_REQUEST_WORKERS: int = 1

    # ── Monitoring & Logging ──────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_ACCESS_LOGS: bool = True
    LOG_REQUESTS: bool = True
    LOG_HEALTHCHECKS: bool = False
    LOG_SLOW_REQUEST_THRESHOLD_MS: int = 2000
    LOG_SERVICE_NAME: str = "wezu-backend"
    LOG_SCHEMA_VERSION: str = "1.0"
    LOG_REDACT_SENSITIVE_FIELDS: bool = True
    LOG_MAX_FIELD_LENGTH: int = 2048
    LOG_MAX_COLLECTION_ITEMS: int = 50
    LOG_EXCLUDE_PATHS: list[str] = ["/health", "/ready", "/live"]
    LOG_ANOMALY_DETECTION_ENABLED: bool = True
    LOG_ANOMALY_MAX_UNKNOWN_FIELDS: int = 25
    LOG_ANOMALY_MAX_BODY_BYTES: int = 262144
    LOG_ANOMALY_EMPTY_SUCCESS_RESPONSE: bool = True
    DB_LOG_NOOP_MUTATIONS: bool = True
    DB_NOOP_MUTATION_IGNORE_TABLES: list[str] = ["alembic_version"]
    AUTH_TOKEN_CACHE_TTL_SECONDS: int = 5
    ANALYTICS_CACHE_TTL_SECONDS: int = 30
    DEALER_PORTAL_CACHE_TTL_SECONDS: int = 30
    USER_ADMIN_CACHE_TTL_SECONDS: int = 30
    SESSION_CACHE_TTL_SECONDS: int = 10
    SENTRY_DSN: Optional[str] = None
    SENTRY_ENVIRONMENT: str = "production"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    # ── Application ───────────────────────────────────────────────────────
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
    TRUSTED_PROXY_CIDRS: list[str] = [
        "127.0.0.1/32", "::1/128", "10.0.0.0/8",
        "172.16.0.0/12", "192.168.0.0/16", "fc00::/7",
    ]
    ENABLE_API_DOCS: bool = False
    ENFORCE_PRODUCTION_SAFETY: bool = True
    TRACKING_BASE_URL: str = "https://wezu.app/track"
    FRONTEND_BASE_URL: str = "https://app.wezu.com"
    API_PUBLIC_BASE_URL: Optional[str] = None
    MEDIA_BASE_URL: Optional[str] = None
    AUTO_CREATE_TABLES: bool = False
    AUTO_SEED_ROLES: bool = False
    ALLOW_TEST_OTP_BYPASS: bool = False
    TEST_OTP_BYPASS_TARGETS: list[str] = []
    TEST_OTP_BYPASS_CODE: str = ""
    LOGISTICS_SCHEMA_CHECK_ENABLED: bool = True
    LOGISTICS_SCHEMA_STRICT: bool = False

    # ── Feature Toggles (from Hardened) ───────────────────────────────────
    FEATURE_APPLE_SIGNIN_ENABLED: bool = True
    FEATURE_GOOGLE_SIGNIN_ENABLED: bool = True
    FEATURE_BIOMETRIC_AUTH_ENABLED: bool = True
    FEATURE_TWO_FACTOR_AUTH_ENABLED: bool = True
    PASSKEY_ENABLED: bool = True
    PASSKEY_RP_ID: Optional[str] = None
    PASSKEY_RP_NAME: str = "WEZU Logistics"
    PASSKEY_ORIGINS: list[str] = []
    PASSKEY_ANDROID_RELATIONS: list[str] = [
        "delegate_permission/common.handle_all_urls",
        "delegate_permission/common.get_login_creds",
    ]
    PASSKEY_ANDROID_PACKAGE_NAME: str = "com.example.frontend_logistic"
    PASSKEY_ANDROID_SHA256_CERT_FINGERPRINTS: list[str] = [
        "53:65:53:C8:2E:84:85:79:28:2E:84:37:C5:5D:AA:3F:1B:DE:9E:6F:53:20:A6:4F:5B:AA:D9:96:15:3B:9F:B5"
    ]
    PASSKEY_CHALLENGE_TTL_SECONDS: int = 300
    PASSKEY_MAX_CREDENTIALS_PER_USER: int = 20
    FEATURE_VIDEO_KYC_ENABLED: bool = True
    FEATURE_BATTERY_SWAP_ENABLED: bool = True
    FEATURE_ECOMMERCE_ENABLED: bool = True
    MAX_ADDRESSES_PER_USER: int = 5
    SUPPORT_HOURS: str = "24/7"

    # ── Startup Dependency Toggles (from Hardened) ────────────────────────
    ENABLE_PAYMENT_WORKFLOWS: bool = True
    ENABLE_RAZORPAY_WEBHOOKS: bool = True
    ENABLE_SMS_WORKFLOWS: bool = True
    REQUIRE_PAYMENT_AT_STARTUP: bool = False
    REQUIRE_SMS_AT_STARTUP: bool = False
    ENABLE_REDIS_SECURITY_WORKFLOWS: bool = True
    STRICT_STARTUP_DEPENDENCY_CHECKS: bool = True
    MIGRATION_GRAPH_STRICT: bool = True
    MIGRATION_GRAPH_REQUIRE_SINGLE_HEAD: bool = True
    MIGRATION_GRAPH_REQUIRE_DB_AT_HEAD: bool = True
    MIGRATION_GRAPH_VERSIONS_DIR: str = "alembic/versions"
    ALLOW_START_WITHOUT_DB: bool = False
    REQUIRE_DISTRIBUTED_2FA_RATE_LIMIT: bool = True

    # ── Customer Support ──────────────────────────────────────────────────
    SUPPORT_EMAIL: str = "support@wezu.com"
    SUPPORT_PHONE: str = "+91-0000000000"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False
    )

    # ── Validators ────────────────────────────────────────────────────────

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: Any) -> str:
        if not isinstance(value, str):
            return str(value)
        normalized = value.strip()
        if normalized.startswith("postgres://"):
            normalized = "postgresql://" + normalized[len("postgres://"):]

        split_url = urlsplit(normalized)
        if split_url.scheme.startswith("sqlite"):
            # Preserve sqlite URI slash semantics (sqlite:///path, sqlite:////abs/path).
            return normalized
        netloc = split_url.netloc

        if split_url.hostname:
            host = split_url.hostname
            if ":" in host and not host.startswith("["):
                host = f"[{host}]"
            port = f":{split_url.port}" if split_url.port else ""

            auth_prefix = ""
            if split_url.username is not None:
                username = quote(unquote(split_url.username), safe="")
                auth_prefix = username
                if split_url.password is not None:
                    password = quote(unquote(split_url.password), safe="")
                    auth_prefix = f"{auth_prefix}:{password}"
                auth_prefix = f"{auth_prefix}@"

            netloc = f"{auth_prefix}{host}{port}"

        query_pairs = parse_qsl(split_url.query, keep_blank_values=True) if split_url.query else []
        sanitized_pairs = [
            (key, raw_value)
            for key, raw_value in query_pairs
            if not (key.lower() == "options" and "search_path" in raw_value.lower())
        ]
        sanitized_query = urlencode(sanitized_pairs, doseq=True) if sanitized_pairs else ""
        return urlunsplit((
            split_url.scheme, netloc, split_url.path,
            sanitized_query, split_url.fragment,
        ))

    @field_validator("GOOGLE_MAPS_API_KEY", mode="before")
    @classmethod
    def _normalize_google_maps_api_key(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        key = str(value).strip()
        if not key:
            return None
        placeholder_values = {
            "your-google-maps-api-key", "your-google-maps-key",
            "google_maps_api_key", "changeme", "change-me",
        }
        if key.lower() in placeholder_values:
            return None
        return key

    @field_validator("AUTH_PROVIDER", mode="before")
    @classmethod
    def _normalize_auth_provider(cls, value: Any) -> str:
        if value is None:
            return "local"
        provider = str(value).strip().lower()
        return provider or "local"

    @field_validator("SUPABASE_DEFAULT_ROLE_NAME", mode="before")
    @classmethod
    def _normalize_supabase_default_role(cls, value: Any) -> str:
        if value is None:
            return "customer"
        role_name = str(value).strip().lower()
        return role_name or "customer"

    @field_validator("MEDIA_BASE_URL", "API_PUBLIC_BASE_URL", "SUPABASE_URL", "SUPABASE_JWKS_URL", mode="before")
    @classmethod
    def _normalize_base_url(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        base = str(value).strip()
        if not base:
            return None
        return base.rstrip("/")

    @field_validator(
        "CORS_ORIGINS", "ALLOWED_HOSTS", "FORWARDED_ALLOW_IPS",
        "TRUSTED_PROXY_CIDRS", "PASSKEY_ORIGINS",
        "PASSKEY_ANDROID_RELATIONS", "PASSKEY_ANDROID_SHA256_CERT_FINGERPRINTS",
        "SUPABASE_ALLOWED_ALGORITHMS", "LOG_EXCLUDE_PATHS",
        "SQL_SLOW_QUERY_IGNORE_PATTERNS",
        "DB_NOOP_MUTATION_IGNORE_TABLES",
        "TEST_OTP_BYPASS_TARGETS",
        mode="before",
    )
    @classmethod
    def _parse_list_from_env(cls, value: Any) -> list[str]:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            if value.startswith("["):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in value.split(",") if item.strip()]
        return []

    @field_validator("ALLOWED_HOSTS", mode="after")
    @classmethod
    def _normalize_allowed_hosts(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            host = str(item).strip()
            if not host:
                continue
            if host == "*":
                return ["*"]
            parsed = urlsplit(host)
            if parsed.scheme:
                host = (parsed.hostname or "").strip()
            else:
                host = host.split("/", 1)[0].strip()
                if host.count(":") == 1 and not host.startswith("["):
                    host = host.split(":", 1)[0].strip()
            host = host.strip().lower().strip(".")
            if not host:
                continue
            if host not in seen:
                seen.add(host)
                normalized.append(host)
        return normalized

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

    @field_validator("SUPABASE_ALLOWED_ALGORITHMS", mode="after")
    @classmethod
    def _normalize_supabase_algorithms(cls, value: list[str]) -> list[str]:
        normalized = [item.strip().upper() for item in value if item and item.strip()]
        if not normalized:
            return ["RS256"]
        if "NONE" in normalized:
            raise ValueError("SUPABASE_ALLOWED_ALGORITHMS cannot include 'none'")
        return normalized

    @model_validator(mode="after")
    def _validate_supabase_auth(self) -> "Settings":
        if self.AUTH_PROVIDER not in {"supabase", "hybrid"}:
            return self
        if not self.SUPABASE_URL and not self.SUPABASE_JWKS_URL:
            raise ValueError(
                "AUTH_PROVIDER is set to supabase/hybrid but SUPABASE_URL or SUPABASE_JWKS_URL is missing"
            )
        if self.SUPABASE_JWKS_TIMEOUT_SECONDS <= 0:
            raise ValueError("SUPABASE_JWKS_TIMEOUT_SECONDS must be > 0")
        if self.SUPABASE_JWKS_CACHE_TTL_SECONDS < 0:
            raise ValueError("SUPABASE_JWKS_CACHE_TTL_SECONDS must be >= 0")
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
