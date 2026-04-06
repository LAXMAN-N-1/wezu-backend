from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from app.api import deps
from app.services.storage_service import storage_service
from app.models.user import User

router = APIRouter()

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    directory: str = "misc",
    current_user: User = Depends(deps.get_current_user),
):
    """
    Generic file upload endpoint.
    Returns the URL of the uploaded file.
    """
    try:
        url = await storage_service.upload_file(file, directory)
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
