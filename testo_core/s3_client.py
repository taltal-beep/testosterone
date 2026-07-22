"""
MinIO / S3-compatible artifact storage (boto3).

Credentials: MINIO_ROOT_USER, MINIO_ROOT_PASSWORD.
Endpoint defaults: http://localhost:9000 on the host, http://uqo-minio:9000 in Docker.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

from botocore.config import Config
from botocore.exceptions import ClientError


def _is_running_in_docker() -> bool:
    return Path("/.dockerenv").exists() or os.getenv("RUNNING_IN_DOCKER", "").lower() in {"1", "true", "yes"}


def _default_minio_endpoint() -> str:
    v = (os.getenv("MINIO_ENDPOINT") or "").strip()
    if v:
        return v
    return "http://uqo-minio:9000" if _is_running_in_docker() else "http://localhost:9000"


def _public_base_url() -> str:
    """Browser / API base for path-style object URLs (defaults to MINIO_ENDPOINT)."""
    return (os.getenv("MINIO_PUBLIC_BASE_URL") or os.getenv("MINIO_ENDPOINT") or _default_minio_endpoint()).rstrip(
        "/"
    )


class ArtifactS3Storage:
    """
    Singleton wrapper around a boto3 S3 client configured for MinIO.
    """

    _instance: ArtifactS3Storage | None = None

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        access = (os.getenv("MINIO_ROOT_USER") or "").strip()
        secret = (os.getenv("MINIO_ROOT_PASSWORD") or "").strip()
        if not access or not secret:
            raise ValueError("MINIO_ROOT_USER and MINIO_ROOT_PASSWORD are required for S3 artifact storage")
        endpoint = _default_minio_endpoint()
        region = (os.getenv("MINIO_REGION") or "us-east-1").strip()
        self._bucket = (os.getenv("BUCKET_NAME") or "uqo-artifacts").strip()
        import boto3

        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access,
            aws_secret_access_key=secret,
            region_name=region,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        self._initialized = True
        self.ensure_bucket_exists(self._bucket)

    @classmethod
    def instance(cls) -> ArtifactS3Storage:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance_for_tests(cls) -> None:
        cls._instance = None

    @property
    def bucket_name(self) -> str:
        return self._bucket

    def ensure_bucket_exists(self, bucket_name: str | None = None) -> None:
        b = (bucket_name or self._bucket).strip()
        try:
            self._client.head_bucket(Bucket=b)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            http = int(e.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0) or 0)
            if http == 404 or code in ("404", "NoSuchBucket", "NotFound"):
                self._client.create_bucket(Bucket=b)
            else:
                raise

    def upload_file(self, local_path: str | Path, s3_key: str, bucket_name: str | None = None) -> None:
        b = (bucket_name or self._bucket).strip()
        self._client.upload_file(str(local_path), b, s3_key.replace("\\", "/"))

    def object_exists(self, key: str, bucket_name: str | None = None) -> bool:
        b = (bucket_name or self._bucket).strip()
        try:
            self._client.head_object(Bucket=b, Key=key)
            return True
        except ClientError:
            return False

    def list_keys_under_prefix(self, prefix: str, bucket_name: str | None = None) -> list[str]:
        b = (bucket_name or self._bucket).strip()
        keys: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=b, Prefix=prefix):
            for obj in page.get("Contents") or []:
                k = obj.get("Key")
                if k:
                    keys.append(k)
        return keys

    def get_object_bytes(self, key: str, bucket_name: str | None = None) -> bytes:
        b = (bucket_name or self._bucket).strip()
        resp = self._client.get_object(Bucket=b, Key=key)
        return resp["Body"].read()

    def public_url_for_key(self, key: str, bucket_name: str | None = None) -> str:
        """Path-style URL suitable for anonymous download if bucket policy allows."""
        b = (bucket_name or self._bucket).strip()
        base = _public_base_url()
        safe_key = quote(key, safe="/")
        return f"{base}/{b}/{safe_key}"


def get_artifact_s3() -> ArtifactS3Storage:
    """Return the shared MinIO S3 client (creates bucket on first use)."""
    return ArtifactS3Storage.instance()


if __name__ == "__main__":
    import tempfile

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    storage = get_artifact_s3()
    storage.ensure_bucket_exists()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("hello from uqo s3 smoke test\n")
        tmp_path = f.name
    try:
        key = "runs/_smoke_/artifacts/hello_world.txt"
        storage.upload_file(tmp_path, key)
        print(f"Uploaded s3://{storage.bucket_name}/{key}")
        data = storage.get_object_bytes(key)
        print(f"Read back ({len(data)} bytes): {data[:80]!r}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)
