"""One place to build the S3 client.

Presigned URLs must use SigV4: S3 rejects conditional writes (If-None-Match,
our immutability guard) signed with legacy SigV2, and boto3 can default to
SigV2 for presigning. The regional endpoint keeps SigV4 URLs valid in us-east-1.
"""
import os

import boto3
from botocore.config import Config


def s3_client():
    region = os.environ.get("AWS_REGION", "us-east-1")
    return boto3.client(
        "s3",
        region_name=region,
        endpoint_url=f"https://s3.{region}.amazonaws.com",
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    )
