"""POST /upload {"key", "content_type"} -> presigned SSE-KMS PUT URL.

Published artifacts are immutable: the URL only works for a key that
doesn't exist yet (S3 conditional write). A new build needs a new name.
"""

import functools
import os


from shared import aws, http, permissions

EXPIRES_IN = 300
DEFAULT_CONTENT_TYPE = "application/octet-stream"


@functools.cache
def _s3():
    return aws.s3_client()


def handler(event, context):
    body = http.json_body(event)
    key = body.get("key") if body else None
    claims = http.claims_from_event(event)
    if not claims:
        http.log_request("write", key, None, "unauthenticated", event=event)
        return http.error(401, "unauthorized")
    principal = permissions.principal_from_claims(claims)

    content_type = (body or {}).get("content_type", DEFAULT_CONTENT_TYPE)
    # The body is client JSON, so check types before is_safe_key calls str methods.
    valid = isinstance(key, str) and permissions.is_safe_key(key)
    if not valid or not isinstance(content_type, str) or not content_type:
        http.log_request("write", key, principal, "bad_request", event=event)
        return http.error(400, "body must be JSON with a valid 'key' and string 'content_type'")

    if not permissions.is_allowed(principal, "write", key):
        http.log_request("write", key, principal, "deny", event=event)
        return http.error(403, "forbidden")

    kms_key_arn = os.environ["KMS_KEY_ARN"]
    url = _s3().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": os.environ["BUCKET_NAME"],
            "Key": key,
            "ContentType": content_type,
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": kms_key_arn,
            # Immutable artifacts: S3 refuses the PUT (412) if the key already exists.
            "IfNoneMatch": "*",
        },
        ExpiresIn=EXPIRES_IN,
        HttpMethod="PUT",
    )
    http.log_request("write", key, principal, "allow", event=event)
    return http.response(200, {
        "url": url,
        "key": key,
        "expires_in": EXPIRES_IN,
        # Signed into the URL: the PUT fails unless the client sends these exactly.
        "required_headers": {
            "Content-Type": content_type,
            "x-amz-server-side-encryption": "aws:kms",
            "x-amz-server-side-encryption-aws-kms-key-id": kms_key_arn,
            "If-None-Match": "*",
        },
    })
