from fastapi import APIRouter, Depends, Body
from sqlmodel import Session
from app.api import deps
from app.models.user import User

router = APIRouter()

@router.get("/preferences")
def get_user_preferences(
    current_user: User = Depends(deps.get_current_user)
):
    """Get admin UI theme & session preferences."""
    import json
    prefs = {}
    if current_user.ui_preferences:
        try:
            prefs = json.loads(current_user.ui_preferences)
        except json.JSONDecodeError:
            pass
    return {"ui_preferences": prefs}

@router.post("/preferences")
def update_user_preferences(
    preferences: dict = Body(...),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Store admin UI theme & session preferences (Dark/Light mode)."""
    import json
    # Use nested ui_preferences key if provided, otherwise entirely
    new_prefs = preferences.get("ui_preferences", preferences)
    
    # Merge with existing
    current_prefs = {}
    if current_user.ui_preferences:
        try:
            current_prefs = json.loads(current_user.ui_preferences)
        except json.JSONDecodeError:
            pass
            
    current_prefs.update(new_prefs)
    
    current_user.ui_preferences = json.dumps(current_prefs)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    
    return {"message": "Preferences updated successfully", "ui_preferences": current_prefs}
