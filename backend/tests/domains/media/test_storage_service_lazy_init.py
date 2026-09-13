"""Tests that StorageService defers every S3 call until storage is used.

Construction must never connect, so a cold start does not pay for or fail on S3.
"""

import logging
from typing import Iterator
from unittest.mock import MagicMock, patch
from uuid import uuid4

import boto3
import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException
from moto import mock_aws

import app.api.services.storage_service as ss_module
from app.api.services.storage_service import StorageService
from app.core.config import settings

BUCKET = "lazy-init-bucket"


@pytest.fixture
def live_storage_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Point settings at a live bucket and disable the test-environment short circuit."""
    monkeypatch.setattr(settings, "USER_IMAGES_BUCKET", BUCKET)
    monkeypatch.setattr(settings, "AWS_ACCESS_KEY_ID", "AKIATEST")
    monkeypatch.setattr(settings, "AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setattr(settings, "AWS_SESSION_TOKEN", "session-token")
    monkeypatch.setattr(settings, "AWS_REGION", "us-west-2")
    monkeypatch.setattr(settings, "S3_ENDPOINT_URL", "")
    with patch.object(ss_module, "_is_test_environment", return_value=False):
        yield


def forbidden() -> ClientError:
    """A HeadBucket 403 ClientError."""
    return ClientError({"Error": {"Code": "403", "Message": "Forbidden"}}, "HeadBucket")


def test_constructor_does_not_touch_s3(live_storage_settings: None) -> None:
    """Constructing the service creates no boto3 client."""
    with patch.object(ss_module.boto3, "client") as client_factory:
        service = StorageService()

    client_factory.assert_not_called()
    assert service.s3_client is None
    assert service.s3_client_presigner is None
    assert service.bucket_name == BUCKET


def test_first_use_connects_with_session_token_and_caches_client(live_storage_settings: None) -> None:
    """First use builds the client with configured credentials and probes the bucket."""
    fake_client = MagicMock()
    with patch.object(ss_module.boto3, "client", return_value=fake_client) as client_factory:
        service = StorageService()
        service._ensure_client()
        service._ensure_client()

    assert client_factory.call_count == 2
    kwargs = client_factory.call_args_list[0].kwargs
    assert kwargs["aws_access_key_id"] == "AKIATEST"
    assert kwargs["aws_secret_access_key"] == "secret"
    assert kwargs["aws_session_token"] == "session-token"
    assert kwargs["region_name"] == "us-west-2"
    fake_client.head_bucket.assert_called_once_with(Bucket=BUCKET)
    assert service.s3_client is fake_client
    assert service.s3_client_presigner is fake_client


def test_empty_credentials_fall_back_to_default_chain(
    live_storage_settings: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Blank credential settings pass None so boto3 uses the default provider chain."""
    monkeypatch.setattr(settings, "AWS_ACCESS_KEY_ID", "")
    monkeypatch.setattr(settings, "AWS_SECRET_ACCESS_KEY", "")
    monkeypatch.setattr(settings, "AWS_SESSION_TOKEN", "")
    with patch.object(ss_module.boto3, "client", return_value=MagicMock()) as client_factory:
        StorageService()._ensure_client()

    kwargs = client_factory.call_args_list[0].kwargs
    assert kwargs["aws_access_key_id"] is None
    assert kwargs["aws_secret_access_key"] is None
    assert kwargs["aws_session_token"] is None


def test_probe_failure_is_deferred_until_storage_is_used(
    live_storage_settings: None, caplog: pytest.LogCaptureFixture
) -> None:
    """A denied bucket probe surfaces on each storage call, not at construction."""
    fake_client = MagicMock()
    fake_client.head_bucket.side_effect = forbidden()
    with patch.object(ss_module.boto3, "client", return_value=fake_client):
        service = StorageService()
        assert service.s3_client is None

        with caplog.at_level(logging.ERROR, logger="app.api.services.storage_service"):
            with pytest.raises(HTTPException) as upload_error:
                service.upload_image(MagicMock(), entity_type="user", user_id=uuid4())
            with pytest.raises(HTTPException) as presign_error:
                service.get_presigned_url("user/abc/x.jpg")
            assert service.delete_image("user/abc/x.jpg") is False
            assert service.object_exists("user/abc/x.jpg") is False

    assert upload_error.value.status_code == 500
    assert f"Access denied to S3 bucket '{BUCKET}'" in upload_error.value.detail
    assert presign_error.value.status_code == 500
    assert "Access denied to S3 bucket" in caplog.text
    assert service.s3_client is None
    assert service.s3_client_presigner is None


def test_missing_bucket_probe_reports_not_found(live_storage_settings: None) -> None:
    """A 404 probe reports the bucket as not found."""
    fake_client = MagicMock()
    fake_client.head_bucket.side_effect = ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadBucket")
    with patch.object(ss_module.boto3, "client", return_value=fake_client):
        with pytest.raises(HTTPException) as exc_info:
            StorageService().count_bucket_objects()

    assert f"S3 bucket '{BUCKET}' not found" in exc_info.value.detail


def test_injected_client_is_not_replaced(live_storage_settings: None) -> None:
    """A client injected by a test is left alone."""
    injected = MagicMock()
    service = StorageService()
    service.s3_client = injected
    service.s3_client_presigner = injected
    with patch.object(ss_module.boto3, "client") as client_factory:
        service._ensure_client()

    client_factory.assert_not_called()
    assert service.s3_client is injected


def test_unconfigured_bucket_never_connects(live_storage_settings: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """With no bucket configured the service reports 503 without connecting."""
    monkeypatch.setattr(settings, "USER_IMAGES_BUCKET", "")
    with patch.object(ss_module.boto3, "client") as client_factory:
        service = StorageService()
        with pytest.raises(HTTPException) as exc_info:
            service.upload_image(MagicMock(), entity_type="user", user_id=uuid4())

    client_factory.assert_not_called()
    assert exc_info.value.status_code == 503


def test_test_environment_never_connects(live_storage_settings: None) -> None:
    """In the test environment the service never builds a client."""
    with (
        patch.object(ss_module, "_is_test_environment", return_value=True),
        patch.object(ss_module.boto3, "client") as client_factory,
    ):
        service = StorageService()
        service._ensure_client()

    client_factory.assert_not_called()
    assert service.s3_client is None


@mock_aws
def test_lazy_connect_against_moto_bucket(live_storage_settings: None) -> None:
    """End to end lazy connect and object operations against a moto bucket."""
    s3 = boto3.client("s3", region_name="us-west-2")
    s3.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "us-west-2"})
    s3.put_object(Bucket=BUCKET, Key="user/abc/x.jpg", Body=b"x")

    service = StorageService()
    assert service.s3_client is None

    assert service.object_exists("user/abc/x.jpg") is True
    assert service.object_exists("user/abc/missing.jpg") is False
    assert service.s3_client is not None
    assert service.delete_image("user/abc/x.jpg") is True
    assert service.object_exists("user/abc/x.jpg") is False
