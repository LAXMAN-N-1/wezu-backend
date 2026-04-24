from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import inspect, text

from app.core.config import settings
from app.core.database import engine


@dataclass(frozen=True)
class _RevisionFile:
    path: Path
    revision: str
    down_revisions: tuple[str, ...]


@dataclass(frozen=True)
class MigrationGraphReport:
    valid: bool
    issues: tuple[str, ...]
    heads: tuple[str, ...]
    revision_count: int
    current_db_revisions: tuple[str, ...]


def _extract_literal(node: ast.AST):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.Tuple, ast.List)):
        values: list[object] = []
        for elt in node.elts:
            values.append(_extract_literal(elt))
        return values
    return None


def _normalize_down_revisions(value: object) -> tuple[str, ...]:
    if value is None:
        return tuple()
    if isinstance(value, str):
        stripped = value.strip()
        return (stripped,) if stripped else tuple()
    if isinstance(value, (list, tuple)):
        cleaned: list[str] = []
        for item in value:
            if item is None:
                continue
            item_str = str(item).strip()
            if item_str:
                cleaned.append(item_str)
        return tuple(cleaned)
    item_str = str(value).strip()
    return (item_str,) if item_str else tuple()


def _parse_revision_file(path: Path) -> _RevisionFile | None:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    revision = None
    down_revision_value = None

    for node in tree.body:
        target_names: list[str] = []
        value_node: ast.AST | None = None

        if isinstance(node, ast.Assign):
            value_node = node.value
            for target in node.targets:
                if isinstance(target, ast.Name):
                    target_names.append(target.id)
        elif isinstance(node, ast.AnnAssign):
            value_node = node.value
            if isinstance(node.target, ast.Name):
                target_names.append(node.target.id)

        if not value_node or not target_names:
            continue

        for name in target_names:
            if name == "revision":
                revision = _extract_literal(value_node)
            elif name == "down_revision":
                down_revision_value = _extract_literal(value_node)

    if not revision or not isinstance(revision, str):
        return None

    return _RevisionFile(
        path=path,
        revision=revision.strip(),
        down_revisions=_normalize_down_revisions(down_revision_value),
    )


def _detect_cycles(revisions: dict[str, _RevisionFile]) -> list[str]:
    issues: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(revision: str, stack: list[str]) -> None:
        if revision in visiting:
            cycle_path = " -> ".join(stack + [revision])
            issues.append(f"cycle detected in revision graph: {cycle_path}")
            return
        if revision in visited:
            return

        visiting.add(revision)
        stack.append(revision)
        node = revisions.get(revision)
        if node:
            for parent in node.down_revisions:
                if parent in revisions:
                    dfs(parent, stack)
        stack.pop()
        visiting.remove(revision)
        visited.add(revision)

    for rev in revisions.keys():
        dfs(rev, [])

    return issues


def _collect_db_revisions() -> tuple[str, ...]:
    with engine.begin() as conn:
        inspector = inspect(conn)
        if not inspector.has_table("alembic_version"):
            return tuple()
        rows = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        revisions = sorted({str(row[0]).strip() for row in rows if row and row[0]})
        return tuple(revisions)


def _head_revisions(revisions: dict[str, _RevisionFile]) -> tuple[str, ...]:
    referenced: set[str] = set()
    for node in revisions.values():
        for parent in node.down_revisions:
            if parent:
                referenced.add(parent)
    heads = sorted(rev for rev in revisions if rev not in referenced)
    return tuple(heads)


def validate_migration_graph(
    *,
    versions_dir: str | Path | None = None,
    require_single_head: bool | None = None,
    require_db_at_head: bool | None = None,
) -> MigrationGraphReport:
    directory = Path(versions_dir or getattr(settings, "MIGRATION_GRAPH_VERSIONS_DIR", "alembic/versions"))
    single_head = (
        bool(require_single_head)
        if require_single_head is not None
        else bool(getattr(settings, "MIGRATION_GRAPH_REQUIRE_SINGLE_HEAD", True))
    )
    db_at_head = (
        bool(require_db_at_head)
        if require_db_at_head is not None
        else bool(getattr(settings, "MIGRATION_GRAPH_REQUIRE_DB_AT_HEAD", True))
    )

    issues: list[str] = []

    if not directory.exists() or not directory.is_dir():
        return MigrationGraphReport(
            valid=False,
            issues=(f"migration versions directory not found: {directory}",),
            heads=tuple(),
            revision_count=0,
            current_db_revisions=tuple(),
        )

    parsed_files: list[_RevisionFile] = []
    parse_failures: list[str] = []
    feature_slug_to_files: dict[str, list[str]] = {}

    for path in sorted(directory.glob("*.py")):
        parsed = _parse_revision_file(path)
        if parsed is None:
            parse_failures.append(path.name)
            continue
        parsed_files.append(parsed)

        name = path.name
        if "_" in name:
            feature_slug = name.split("_", 1)[1].removesuffix(".py")
            feature_slug_to_files.setdefault(feature_slug, []).append(name)

    if parse_failures:
        issues.append("unparseable migration metadata: " + ", ".join(parse_failures))

    revisions: dict[str, _RevisionFile] = {}
    duplicates: dict[str, list[str]] = {}
    for entry in parsed_files:
        existing = revisions.get(entry.revision)
        if existing:
            duplicates.setdefault(entry.revision, [existing.path.name]).append(entry.path.name)
            continue
        revisions[entry.revision] = entry

    for rev, files in sorted(duplicates.items()):
        unique_files = sorted(dict.fromkeys(files))
        issues.append(
            f"duplicate alembic revision '{rev}' found in: {', '.join(unique_files)}"
        )

    for rev, node in sorted(revisions.items()):
        for parent in node.down_revisions:
            if parent not in revisions:
                issues.append(
                    f"revision '{rev}' ({node.path.name}) references missing down_revision '{parent}'"
                )

    issues.extend(_detect_cycles(revisions))

    for feature_slug, files in sorted(feature_slug_to_files.items()):
        if len(files) > 1:
            issues.append(
                "duplicate migration feature slug '"
                + feature_slug
                + "' appears in multiple files: "
                + ", ".join(sorted(files))
            )

    heads = _head_revisions(revisions)
    if single_head and len(heads) != 1:
        issues.append(f"expected exactly 1 alembic head, found {len(heads)}: {', '.join(heads)}")

    db_revisions = tuple()
    if db_at_head:
        try:
            db_revisions = _collect_db_revisions()
        except Exception as exc:
            issues.append(f"failed to inspect alembic_version table: {exc}")

    if db_at_head:
        if not db_revisions:
            issues.append("alembic_version table missing or empty; database is not stamped")
        else:
            unknown = [rev for rev in db_revisions if rev not in revisions]
            if unknown:
                issues.append("database has unknown alembic revisions: " + ", ".join(sorted(unknown)))
            if heads and set(db_revisions) != set(heads):
                issues.append(
                    "database revision is not at migration head "
                    f"(db={','.join(db_revisions)} head={','.join(heads)})"
                )

    return MigrationGraphReport(
        valid=not issues,
        issues=tuple(issues),
        heads=heads,
        revision_count=len(revisions),
        current_db_revisions=db_revisions,
    )
