from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class DashboardWidget(BaseModel):
    id: str
    type: str # chart, stat, list, map
    title: str
    config: Dict[str, Any] = {}
    position: Dict[str, int] # x, y, w, h

class DashboardConfigResponse(BaseModel):
    layout: List[DashboardWidget]
