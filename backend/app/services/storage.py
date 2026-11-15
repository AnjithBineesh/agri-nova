"""File storage abstraction: local filesystem by default, S3-compatible object storage when configured.

Files are stored under random names (never the user-supplied filename) and are only served
through authorised API endpoints.
"""
import uuid
from pathlib import Path

from ..config import get_settings


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes, folder: str, suffix: str) -> str:
        d = self.root / folder
        d.mkdir(parents=True, exist_ok=True)
        key = f"{folder}/{uuid.uuid4().hex}{suffix}"
        (self.root / key).write_bytes(data)
        return key

    def read(self, key: str) -> bytes:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise PermissionError("Invalid storage key")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = (self.root / key).resolve()
        if self.root.resolve() in path.parents and path.exists():
            path.unlink()


class S3Storage:  # pragma: no cover - requires boto3 and a bucket
    def __init__(self, bucket: str, endpoint_url: str | None):
        import boto3

        self.bucket = bucket
        self.client = boto3.client("s3", endpoint_url=endpoint_url)

    def save(self, data: bytes, folder: str, suffix: str) -> str:
        key = f"{folder}/{uuid.uuid4().hex}{suffix}"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ServerSideEncryption="AES256")
        return key

    def read(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


_storage = None


def get_storage():
    global _storage
    if _storage is None:
        s = get_settings()
        _storage = S3Storage(s.s3_bucket, s.s3_endpoint_url) if s.storage_backend == "s3" and s.s3_bucket \
            else LocalStorage(Path(s.storage_dir))
    return _storage
