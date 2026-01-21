import os
import shutil
from fastapi import UploadFile
from app.core.config import settings
import boto3

class StorageService:
    @staticmethod
    async def upload_file(file: UploadFile, directory: str = "misc") -> str:
        # Check if AWS S3 is configured
        if hasattr(settings, "AWS_ACCESS_KEY_ID") and settings.AWS_ACCESS_KEY_ID:
             return StorageService.upload_s3(file, directory)
        else:
             return await StorageService.upload_local(file, directory)

    @staticmethod
    async def upload_local(file: UploadFile, directory: str) -> str:
        os.makedirs(f"uploads/{directory}", exist_ok=True)
        file_path = f"uploads/{directory}/{file.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return f"/static/{file_path}"

    @staticmethod
    def upload_s3(file: UploadFile, directory: str) -> str:
        # Implement Boto3 upload logic
        # s3 = boto3.client(...)
        # s3.upload_fileobj(...)
        return f"https://{settings.AWS_BUCKET_NAME}.s3.amazonaws.com/{directory}/{file.filename}"
