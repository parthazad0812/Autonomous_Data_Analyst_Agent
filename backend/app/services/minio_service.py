from minio import Minio
from minio.error import S3Error
import io
from datetime import timedelta
from app.config import settings


def get_minio_client() -> Minio:
    """Return a configured MinIO client."""
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def ensure_bucket_exists() -> None:
    """Create the datasets bucket if it doesn't exist yet."""
    client = get_minio_client()
    bucket = settings.minio_bucket
    try:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
    except S3Error as e:
        raise RuntimeError(f"MinIO bucket error: {e}") from e


def upload_file_to_minio(
    object_name: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> str:
    """
    Upload raw bytes to MinIO.
    Returns the object name (used as the storage path).
    """
    ensure_bucket_exists()
    client = get_minio_client()
    client.put_object(
        settings.minio_bucket,
        object_name,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return object_name


def delete_file_from_minio(object_name: str) -> None:
    """Remove an object from MinIO. Silently ignores if not found."""
    client = get_minio_client()
    try:
        client.remove_object(settings.minio_bucket, object_name)
    except S3Error:
        pass


def get_presigned_url(object_name: str, expires_hours: int = 1) -> str:
    """Generate a presigned GET URL for temporary access."""
    client = get_minio_client()
    return client.presigned_get_object(
        settings.minio_bucket,
        object_name,
        expires=timedelta(hours=expires_hours),
    )
