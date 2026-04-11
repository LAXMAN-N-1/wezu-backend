"""
Unit Tests for app/core/audit.py
Tests AuditLogger.log_event, cleanup_old_logs, and _log_from_context
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

# Patch JSONB for SQLite before importing models
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

def visit_JSONB(self, type_, **kw):
    return "JSON"

SQLiteTypeCompiler.visit_JSONB = visit_JSONB

from app.models.audit_log import AuditLog
from app.core.audit import AuditLogger, cleanup_old_logs, _log_from_context


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture(name="db")
def db_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


# ── AuditLogger.log_event ───────────────────────────────────────────

class TestAuditLoggerLogEvent:
    def test_creates_record_with_all_fields(self, db):
        entry = AuditLogger.log_event(
            db=db,
            user_id=42,
            action="LOGIN",
            resource_type="AUTH",
            resource_id="42",
            metadata={"role": "admin"},
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )
        assert entry is not None
        assert entry.id is not None
        assert entry.user_id == 42
        assert entry.action == "LOGIN"
        assert entry.resource_type == "AUTH"
        assert entry.resource_id == "42"
        assert entry.meta_data == {"role": "admin"}
        assert entry.ip_address == "192.168.1.1"
        assert entry.user_agent == "Mozilla/5.0"
        assert entry.timestamp is not None

    def test_creates_record_with_none_user_id(self, db):
        """System actions should work with user_id=None."""
        entry = AuditLogger.log_event(
            db=db, user_id=None, action="SYSTEM_CHECK", resource_type="SYSTEM"
        )
        assert entry is not None
        assert entry.user_id is None
        assert entry.action == "SYSTEM_CHECK"

    def test_creates_record_with_minimal_params(self, db):
        entry = AuditLogger.log_event(
            db=db, user_id=1, action="TEST", resource_type="TEST"
        )
        assert entry is not None
        assert entry.resource_id is None
        assert entry.meta_data is None
        assert entry.ip_address is None
        assert entry.user_agent is None

    def test_resource_id_converted_to_string(self, db):
        entry = AuditLogger.log_event(
            db=db, user_id=1, action="TEST", resource_type="TEST", resource_id=123
        )
        assert entry.resource_id == "123"

    def test_persisted_to_database(self, db):
        AuditLogger.log_event(db=db, user_id=5, action="CREATE", resource_type="USER")
        logs = db.exec(select(AuditLog).where(AuditLog.user_id == 5)).all()
        assert len(logs) == 1
        assert logs[0].action == "CREATE"

    def test_never_raises_on_error(self):
        """log_event should return None on error, never raise."""
        broken_db = MagicMock(spec=Session)
        broken_db.add.side_effect = Exception("DB is broken")
        result = AuditLogger.log_event(
            db=broken_db, user_id=1, action="FAIL", resource_type="TEST"
        )
        assert result is None
        broken_db.rollback.assert_called_once()

    def test_multiple_events(self, db):
        AuditLogger.log_event(db=db, user_id=1, action="A", resource_type="T")
        AuditLogger.log_event(db=db, user_id=2, action="B", resource_type="T")
        AuditLogger.log_event(db=db, user_id=3, action="C", resource_type="T")
        logs = db.exec(select(AuditLog)).all()
        assert len(logs) == 3


# ── cleanup_old_logs ────────────────────────────────────────────────

class TestCleanupOldLogs:
    def _seed_logs(self, db, days_ago_list):
        """Create AuditLog entries at specific ages."""
        for days in days_ago_list:
            log = AuditLog(
                user_id=1,
                action="TEST",
                resource_type="TEST",
                timestamp=datetime.utcnow() - timedelta(days=days),
            )
            db.add(log)
        db.commit()

    def test_deletes_old_records(self, db):
        self._seed_logs(db, [100, 200, 10, 5])  # 2 old, 2 recent
        deleted = cleanup_old_logs(db, retention_days=90)
        assert deleted == 2
        remaining = db.exec(select(AuditLog)).all()
        assert len(remaining) == 2

    def test_keeps_recent_records(self, db):
        self._seed_logs(db, [10, 20, 30])
        deleted = cleanup_old_logs(db, retention_days=90)
        assert deleted == 0
        remaining = db.exec(select(AuditLog)).all()
        assert len(remaining) == 3

    def test_empty_table(self, db):
        deleted = cleanup_old_logs(db, retention_days=90)
        assert deleted == 0

    def test_custom_retention_days(self, db):
        self._seed_logs(db, [5, 10, 15, 20])
        deleted = cleanup_old_logs(db, retention_days=12)
        assert deleted == 2


# ── _log_from_context ───────────────────────────────────────────────

class TestLogFromContext:
    def test_extracts_db_param(self, db):
        mock_request = MagicMock()
        mock_request.client.host = "1.2.3.4"
        mock_request.headers.get.return_value = "TestAgent"

        mock_user = MagicMock()
        mock_user.id = 99

        _log_from_context(
            kwargs={"db": db, "request": mock_request, "current_user": mock_user},
            action="TEST_ACTION",
            resource_type="TEST_RES",
        )

        logs = db.exec(select(AuditLog)).all()
        assert len(logs) == 1
        assert logs[0].action == "TEST_ACTION"
        assert logs[0].user_id == 99
        assert logs[0].ip_address == "1.2.3.4"

    def test_extracts_session_param(self, db):
        """Falls back to 'session' kwarg when 'db' is not present."""
        mock_user = MagicMock()
        mock_user.id = 10

        _log_from_context(
            kwargs={"session": db, "current_user": mock_user},
            action="SESSION_TEST",
            resource_type="TEST",
        )

        logs = db.exec(select(AuditLog)).all()
        assert len(logs) == 1
        assert logs[0].action == "SESSION_TEST"

    def test_skips_when_no_db(self):
        """Should not crash when no db/session in kwargs."""
        _log_from_context(
            kwargs={"current_user": MagicMock()},
            action="NO_DB",
            resource_type="TEST",
        )
        # No exception = pass

    def test_extracts_resource_id_param(self, db):
        mock_user = MagicMock()
        mock_user.id = 1

        _log_from_context(
            kwargs={"db": db, "current_user": mock_user, "battery_id": 42},
            action="UPDATE",
            resource_type="BATTERY",
            resource_id_param="battery_id",
        )

        logs = db.exec(select(AuditLog)).all()
        assert len(logs) == 1
        assert logs[0].resource_id == "42"

    def test_no_current_user(self, db):
        """Should handle missing current_user (user_id=None)."""
        _log_from_context(
            kwargs={"db": db},
            action="ANON",
            resource_type="TEST",
        )

        logs = db.exec(select(AuditLog)).all()
        assert len(logs) == 1
        assert logs[0].user_id is None

    def test_never_raises(self):
        """Should never raise, even with bad kwargs."""
        _log_from_context(kwargs={}, action="BAD", resource_type="BAD")
        # No exception = pass
