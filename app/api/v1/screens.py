from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any, List
from sqlmodel import Session
from app.api import deps
from app.core.rbac import canonical_role_name, role_sort_key
from app.models.user import User
from app.schemas.ui_config import ScreenConfig, ScreenColumn, ScreenAction
from app.core.screen_config import MASTER_SCREEN_CONFIG
from app.services.auth_service import AuthService

router = APIRouter()

@router.get("/{screen_id}/config", response_model=ScreenConfig)
def get_screen_config(
    screen_id: str,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Get dynamic configuration for a specific screen based on user permissions.
    """
    # 1. Validate Screen ID
    screen_def = MASTER_SCREEN_CONFIG.get(screen_id)
    if not screen_def:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Screen configuration not found for '{screen_id}'"
        )

    # 2. Get User Permissions
    current_role = canonical_role_name(current_user.role.name) if current_user.role else None
    if not current_role:
        role_names = sorted(deps.get_user_role_names(current_user), key=lambda value: role_sort_key(value))
        current_role = role_names[0] if role_names else None
    
    # In a real scenario, we'd merge permissions from all roles, but sticking to existing pattern
    permissions_list = []
    if current_role:
        permissions_list = AuthService.get_permissions_for_role(db, current_role)
    
    user_permissions = set(permissions_list)
    has_all_access = "all" in user_permissions

    # 3. Process Columns
    processed_columns: List[ScreenColumn] = []
    for col in screen_def.get("columns", []):
        perm_req = col.get("permission_required")
        
        # Determine visibility
        is_visible = col.get("visible", True)
        if perm_req:
            if not has_all_access and perm_req not in user_permissions:
                is_visible = False
        
        processed_columns.append(ScreenColumn(
            field=col["field"],
            label=col["label"],
            visible=is_visible,
            sortable=col.get("sortable", False),
            permission_required=perm_req
        ))

    # 4. Process Actions
    processed_actions: List[ScreenAction] = []
    for action in screen_def.get("actions", []):
        perm_req = action.get("permission")
        
        # Determine enabled/availability
        # Requirement: "enabled: false // user doesn't have permission"
        is_enabled = action.get("enabled", True)
        if perm_req:
            if not has_all_access and perm_req not in user_permissions:
                is_enabled = False

        processed_actions.append(ScreenAction(
            id=action["id"],
            label=action["label"],
            enabled=is_enabled,
            permission=perm_req
        ))

    return ScreenConfig(
        screen_id=screen_id,
        columns=processed_columns,
        actions=processed_actions,
        filters=screen_def.get("filters", []),
        bulk_actions=screen_def.get("bulk_actions", [])
    )
