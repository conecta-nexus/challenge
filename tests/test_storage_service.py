"""Unit tests for object storage service operations."""

from datetime import timedelta
from io import BytesIO
from unittest.mock import MagicMock

import pytest

from src.core.storage import StorageClient
from src.services.storage_service import StorageService, StorageServiceError


BUCKET_NAME = "challenge-attachments"
PART_SIZE_BYTES = 10 * 1024 * 1024


@pytest.fixture
def minio_client() -> MagicMock:
    """Provide a mocked MinIO SDK client."""
    return MagicMock()


@pytest.fixture
def storage_client(minio_client: MagicMock) -> MagicMock:
    """Provide the storage adapter expected by StorageService."""
    client = MagicMock(spec=StorageClient)
    client.client = minio_client
    client.bucket_name = BUCKET_NAME
    client.part_size_bytes = PART_SIZE_BYTES
    return client


@pytest.fixture
def storage_service(storage_client: MagicMock) -> StorageService:
    """Build the service with no real MinIO connection."""
    return StorageService(storage_client=storage_client)


async def test_upload_file_streams_binary_content(
    storage_service: StorageService,
    minio_client: MagicMock,
) -> None:
    """Pass the original binary stream to MinIO without loading it in memory."""
    content = b"challenge attachment content"
    file_obj = BytesIO(content)
    streamed_objects: list[BytesIO] = []

    def consume_stream(**kwargs) -> None:
        stream = kwargs["data"]
        streamed_objects.append(stream)
        assert stream.read() == content

    minio_client.put_object.side_effect = consume_stream

    result = await storage_service.upload_file(
        file_obj=file_obj,
        destination_path="challenges/123/attachments/proposal.pdf",
        content_type="application/pdf",
    )

    assert result == "challenges/123/attachments/proposal.pdf"
    assert streamed_objects == [file_obj]
    minio_client.put_object.assert_called_once_with(
        bucket_name=BUCKET_NAME,
        object_name="challenges/123/attachments/proposal.pdf",
        data=file_obj,
        length=-1,
        part_size=PART_SIZE_BYTES,
        content_type="application/pdf",
    )


async def test_generate_signed_url_uses_requested_expiration(
    storage_service: StorageService,
    minio_client: MagicMock,
) -> None:
    """Return the signed URL produced by MinIO with the requested lifetime."""
    expected_url = (
        "http://minio:9000/challenge-attachments/attachment.pdf?signature=test"
    )
    minio_client.presigned_get_object.return_value = expected_url

    result = await storage_service.generate_signed_url(
        storage_path="/challenges/123/attachment.pdf",
        expires_in_seconds=900,
    )

    assert result == expected_url
    minio_client.presigned_get_object.assert_called_once_with(
        bucket_name=BUCKET_NAME,
        object_name="challenges/123/attachment.pdf",
        expires=timedelta(seconds=900),
    )


async def test_delete_file_removes_object(
    storage_service: StorageService,
    minio_client: MagicMock,
) -> None:
    """Delete the normalized object path and report success."""
    result = await storage_service.delete_file("/challenges/123/attachment.pdf")

    assert result is True
    minio_client.remove_object.assert_called_once_with(
        bucket_name=BUCKET_NAME,
        object_name="challenges/123/attachment.pdf",
    )


async def test_upload_file_rejects_empty_content_type(
    storage_service: StorageService,
    minio_client: MagicMock,
) -> None:
    """Reject invalid metadata before invoking the storage provider."""
    with pytest.raises(ValueError, match="content_type cannot be empty"):
        await storage_service.upload_file(
            file_obj=BytesIO(b"content"),
            destination_path="challenges/123/attachment.bin",
            content_type="   ",
        )

    minio_client.put_object.assert_not_called()


@pytest.mark.parametrize("expires_in_seconds", [0, 604801])
async def test_generate_signed_url_rejects_invalid_expiration(
    storage_service: StorageService,
    minio_client: MagicMock,
    expires_in_seconds: int,
) -> None:
    """Reject expirations outside the MinIO-supported range."""
    with pytest.raises(
        ValueError,
        match="expires_in_seconds must be between 1 and 604800",
    ):
        await storage_service.generate_signed_url(
            storage_path="challenges/123/attachment.pdf",
            expires_in_seconds=expires_in_seconds,
        )

    minio_client.presigned_get_object.assert_not_called()


async def test_storage_path_rejects_parent_segments(
    storage_service: StorageService,
    minio_client: MagicMock,
) -> None:
    """Prevent object keys from containing directory traversal segments."""
    with pytest.raises(
        ValueError,
        match="storage_path cannot contain parent path segments",
    ):
        await storage_service.generate_signed_url("challenges/../secret.txt")

    minio_client.presigned_get_object.assert_not_called()


async def test_storage_provider_error_is_translated(
    storage_service: StorageService,
    minio_client: MagicMock,
) -> None:
    """Expose a service-level exception instead of a provider error."""
    minio_client.presigned_get_object.side_effect = OSError("connection failed")

    with pytest.raises(
        StorageServiceError,
        match="Unable to generate a signed URL",
    ):
        await storage_service.generate_signed_url(
            "challenges/123/attachment.pdf"
        )

