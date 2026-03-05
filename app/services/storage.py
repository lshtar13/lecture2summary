import os
import boto3
from botocore.client import Config
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class StorageService:
    def __init__(self):
        self.endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
        self.bucket_name = os.getenv("MINIO_BUCKET_NAME", "lectures")
        self.secure = os.getenv("MINIO_SECURE", "False") == "True"

        self.s3 = boto3.client(
            "s3",
            endpoint_url=f"http://{self.endpoint}" if not self.secure else f"https://{self.endpoint}",
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",  # MinIO default
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            self.s3.head_bucket(Bucket=self.bucket_name)
        except:
            self.s3.create_bucket(Bucket=self.bucket_name)

    def upload_file(self, file_path: str, object_name: str) -> bool:
        try:
            self.s3.upload_file(file_path, self.bucket_name, object_name)
            return True
        except Exception as e:
            print(f"Error uploading to MinIO: {e}")
            return False

    def download_file(self, object_name: str, download_path: str) -> bool:
        try:
            self.s3.download_file(self.bucket_name, object_name, download_path)
            return True
        except Exception as e:
            print(f"Error downloading from MinIO: {e}")
            return False

    def delete_file(self, object_name: str) -> bool:
        try:
            self.s3.delete_object(Bucket=self.bucket_name, Key=object_name)
            return True
        except Exception as e:
            print(f"Error deleting from MinIO: {e}")
            return False

    def get_presigned_url(self, object_name: str, expiration=3600) -> str:
        try:
            url = self.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": object_name},
                ExpiresIn=expiration,
            )
            return url
        except Exception as e:
            print(f"Error generating presigned URL: {e}")
            return ""
