#!/usr/bin/env python3
from __future__ import annotations

from app.db.migration_graph_guard import validate_migration_graph


def main() -> int:
    report = validate_migration_graph()
    if report.valid:
        print(
            "OK migration graph",
            f"heads={','.join(report.heads)}",
            f"revisions={report.revision_count}",
            f"db={','.join(report.current_db_revisions) or 'none'}",
        )
        return 0

    print("INVALID migration graph")
    for issue in report.issues:
        print(f"- {issue}")
    print(f"heads={','.join(report.heads) or 'none'}")
    print(f"revisions={report.revision_count}")
    print(f"db={','.join(report.current_db_revisions) or 'none'}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
