"""Regression: presigned URLs must be SigV4 (found in the e2e test, 2026-10-25)."""
from unittest import mock

from shared import aws


def test_s3_client_signs_with_sigv4():
    with mock.patch.object(aws.boto3, "client") as client:
        aws.s3_client()
    _, kwargs = client.call_args
    assert kwargs["config"].signature_version == "s3v4"
    assert kwargs["endpoint_url"].startswith("https://s3.")
