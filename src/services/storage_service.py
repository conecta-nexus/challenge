"""Object storage operations used by challenge attachment workflows."""

import asyncio
from datetime import timedelta
from typing import BinaryIO

from minio.error import MinioException
from urllib3.exceptions import HTTPError

from src.core.storage import StorageClient, get_storage_client


class StorageServiceError(RuntimeError):
    """Represent an object storage operation failure."""


class StorageService:
    """Provide asynchronous application-facing object storage operations."""

    MAX_SIGNED_URL_EXPIRY_SECONDS = 7 * 24 * 60 * 60

    def __init__(self, storage_client: StorageClient | None = None) -> None:
        self._storage = storage_client or get_storage_client()

    async def upload_file(
        self,
        file_obj: BinaryIO,
        destination_path: str,
        content_type: str,
    ) -> str:
        """Stream a file object into storage and return its object path."""
        object_name = self._validate_storage_path(destination_path)
        if not content_type.strip():
            raise ValueError("content_type cannot be empty")

        try:
            await asyncio.to_thread(
                self._storage.client.put_object,
                bucket_name=self._storage.bucket_name,
                object_name=object_name,
                data=file_obj,
                length=-1,
                part_size=self._storage.part_size_bytes,
                content_type=content_type,
            )
        except (MinioException, HTTPError, OSError) as exc:
            raise StorageServiceError(
                f"Unable to upload object '{object_name}'"
            ) from exc

        return object_name

    async def generate_signed_url(
        self,
        storage_path: str,
        expires_in_seconds: int = 3600,
    ) -> str:
        """Generate an ephemeral signed download URL."""
        object_name = self._validate_storage_path(storage_path)
        if not 1 <= expires_in_seconds <= self.MAX_SIGNED_URL_EXPIRY_SECONDS:
            raise ValueError("expires_in_seconds must be between 1 and 604800")

        try:
            return await asyncio.to_thread(
                self._storage.client.presigned_get_object,
                bucket_name=self._storage.bucket_name,
                object_name=object_name,
                expires=timedelta(seconds=expires_in_seconds),
            )
        except (MinioException, HTTPError, OSError) as exc:
            raise StorageServiceError(
                f"Unable to generate a signed URL for '{object_name}'"
            ) from exc

    async def delete_file(self, storage_path: str) -> bool:
        """Delete an object; S3 deletion remains idempotent."""
        object_name = self._validate_storage_path(storage_path)

        try:
            await asyncio.to_thread(
                self._storage.client.remove_object,
                bucket_name=self._storage.bucket_name,
                object_name=object_name,
            )
        except (MinioException, HTTPError, OSError) as exc:
            raise StorageServiceError(
                f"Unable to delete object '{object_name}'"
            ) from exc

        return True

    @staticmethod
    def _validate_storage_path(storage_path: str) -> str:
        object_name = storage_path.strip().lstrip("/")
        if not object_name:
            raise ValueError("storage_path cannot be empty")
        if ".." in object_name.split("/"):
            raise ValueError("storage_path cannot contain parent path segments")
        return object_name
