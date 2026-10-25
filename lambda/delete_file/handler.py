"""DELETE /files?key=... -> delete the object (a delete marker; bucket is versioned)."""

import functools
import os

import boto3

from shared import http, permissions


@functools.cache
def _s3():
    return boto3.client("s3")


def handler(event, context):
    key = http.query_param(event, "key")
    claims = http.claims_from_event(event)
    if not claims:
        http.log_request("delete", key, None, "unauthenticated", event=event)
        return http.error(401, "unauthorized")
    principal = permissions.principal_from_claims(claims)

    if not permissions.is_safe_key(key):
        http.log_request("delete", key, principal, "bad_request", event=event)
        return http.error(400, "invalid key")

    if not permissions.is_allowed(principal, "delete", key):
        http.log_request("delete", key, principal, "deny", event=event)
        return http.error(403, "forbidden")

    _s3().delete_object(Bucket=os.environ["BUCKET_NAME"], Key=key)
    http.log_request("delete", key, principal, "allow", event=event)
    return http.response(200, {"deleted": key})
