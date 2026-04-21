from __future__ import annotations

from pathlib import Path

from app.db import migration_graph_guard as guard


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_validate_migration_graph_parses_typed_assignments(tmp_path: Path) -> None:
    _write(
        tmp_path / "001_base.py",
        """
revision: str = "base_rev"
down_revision: str | None = None
""".strip(),
    )
    _write(
        tmp_path / "002_head.py",
        """
revision = "head_rev"
down_revision = "base_rev"
""".strip(),
    )

    report = guard.validate_migration_graph(
        versions_dir=tmp_path,
        require_single_head=True,
        require_db_at_head=False,
    )

    assert report.valid is True
    assert report.heads == ("head_rev",)
    assert report.revision_count == 2
    assert report.issues == ()


def test_validate_migration_graph_skips_db_probe_when_not_required(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write(
        tmp_path / "001_base.py",
        """
revision: str = "base_rev"
down_revision: str | None = None
""".strip(),
    )

    def _boom() -> tuple[str, ...]:
        raise RuntimeError("db should not be touched")

    monkeypatch.setattr(guard, "_collect_db_revisions", _boom)

    report = guard.validate_migration_graph(
        versions_dir=tmp_path,
        require_single_head=True,
        require_db_at_head=False,
    )

    assert report.valid is True
    assert report.issues == ()
    assert report.current_db_revisions == ()

