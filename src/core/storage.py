"""MinIO client initialization and storage lifecycle management."""

import asyncio
from functools import lru_cache

import urllib3
from minio import Minio
from urllib3.util import Retry, Timeout

from src.core.config import Settings, settings


class StorageClient:
    """Own a reusable MinIO client and its HTTP connection pool."""

    def __init__(self, app_settings: Settings) -> None:
        self._settings = app_settings
        self._http_client = urllib3.PoolManager(
            maxsize=app_settings.storage_pool_max_size,
            block=True,
            timeout=Timeout(connect=5.0, read=60.0),
            retries=Retry(
                total=3,
                connect=3,
                read=2,
                backoff_factor=0.2,
                status_forcelist=(500, 502, 503, 504),
            ),
        )
        self._client = Minio(
            endpoint=app_settings.storage_endpoint,
            access_key=app_settings.storage_access_key,
            secret_key=app_settings.storage_secret_key,
            secure=app_settings.storage_secure,
            region=app_settings.storage_region,
            http_client=self._http_client,
        )

    @property
    def client(self) -> Minio:
        return self._client

    @property
    def bucket_name(self) -> str:
        return self._settings.storage_bucket

    @property
    def part_size_bytes(self) -> int:
        return self._settings.storage_part_size_bytes

    def ensure_bucket(self) -> None:
        """Create the configured bucket when it does not already exist."""
        if not self._client.bucket_exists(self.bucket_name):
            self._client.make_bucket(
                bucket_name=self.bucket_name,
                location=self._settings.storage_region,
            )

    def close(self) -> None:
        """Release pooled HTTP connections."""
        self._http_client.clear()


@lru_cache(maxsize=1)
def get_storage_client() -> StorageClient:
    """Return the process-wide storage client."""
    return StorageClient(settings)


async def initialize_storage() -> None:
    """Initialize storage and create the local bucket when enabled."""
    if settings.storage_auto_create_bucket:
        await asyncio.to_thread(get_storage_client().ensure_bucket)


def shutdown_storage() -> None:
    """Close pooled connections created by the process-wide client."""
    get_storage_client().close()
    get_storage_client.cache_clear()
