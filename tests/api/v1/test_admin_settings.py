from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.api import deps
from app.models.system import SystemConfig
from app.models.user import User
from app.utils.runtime_cache import invalidate_cache


def _set_admin_override(client: TestClient, session: Session) -> None:
    admin_user = session.exec(select(User).where(User.email == "admin@test.com")).first()
    assert admin_user is not None
    client.app.dependency_overrides[deps.get_current_active_admin] = lambda: admin_user


def _upsert_config(session: Session, *, key: str, value: str, description: str | None = None) -> None:
    config = session.exec(select(SystemConfig).where(SystemConfig.key == key)).first()
    if config is None:
        config = SystemConfig(key=key, value=value, description=description)
        session.add(config)
    else:
        config.value = value
        config.description = description
        session.add(config)
    session.commit()


def test_get_general_settings_with_key_uses_key_filter(
    client: TestClient, session: Session, monkeypatch
):
    invalidate_cache("admin_settings")
    _set_admin_override(client, session)
    _upsert_config(session, key="ui_theme", value="dark", description="Theme")
    _upsert_config(session, key="max_login_attempts", value="5", description="Security")

    statements: list[str] = []
    original_exec = session.exec

    def _tracking_exec(statement, *args, **kwargs):
        sql = str(statement)
        if "system_configs" in sql:
            statements.append(sql)
        return original_exec(statement, *args, **kwargs)

    monkeypatch.setattr(session, "exec", _tracking_exec)

    response = client.get("/api/v1/admin/settings/general", params={"key": "ui_theme"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ui_theme"]["value"] == "dark"
    assert any(
        "WHERE system_configs.key" in statement
        for statement in statements
    )


def test_get_general_settings_with_key_is_cached(client: TestClient, session: Session, monkeypatch):
    invalidate_cache("admin_settings")
    _set_admin_override(client, session)
    _upsert_config(session, key="support_email", value="ops@wezu.com", description="Support")

    query_count = 0
    original_exec = session.exec

    def _tracking_exec(statement, *args, **kwargs):
        nonlocal query_count
        if "system_configs" in str(statement):
            query_count += 1
        return original_exec(statement, *args, **kwargs)

    monkeypatch.setattr(session, "exec", _tracking_exec)

    first = client.get("/api/v1/admin/settings/general", params={"key": "support_email"})
    second = client.get("/api/v1/admin/settings/general", params={"key": "support_email"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert query_count == 1


def test_get_general_settings_without_key_returns_all(client: TestClient, session: Session):
    invalidate_cache("admin_settings")
    _set_admin_override(client, session)
    _upsert_config(session, key="timezone", value="Asia/Kolkata", description="Default TZ")
    _upsert_config(session, key="currency", value="INR", description="Currency")

    response = client.get("/api/v1/admin/settings/general")

    assert response.status_code == 200
    payload = response.json()
    assert "timezone" in payload
    assert "currency" in payload
