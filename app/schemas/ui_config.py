from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class ScreenColumn(BaseModel):
    field: str
    label: str
    visible: bool = True
    sortable: bool = False
    permission_required: Optional[str] = None

class ScreenAction(BaseModel):
    id: str
    label: str
    enabled: bool = True
    permission: Optional[str] = None

class ScreenConfig(BaseModel):
    screen_id: str
    columns: List[ScreenColumn]
    actions: List[ScreenAction] = []
    filters: List[Dict[str, Any]] = []
    bulk_actions: List[Dict[str, Any]] = []
