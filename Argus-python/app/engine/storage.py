import asyncio
import io
import logging
from typing import List

from minio import Minio
from minio.error import S3Error

from app.config import settings

logger = logging.getLogger(__name__)


class MinioStorageService:
    """MinIO object storage.

    All public methods are async — the minio-py client is blocking, so calls
    run in a worker thread to keep the event loop responsive (a synchronous
    download of a large file used to stall every request, SSE streams included).
    """

    def __init__(self):
        endpoint = settings.minio.endpoint
        self.client = Minio(
            endpoint=endpoint,
            access_key=settings.minio.access_key,
            secret_key=settings.minio.secret_key,
            secure=settings.minio.secure,
        )
        self.bucket = settings.minio.bucket
        self._ready_buckets: set[str] = set()
        logger.info("MinIO initialized: endpoint=%s, bucket=%s", endpoint, self.bucket)

    def _ensure_bucket(self, bucket: str) -> None:
        if bucket in self._ready_buckets:
            return
        if not self.client.bucket_exists(bucket):
            self.client.make_bucket(bucket)
            logger.info("Created MinIO bucket: %s", bucket)
        self._ready_buckets.add(bucket)

    async def upload(self, object_key: str, data: bytes, content_type: str, bucket: str | None = None) -> None:
        await asyncio.to_thread(self._upload, object_key, data, content_type, bucket)

    def _upload(self, object_key: str, data: bytes, content_type: str, bucket: str | None) -> None:
        bucket = bucket or self.bucket
        try:
            self._ensure_bucket(bucket)
            self.client.put_object(
                bucket, object_key, io.BytesIO(data), len(data), content_type=content_type
            )
        except S3Error as e:
            raise RuntimeError(f"MinIO upload failed: {e}")

    async def download(self, object_key: str, bucket: str | None = None) -> bytes:
        return await asyncio.to_thread(self._download, object_key, bucket)

    def _download(self, object_key: str, bucket: str | None) -> bytes:
        bucket = bucket or self.bucket
        try:
            response = self.client.get_object(bucket, object_key)
            return response.read()
        except S3Error as e:
            raise RuntimeError(f"MinIO download failed: {e}")

    async def delete(self, object_key: str, bucket: str | None = None) -> None:
        await asyncio.to_thread(self._delete, object_key, bucket)

    def _delete(self, object_key: str, bucket: str | None) -> None:
        bucket = bucket or self.bucket
        try:
            self.client.remove_object(bucket, object_key)
        except S3Error as e:
            raise RuntimeError(f"MinIO delete failed: {e}")

    async def compose(self, target_key: str, source_keys: List[str], content_type: str, bucket: str | None = None) -> None:
        await asyncio.to_thread(self._compose, target_key, source_keys, content_type, bucket)

    def _compose(self, target_key: str, source_keys: List[str], content_type: str, bucket: str | None) -> None:
        bucket = bucket or self.bucket
        if not source_keys:
            raise RuntimeError("No source keys for compose")
        try:
            from minio.commonconfig import ComposeSource
            sources = [ComposeSource(bucket, k) for k in source_keys]
            self.client.compose_object(bucket, target_key, sources)
            logger.info("Composed MinIO object: bucket=%s, target=%s, sources=%d", bucket, target_key, len(source_keys))
        except S3Error as e:
            raise RuntimeError(f"MinIO compose failed: {e}")

    async def check_health(self) -> bool:
        try:
            return await asyncio.to_thread(self.client.bucket_exists, self.bucket)
        except Exception as e:
            logger.warning("MinIO health check failed: %s", e)
            return False


storage_service = MinioStorageService()
