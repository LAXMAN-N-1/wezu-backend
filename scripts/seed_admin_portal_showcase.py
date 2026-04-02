#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.db.seeds.admin_portal_showcase import main


if __name__ == "__main__":
    raise SystemExit(main())
