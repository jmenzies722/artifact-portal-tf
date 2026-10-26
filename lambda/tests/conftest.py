import sys
import types
from unittest import mock

import pytest

# boto3 ships in the Lambda runtime; tests never call it, so a stub is enough
# when it isn't installed locally.
try:
    import boto3  # noqa: F401
except ImportError:
    sys.modules["boto3"] = types.SimpleNamespace(client=mock.MagicMock())

from helpers import FakeClientError  # noqa: E402


@pytest.fixture(autouse=True)
def lambda_env(monkeypatch):
    monkeypatch.setenv("BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("KMS_KEY_ARN", "arn:aws:kms:us-east-1:111122223333:key/test")
    monkeypatch.setenv("AUDIT_TABLE", "test-audit")


@pytest.fixture(autouse=True)
def audit_db(monkeypatch):
    """Every handler test gets a mock DynamoDB for audit writes, so none
    reaches AWS; tests that care assert on its put_item calls."""
    from shared import audit

    client = mock.MagicMock()
    monkeypatch.setattr(audit, "_dynamodb", lambda: client)
    return client


@pytest.fixture
def s3():
    client = mock.MagicMock()
    client.exceptions.ClientError = FakeClientError
    return client
