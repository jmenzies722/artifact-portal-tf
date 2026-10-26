"""Durable audit trail in DynamoDB: one item per allowed upload/download/delete.

http.log_request already logs every decision (deny included) to CloudWatch;
this table keeps the allowed ones queryable for 90 days, by day or by key.
"""

import functools
import json
import os
import time
import uuid
from datetime import datetime, timezone

from shared import aws, http

RETENTION_DAYS = 90

# Only allowed requests are recorded, so the outcome is what the API did,
# not the decision. A presigned URL doesn't prove the transfer happened.
OUTCOMES = {"upload": "url_issued", "download": "url_issued", "delete": "deleted"}


@functools.cache
def _dynamodb():
    return aws.dynamodb_client()


def actor_of(claims, principal):
    """Email for people when the token has it, else username; client_id for machines."""
    claims = claims or {}
    if principal.get("kind") == "machine":
        return claims.get("client_id") or claims.get("sub")
    return (claims.get("email") or claims.get("username")
            or claims.get("cognito:username") or claims.get("sub"))


def build_item(event, principal, action, key, now=None):
    now = now or datetime.now(timezone.utc)
    ctx = (event or {}).get("requestContext") or {}
    claims = http.claims_from_event(event) or {}
    ts = now.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    attrs = {
        "pk": f"DAY#{now:%Y-%m-%d}",
        # The request id makes sk unique even when two requests share a millisecond.
        "sk": f"{ts}#{ctx.get('requestId') or uuid.uuid4().hex}",
        "action": action,
        "key": key,
        "actor": actor_of(claims, principal),
        "actor_kind": principal.get("kind"),
        "groups": sorted(principal.get("groups", ())),
        "outcome": OUTCOMES.get(action, "allowed"),
        "source_ip": (ctx.get("http") or {}).get("sourceIp"),
        "expires_at": int(now.timestamp()) + RETENTION_DAYS * 86400,
    }
    item = {}
    for name, value in attrs.items():
        if value is None:
            continue  # DynamoDB has no null-for-free; just leave the attribute out
        if isinstance(value, int):
            item[name] = {"N": str(value)}
        elif isinstance(value, list):
            item[name] = {"L": [{"S": v} for v in value]}
        else:
            item[name] = {"S": str(value)}
    return item


def record(event, principal, action, key):
    """Write one audit item. Never raises.

    Called only after the request succeeded. If the audit write fails, the
    user still gets their URL/delete: the action already happened (or is
    authorised), and refusing it wouldn't undo that. The CloudWatch line from
    http.log_request is the fallback record, and this error log marks the gap.
    """
    started = time.monotonic()
    try:
        _dynamodb().put_item(
            TableName=os.environ["AUDIT_TABLE"],
            Item=build_item(event, principal, action, key),
        )
    except Exception as e:  # noqa: BLE001 - deliberately broad, see docstring
        print(json.dumps({
            "level": "ERROR",
            "msg": "audit_write_failed",
            "action": action,
            "key": key,
            "error": type(e).__name__,
            "elapsed_ms": round((time.monotonic() - started) * 1000),
        }))
