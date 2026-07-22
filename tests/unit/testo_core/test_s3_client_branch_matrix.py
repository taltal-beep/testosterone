from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

import testo_core.s3_client as s3

pytestmark = [pytest.mark.unit]


def _client_error(*, http_status: int, code: str) -> ClientError:
    return ClientError(
        error_response={
            "Error": {"Code": code, "Message": "x"},
            "ResponseMetadata": {"HTTPStatusCode": http_status},
        },
        operation_name="HeadBucket",
    )


def test_default_minio_endpoint_prefers_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINIO_ENDPOINT", "http://example:9000")
    assert s3._default_minio_endpoint() == "http://example:9000"


def test_default_minio_endpoint_docker_vs_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MINIO_ENDPOINT", raising=False)
    monkeypatch.setattr(s3, "_is_running_in_docker", lambda: True)
    assert s3._default_minio_endpoint().startswith("http://uqo-minio")
    monkeypatch.setattr(s3, "_is_running_in_docker", lambda: False)
    assert s3._default_minio_endpoint().startswith("http://localhost")


def test_artifact_storage_requires_creds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MINIO_ROOT_USER", raising=False)
    monkeypatch.delenv("MINIO_ROOT_PASSWORD", raising=False)
    s3.ArtifactS3Storage.reset_instance_for_tests()
    with pytest.raises(ValueError):
        s3.ArtifactS3Storage()


def test_ensure_bucket_exists_creates_on_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINIO_ROOT_USER", "u")
    monkeypatch.setenv("MINIO_ROOT_PASSWORD", "p")
    s3.ArtifactS3Storage.reset_instance_for_tests()

    fake = MagicMock()
    fake.head_bucket.side_effect = _client_error(http_status=404, code="NoSuchBucket")

    # Patch boto3.client import inside __init__
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args, **kwargs):
        if name == "boto3":
            return SimpleNamespace(client=lambda *_a, **_kw: fake)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    st = s3.ArtifactS3Storage()
    st.ensure_bucket_exists("b")
    fake.create_bucket.assert_called()


def test_object_exists_false_on_clienterror(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINIO_ROOT_USER", "u")
    monkeypatch.setenv("MINIO_ROOT_PASSWORD", "p")
    s3.ArtifactS3Storage.reset_instance_for_tests()

    fake = MagicMock()
    fake.head_bucket.return_value = None
    fake.head_object.side_effect = _client_error(http_status=404, code="NotFound")

    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args, **kwargs):
        if name == "boto3":
            return SimpleNamespace(client=lambda *_a, **_kw: fake)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    st = s3.ArtifactS3Storage()
    assert st.object_exists("k") is False


def test_public_url_for_key_quotes_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINIO_ROOT_USER", "u")
    monkeypatch.setenv("MINIO_ROOT_PASSWORD", "p")
    monkeypatch.setenv("MINIO_PUBLIC_BASE_URL", "http://minio.local")
    s3.ArtifactS3Storage.reset_instance_for_tests()

    fake = MagicMock()
    fake.head_bucket.return_value = None

    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args, **kwargs):
        if name == "boto3":
            return SimpleNamespace(client=lambda *_a, **_kw: fake)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    st = s3.ArtifactS3Storage()
    url = st.public_url_for_key("a b/c")
    assert url == "http://minio.local/uqo-artifacts/a%20b/c"

