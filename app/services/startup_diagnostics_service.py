from __future__ import annotations

import copy
from datetime import datetime
from threading import Lock
from typing import Any
from urllib import request

from sqlalchemy import text
from sqlmodel import Session

from app.core.config import settings
from app.db.migration_graph_guard import validate_migration_graph
from app.core.database import engine
from app.services.background_runtime_service import BackgroundRuntimeService
from app.services.notification_outbox_service import NotificationOutboxService
from app.services.redis_service import RedisService
from app.workers import get_scheduler_runtime_state, get_stream_worker_state


class StartupDiagnosticsService:
    """Collect and enforce runtime dependency readiness for production safety."""
    _cache_lock = Lock()
    _refresh_lock = Lock()
    _cached_report: dict[str, Any] | None = None
    _cached_generated_at: datetime | None = None

    @staticmethod
    def _build_report() -> dict[str, Any]:
        components = {
            "database": StartupDiagnosticsService._database_component(),
            "migration_graph": StartupDiagnosticsService._migration_graph_component(),
            "redis": StartupDiagnosticsService._redis_component(),
            "payment_gateway": StartupDiagnosticsService._payment_component(),
            "sms": StartupDiagnosticsService._sms_component(),
            "email": StartupDiagnosticsService._email_component(),
            "fraud_compute": StartupDiagnosticsService._fraud_compute_component(),
            "scheduler": StartupDiagnosticsService._scheduler_component(),
            "event_streams": StartupDiagnosticsService._event_stream_component(),
            "notification_delivery": StartupDiagnosticsService._notification_delivery_component(),
            "background_runtime": StartupDiagnosticsService._background_runtime_component(),
        }
        required_failures = [
            name
            for name, state in components.items()
            if state.get("required") and state.get("status") not in {"ready", "disabled"}
        ]
        overall_status = "ready" if not required_failures else "degraded"
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "environment": settings.ENVIRONMENT,
            "overall_status": overall_status,
            "required_failures": required_failures,
            "components": components,
        }

    @staticmethod
    def _database_component() -> dict[str, Any]:
        database_required = not bool(getattr(settings, "ALLOW_START_WITHOUT_DB", False))
        try:
            with Session(engine) as session:
                session.exec(text("SELECT 1"))
            return {
                "status": "ready",
                "required": database_required,
                "details": "Database connection is healthy",
            }
        except Exception as exc:
            return {
                "status": "unavailable",
                "required": database_required,
                "details": f"Database check failed: {exc}",
            }

    @staticmethod
    def _migration_graph_component() -> dict[str, Any]:
        required = bool(getattr(settings, "MIGRATION_GRAPH_STRICT", True))
        report = validate_migration_graph(
            require_single_head=bool(getattr(settings, "MIGRATION_GRAPH_REQUIRE_SINGLE_HEAD", True)),
            require_db_at_head=bool(getattr(settings, "MIGRATION_GRAPH_REQUIRE_DB_AT_HEAD", True)),
        )
        if report.valid:
            return {
                "status": "ready",
                "required": required,
                "details": {
                    "heads": list(report.heads),
                    "revision_count": report.revision_count,
                    "current_db_revisions": list(report.current_db_revisions),
                },
            }
        return {
            "status": "invalid",
            "required": required,
            "details": {
                "issues": list(report.issues),
                "heads": list(report.heads),
                "revision_count": report.revision_count,
                "current_db_revisions": list(report.current_db_revisions),
            },
        }

    @staticmethod
    def _redis_component() -> dict[str, Any]:
        required = bool(getattr(settings, "ENABLE_REDIS_SECURITY_WORKFLOWS", True))
        if not required:
            return {
                "status": "disabled",
                "required": False,
                "details": "Redis-dependent security workflows disabled",
            }

        client = RedisService.get_client()
        if client is None:
            return {
                "status": "unavailable",
                "required": True,
                "details": "Redis client is unavailable",
            }

        try:
            client.ping()
            return {
                "status": "ready",
                "required": True,
                "details": "Redis ping successful",
            }
        except Exception as exc:
            return {
                "status": "unavailable",
                "required": True,
                "details": f"Redis ping failed: {exc}",
            }

    @staticmethod
    def _payment_component() -> dict[str, Any]:
        workflows_enabled = bool(getattr(settings, "ENABLE_PAYMENT_WORKFLOWS", True))
        required = workflows_enabled and bool(getattr(settings, "REQUIRE_PAYMENT_AT_STARTUP", False))
        if not workflows_enabled:
            return {
                "status": "disabled",
                "required": False,
                "details": "Payment workflows disabled",
            }

        missing: list[str] = []
        if not settings.RAZORPAY_KEY_ID:
            missing.append("RAZORPAY_KEY_ID")
        if not settings.RAZORPAY_KEY_SECRET:
            missing.append("RAZORPAY_KEY_SECRET")
        if getattr(settings, "ENABLE_RAZORPAY_WEBHOOKS", True) and not settings.RAZORPAY_WEBHOOK_SECRET:
            missing.append("RAZORPAY_WEBHOOK_SECRET")

        if missing:
            return {
                "status": "unconfigured",
                "required": required,
                "details": f"Missing payment settings: {', '.join(missing)}",
            }

        return {
            "status": "ready",
            "required": required,
            "details": "Razorpay credentials configured",
        }

    @staticmethod
    def _sms_component() -> dict[str, Any]:
        workflows_enabled = bool(getattr(settings, "ENABLE_SMS_WORKFLOWS", True))
        required = workflows_enabled and bool(getattr(settings, "REQUIRE_SMS_AT_STARTUP", False))
        if not workflows_enabled:
            return {
                "status": "disabled",
                "required": False,
                "details": "SMS workflows disabled",
            }

        provider = (settings.SMS_PROVIDER or "").strip().lower()
        missing: list[str] = []
        if provider == "twilio":
            if not settings.TWILIO_ACCOUNT_SID:
                missing.append("TWILIO_ACCOUNT_SID")
            if not settings.TWILIO_AUTH_TOKEN:
                missing.append("TWILIO_AUTH_TOKEN")
            if not settings.TWILIO_PHONE_NUMBER:
                missing.append("TWILIO_PHONE_NUMBER")
        elif provider == "msg91":
            if not settings.MSG91_AUTH_KEY:
                missing.append("MSG91_AUTH_KEY")
            if not settings.MSG91_SENDER_ID:
                missing.append("MSG91_SENDER_ID")

        if missing:
            return {
                "status": "unconfigured",
                "required": required,
                "details": f"Missing SMS settings for provider '{provider}': {', '.join(missing)}",
            }

        return {
            "status": "ready",
            "required": required,
            "details": f"SMS provider '{provider or 'unknown'}' configured",
        }

    @staticmethod
    def _scheduler_component() -> dict[str, Any]:
        state = get_scheduler_runtime_state()
        if not state.get("enabled"):
            return {
                "status": "disabled",
                "required": False,
                "details": "Scheduler disabled",
            }
        if state.get("running"):
            heartbeat = state.get("heartbeat") or {}
            deployment_mode = state.get("deployment_mode")
            return {
                "status": "ready",
                "required": False,
                "details": (
                    f"Scheduler active ({deployment_mode}) with {state.get('job_count', 0)} local jobs; "
                    f"next_run={state.get('next_run_time')} "
                    f"heartbeat_status={heartbeat.get('status')}"
                ),
            }
        heartbeat = state.get("heartbeat") or {}
        return {
            "status": "inactive",
            "required": False,
            "details": (
                f"Scheduler enabled but not active; deployment_mode={state.get('deployment_mode')} "
                f"heartbeat_status={heartbeat.get('status')}"
            ),
        }

    @staticmethod
    def _event_stream_component() -> dict[str, Any]:
        required = (
            bool(getattr(settings, "TELEMATICS_QUEUE_REQUIRED", False))
            or bool(getattr(settings, "WEBHOOK_QUEUE_REQUIRED", False))
            or bool(getattr(settings, "NOTIFICATION_QUEUE_REQUIRED", False))
        )
        if not getattr(settings, "ENABLE_EVENT_STREAMS", True):
            return {
                "status": "disabled",
                "required": required,
                "details": "Event streams disabled",
            }

        client = RedisService.get_client()
        if client is None:
            return {
                "status": "unavailable",
                "required": required,
                "details": "Redis unavailable for event streams",
            }
        try:
            client.ping()
        except Exception as exc:
            return {
                "status": "unavailable",
                "required": required,
                "details": f"Redis ping failed for event streams: {exc}",
            }

        stream_state = get_stream_worker_state()
        return {
            "status": "ready",
            "required": required,
            "details": stream_state,
        }

    @staticmethod
    def _notification_delivery_component() -> dict[str, Any]:
        if not bool(getattr(settings, "NOTIFICATION_OUTBOX_ENABLED", True)):
            return {
                "status": "disabled",
                "required": False,
                "details": "Notification outbox disabled",
            }

        snapshot = NotificationOutboxService.get_health_snapshot()
        if snapshot.get("status") != "ready":
            return {
                "status": "unavailable",
                "required": False,
                "details": snapshot.get("details", "Notification outbox health unavailable"),
            }

        pending_count = int(snapshot.get("pending_count", 0))
        dead_letter_count = int(snapshot.get("dead_letter_count", 0))
        oldest_age_seconds = snapshot.get("oldest_pending_age_seconds")
        max_pending = int(snapshot.get("slo_max_pending_count", 5000))
        max_oldest = int(snapshot.get("slo_max_oldest_pending_age_seconds", 300))

        over_pending = pending_count > max_pending
        over_oldest = (oldest_age_seconds or 0) > max_oldest if oldest_age_seconds is not None else False
        has_dead_letters = dead_letter_count > 0

        status = "degraded" if (over_pending or over_oldest or has_dead_letters) else "ready"
        return {
            "status": status,
            "required": False,
            "details": {
                "pending_count": pending_count,
                "dead_letter_count": dead_letter_count,
                "oldest_pending_age_seconds": oldest_age_seconds,
                "slo": {
                    "max_pending_count": max_pending,
                    "max_oldest_pending_age_seconds": max_oldest,
                },
            },
        }

    @staticmethod
    def _background_runtime_component() -> dict[str, Any]:
        state = BackgroundRuntimeService.state()
        mode = state.get("mode") or "auto"
        status = "ready" if state.get("reason") not in {"not_initialized"} else "inactive"
        return {
            "status": status,
            "required": False,
            "details": {
                "mode": mode,
                "run_scheduler": bool(state.get("run_scheduler")),
                "run_outbox_dispatch": bool(state.get("run_outbox_dispatch")),
                "leader_acquired": bool(state.get("leader_acquired")),
                "lock_backend_available": bool(state.get("lock_backend_available")),
                "dedicated_scheduler_alive": bool(state.get("dedicated_scheduler_alive")),
                "reason": state.get("reason"),
            },
        }

    @staticmethod
    def _email_component() -> dict[str, Any]:
        enabled = bool(getattr(settings, "EMAILS_ENABLED", False))
        if not enabled:
            return {
                "status": "disabled",
                "required": False,
                "details": "Email workflows disabled",
            }

        missing: list[str] = []
        if not settings.SENDGRID_API_KEY:
            missing.append("SENDGRID_API_KEY")
        if not settings.SENDGRID_FROM_EMAIL:
            missing.append("SENDGRID_FROM_EMAIL")
        if missing:
            return {
                "status": "unconfigured",
                "required": False,
                "details": f"Missing email settings: {', '.join(missing)}",
            }

        return {
            "status": "ready",
            "required": False,
            "details": "Email provider configured",
        }

    @staticmethod
    def _fraud_compute_component() -> dict[str, Any]:
        enabled = bool(getattr(settings, "FRAUD_COMPUTE_SERVICE_ENABLED", False))
        if not enabled:
            return {
                "status": "disabled",
                "required": False,
                "details": "External fraud compute service is disabled",
            }

        base_url = (getattr(settings, "FRAUD_COMPUTE_SERVICE_URL", None) or "").strip()
        if not base_url:
            return {
                "status": "unconfigured",
                "required": False,
                "details": "FRAUD_COMPUTE_SERVICE_URL is not configured",
            }

        url = f"{base_url.rstrip('/')}/health"
        req = request.Request(url=url, method="GET")
        api_key = (getattr(settings, "FRAUD_COMPUTE_SERVICE_API_KEY", None) or "").strip()
        if api_key:
            req.add_header("X-Compute-Api-Key", api_key)
        try:
            timeout_seconds = max(1, int(getattr(settings, "FRAUD_COMPUTE_SERVICE_TIMEOUT_SECONDS", 2)))
            with request.urlopen(req, timeout=timeout_seconds) as resp:
                if int(resp.status) == 200:
                    return {
                        "status": "ready",
                        "required": False,
                        "details": f"Fraud compute health endpoint reachable ({url})",
                    }
                return {
                    "status": "degraded",
                    "required": False,
                    "details": f"Fraud compute health endpoint returned status={resp.status}",
                }
        except Exception as exc:
            return {
                "status": "degraded",
                "required": False,
                "details": f"Fraud compute health check failed: {exc}",
            }

    @staticmethod
    def collect_report() -> dict[str, Any]:
        ttl_seconds = max(0.0, float(getattr(settings, "STARTUP_DIAGNOSTICS_CACHE_TTL_SECONDS", 5.0)))
        stale_report: dict[str, Any] | None = None
        if ttl_seconds > 0:
            with StartupDiagnosticsService._cache_lock:
                if (
                    StartupDiagnosticsService._cached_report is not None
                    and StartupDiagnosticsService._cached_generated_at is not None
                ):
                    age_seconds = (
                        datetime.utcnow() - StartupDiagnosticsService._cached_generated_at
                    ).total_seconds()
                    if age_seconds <= ttl_seconds:
                        return copy.deepcopy(StartupDiagnosticsService._cached_report)
                    stale_report = copy.deepcopy(StartupDiagnosticsService._cached_report)

            # stale-while-refresh: avoid stampeding dependency checks under concurrent /ready requests
            if stale_report is not None:
                acquired_refresh = StartupDiagnosticsService._refresh_lock.acquire(blocking=False)
                if not acquired_refresh:
                    return stale_report
            else:
                StartupDiagnosticsService._refresh_lock.acquire()
            try:
                with StartupDiagnosticsService._cache_lock:
                    if (
                        StartupDiagnosticsService._cached_report is not None
                        and StartupDiagnosticsService._cached_generated_at is not None
                    ):
                        age_seconds = (
                            datetime.utcnow() - StartupDiagnosticsService._cached_generated_at
                        ).total_seconds()
                        if age_seconds <= ttl_seconds:
                            return copy.deepcopy(StartupDiagnosticsService._cached_report)

                report = StartupDiagnosticsService._build_report()
                with StartupDiagnosticsService._cache_lock:
                    StartupDiagnosticsService._cached_report = copy.deepcopy(report)
                    StartupDiagnosticsService._cached_generated_at = datetime.utcnow()
                return report
            finally:
                StartupDiagnosticsService._refresh_lock.release()

        return StartupDiagnosticsService._build_report()

    @staticmethod
    def enforce_required_dependencies() -> None:
        if not getattr(settings, "STRICT_STARTUP_DEPENDENCY_CHECKS", True):
            return
        if (settings.ENVIRONMENT or "").strip().lower() != "production":
            return

        report = StartupDiagnosticsService.collect_report()
        failures = report.get("required_failures") or []
        if bool(getattr(settings, "ALLOW_START_WITHOUT_DB", False)):
            failures = [name for name in failures if name != "database"]
        if failures:
            raise RuntimeError(
                "Startup dependency validation failed for required components: "
                + ", ".join(failures)
            )
