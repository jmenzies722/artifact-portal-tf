"""GET /files?prefix=... -> objects the caller may see (max 1000)."""

import functools
import os


from shared import aws, http, permissions

MAX_ITEMS = 1000


@functools.cache
def _s3():
    return aws.s3_client()


def _prefixes_to_list(allowed, requested):
    """A prefix inside an allowed one is used as-is; a broader one is narrowed,
    e.g. "partners/" for partner_a becomes ["partners/partner_a/"]."""
    if requested and any(requested.startswith(p) for p in allowed):
        return [requested]
    wanted = [p for p in allowed if p.startswith(requested or "")]
    # Drop prefixes nested in another (partners/partner_a/ under partners/) so nothing lists twice.
    return [p for p in wanted if not any(p != q and p.startswith(q) for q in wanted)]


def _list(prefix, limit):
    items, token = [], None
    while len(items) < limit:
        kwargs = {"Bucket": os.environ["BUCKET_NAME"], "Prefix": prefix, "MaxKeys": limit - len(items)}
        if token:
            kwargs["ContinuationToken"] = token
        page = _s3().list_objects_v2(**kwargs)
        for obj in page.get("Contents", []):
            items.append({
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat(),
            })
        token = page.get("NextContinuationToken")
        if not page.get("IsTruncated") or not token:
            return items, False
    return items, True


def handler(event, context):
    requested = http.query_param(event, "prefix")
    claims = http.claims_from_event(event)
    if not claims:
        http.log_request("list", requested, None, "unauthenticated", event=event)
        return http.error(401, "unauthorized")
    principal = permissions.principal_from_claims(claims)

    if requested and not permissions.is_safe_key(requested):
        http.log_request("list", requested, principal, "bad_request", event=event)
        return http.error(400, "invalid prefix")

    prefixes = _prefixes_to_list(permissions.allowed_prefixes(principal, "list"), requested)
    if not prefixes:
        http.log_request("list", requested, principal, "deny", event=event)
        return http.error(403, "forbidden")

    items, truncated = [], False
    for prefix in prefixes:
        found, truncated = _list(prefix, MAX_ITEMS - len(items))
        items.extend(found)
        if len(items) >= MAX_ITEMS:
            truncated = True
            break
    http.log_request("list", requested, principal, "allow", event=event)
    return http.response(200, {"prefixes": prefixes, "items": items, "truncated": truncated})
