"""GET /download?key=... -> presigned GET URL (404 if the object is missing)."""

import functools
import os


from shared import audit, aws, http, permissions

EXPIRES_IN = 300
_MISSING = {"404", "NoSuchKey", "NotFound"}


@functools.cache
def _s3():
    return aws.s3_client()


def handler(event, context):
    key = http.query_param(event, "key")
    claims = http.claims_from_event(event)
    if not claims:
        http.log_request("read", key, None, "unauthenticated", event=event)
        return http.error(401, "unauthorized")
    principal = permissions.principal_from_claims(claims)

    if not permissions.is_safe_key(key):
        http.log_request("read", key, principal, "bad_request", event=event)
        return http.error(400, "invalid key")

    # Authorise before touching S3 so a 404 can't reveal what exists elsewhere.
    if not permissions.is_allowed(principal, "read", key):
        http.log_request("read", key, principal, "deny", event=event)
        return http.error(403, "forbidden")

    s3 = _s3()
    bucket = os.environ["BUCKET_NAME"]
    try:
        s3.head_object(Bucket=bucket, Key=key)
    except s3.exceptions.ClientError as e:
        if e.response.get("Error", {}).get("Code") in _MISSING:
            http.log_request("read", key, principal, "not_found", event=event)
            return http.error(404, "not found")
        raise

    url = s3.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=EXPIRES_IN
    )
    http.log_request("read", key, principal, "allow", event=event)
    audit.record(event, principal, "download", key)
    return http.response(200, {"url": url, "key": key, "expires_in": EXPIRES_IN})
