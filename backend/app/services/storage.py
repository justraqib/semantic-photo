from __future__ import annotations

import boto3
from botocore.client import Config

from app.core.config import settings


def _get_endpoint_url() -> str:
    if settings.R2_ENDPOINT_URL:
        return settings.R2_ENDPOINT_URL
    if not settings.R2_ACCOUNT_ID:
        raise ValueError("R2_ACCOUNT_ID is required when R2_ENDPOINT_URL is not set.")
    return f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"


def _get_bucket_name() -> str:
    if not settings.R2_BUCKET_NAME:
        raise ValueError("R2_BUCKET_NAME is required.")
    return settings.R2_BUCKET_NAME


def _get_client():
    if not settings.R2_ACCESS_KEY_ID or not settings.R2_SECRET_ACCESS_KEY:
        raise ValueError("R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY are required.")

    return boto3.client(
        "s3",
        endpoint_url=_get_endpoint_url(),
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name=settings.R2_REGION,
        config=Config(signature_version="s3v4"),
    )


def upload_file(file_bytes: bytes, key: str, content_type: str) -> None:
    client = _get_client()
    client.put_object(
        Bucket=_get_bucket_name(),
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )


def delete_file(key: str) -> None:
    client = _get_client()
    client.delete_object(Bucket=_get_bucket_name(), Key=key)


def generate_presigned_url(key: str, expires_in: int = 3600) -> str:
    client = _get_client()
    return client.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": _get_bucket_name(), "Key": key},
        ExpiresIn=expires_in,
    )
