"""
AWS S3 Integration
Handles file upload, download, and storage
"""
import boto3
from botocore.exceptions import ClientError
from typing import Optional, Dict, Any
from app.core.config import settings
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AWSS3Integration:
    """AWS S3 storage wrapper"""
    
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.bucket_name = settings.AWS_S3_BUCKET
    
    def upload_file(
        self,
        file_path: str,
        object_name: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """
        Upload file to S3
        
        Args:
            file_path: Local file path
            object_name: S3 object name (defaults to file_path)
            metadata: Optional metadata
            
        Returns:
            S3 URL if successful
        """
        if object_name is None:
            object_name = file_path
        
        try:
            extra_args = {}
            if metadata:
                extra_args['Metadata'] = metadata
            
            self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                object_name,
                ExtraArgs=extra_args
            )
            
            url = f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{object_name}"
            logger.info(f"File uploaded successfully: {url}")
            return url
            
        except ClientError as e:
            logger.error(f"Failed to upload file: {str(e)}")
            return None
    
    def upload_fileobj(
        self,
        file_obj,
        object_name: str,
        content_type: Optional[str] = None
    ) -> Optional[str]:
        """
        Upload file object to S3
        
        Args:
            file_obj: File-like object
            object_name: S3 object name
            content_type: MIME type
            
        Returns:
            S3 URL if successful
        """
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                object_name,
                ExtraArgs=extra_args
            )
            
            url = f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{object_name}"
            logger.info(f"File object uploaded successfully: {url}")
            return url
            
        except ClientError as e:
            logger.error(f"Failed to upload file object: {str(e)}")
            return None
    
    def download_file(
        self,
        object_name: str,
        file_path: str
    ) -> bool:
        """
        Download file from S3
        
        Args:
            object_name: S3 object name
            file_path: Local file path to save
            
        Returns:
            True if successful
        """
        try:
            self.s3_client.download_file(
                self.bucket_name,
                object_name,
                file_path
            )
            logger.info(f"File downloaded successfully: {file_path}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to download file: {str(e)}")
            return False
    
    def generate_presigned_url(
        self,
        object_name: str,
        expiration: int = 3600,
        http_method: str = 'get_object'
    ) -> Optional[str]:
        """
        Generate presigned URL for temporary access
        
        Args:
            object_name: S3 object name
            expiration: URL expiration in seconds
            http_method: HTTP method (get_object, put_object)
            
        Returns:
            Presigned URL
        """
        try:
            url = self.s3_client.generate_presigned_url(
                http_method,
                Params={
                    'Bucket': self.bucket_name,
                    'Key': object_name
                },
                ExpiresIn=expiration
            )
            logger.info(f"Presigned URL generated for {object_name}")
            return url
            
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {str(e)}")
            return None
    
    def delete_file(self, object_name: str) -> bool:
        """
        Delete file from S3
        
        Args:
            object_name: S3 object name
            
        Returns:
            True if successful
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=object_name
            )
            logger.info(f"File deleted successfully: {object_name}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to delete file: {str(e)}")
            return False
    
    def list_files(
        self,
        prefix: Optional[str] = None,
        max_keys: int = 1000
    ) -> list:
        """
        List files in bucket
        
        Args:
            prefix: Filter by prefix
            max_keys: Maximum number of keys to return
            
        Returns:
            List of file objects
        """
        try:
            params = {
                'Bucket': self.bucket_name,
                'MaxKeys': max_keys
            }
            if prefix:
                params['Prefix'] = prefix
            
            response = self.s3_client.list_objects_v2(**params)
            
            files = []
            for obj in response.get('Contents', []):
                files.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                    'etag': obj['ETag']
                })
            
            return files
            
        except ClientError as e:
            logger.error(f"Failed to list files: {str(e)}")
            return []
    
    def file_exists(self, object_name: str) -> bool:
        """Check if file exists in S3"""
        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=object_name
            )
            return True
        except ClientError:
            return False


# Singleton instance
aws_s3_integration = AWSS3Integration()
