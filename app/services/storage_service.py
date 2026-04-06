import shutil
import uuid
import logging
from pathlib import Path
from fastapi import UploadFile
from app.core.config import settings
from app.core.public_url import to_public_url
import boto3

logger = logging.getLogger(__name__)


class StorageService:
    @staticmethod
    def _should_use_s3() -> bool:
        provider = (settings.STORAGE_PROVIDER or "").strip().lower()
        if provider != "aws_s3":
            return False
        return bool(
            settings.AWS_ACCESS_KEY_ID
            and settings.AWS_SECRET_ACCESS_KEY
            and settings.AWS_BUCKET_NAME
            and settings.AWS_REGION
        )

    @staticmethod
    def _sanitize_directory(directory: str) -> str:
        raw = (directory or "misc").strip().strip("/")
        if not raw:
            return "misc"
        safe_parts = [part for part in raw.split("/") if part and part not in {".", ".."}]
        return "/".join(safe_parts) or "misc"

    @staticmethod
    def _build_safe_filename(original_name: str) -> str:
        suffix = Path(original_name or "").suffix.lower()
        return f"{uuid.uuid4().hex}{suffix}"

    @staticmethod
    async def upload_file(file: UploadFile, directory: str = "misc") -> str:
        if StorageService._should_use_s3():
            return StorageService.upload_s3(file, directory)
        return await StorageService.upload_local(file, directory)

    @staticmethod
    async def upload_local(file: UploadFile, directory: str) -> str:
        safe_dir = StorageService._sanitize_directory(directory)
        safe_name = StorageService._build_safe_filename(file.filename or "")
        output_dir = Path("uploads") / safe_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / safe_name
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return to_public_url(f"/uploads/{safe_dir}/{safe_name}")

    @staticmethod
    def upload_s3(file: UploadFile, directory: str) -> str:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        
        safe_dir = StorageService._sanitize_directory(directory)
        safe_name = StorageService._build_safe_filename(file.filename or "")
        file_path = f"{safe_dir}/{safe_name}"
        
        try:
            s3.upload_fileobj(
                file.file,
                settings.AWS_BUCKET_NAME,
                file_path,
                ExtraArgs={"ACL": "public-read", "ContentType": file.content_type}
            )
        except Exception:
            logger.exception("S3 upload failed for %s", file_path)
            raise
            
        if settings.AWS_S3_CUSTOM_DOMAIN:
            return f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/{file_path}"
        return f"https://{settings.AWS_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{file_path}"

storage_service = StorageService()
