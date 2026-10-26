"""GET /activity?days=1..7 -> recent audit items the caller may see (max 100, newest first).

RBAC: an item is returned only if the caller may `list` its key, so the feed
never reveals a file the caller couldn't find in GET /files.
"""

import functools
import os
from datetime import datetime, timedelta, timezone

from shared import aws, http, permissions

MAX_ITEMS = 100
MAX_DAYS = 7

# Never read source_ip or groups: other people's IPs aren't the caller's business.
# "key" and "action" are DynamoDB reserved words, hence the #names.
PROJECTION = "sk, #k, #a, actor, actor_kind, outcome"
NAMES = {"#k": "key", "#a": "action"}


@functools.cache
def _dynamodb():
    return aws.dynamodb_client()


def _parse_days(raw):
    if raw is None or raw == "":
        return 1
    try:
        days = int(raw)
    except ValueError:
        return None
    return days if 1 <= days <= MAX_DAYS else None


def _partitions(now, days):
    """days=N means the last N*24h, so it spans N+1 day partitions (newest first)
    and the oldest is cut at the exact start time via the sort key."""
    start = now - timedelta(days=days)
    pks, day = [], now.date()
    while day >= start.date():
        pks.append(f"DAY#{day:%Y-%m-%d}")
        day -= timedelta(days=1)
    return pks, start.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _plain(item):
    return {name: value.get("S", value.get("N")) for name, value in item.items()}


def _visible(principal, pks, since):
    """Walk partitions newest-first, filtering as we go, until MAX_ITEMS are found."""
    items, db = [], _dynamodb()
    for pk in pks:
        start_key = None
        while True:
            kwargs = {
                "TableName": os.environ["AUDIT_TABLE"],
                "KeyConditionExpression": "pk = :pk AND sk >= :since",
                "ExpressionAttributeValues": {":pk": {"S": pk}, ":since": {"S": since}},
                "ExpressionAttributeNames": NAMES,
                "ProjectionExpression": PROJECTION,
                "ScanIndexForward": False,  # newest first
            }
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            page = db.query(**kwargs)
            for raw in page.get("Items", []):
                row = _plain(raw)
                if not permissions.is_allowed(principal, "list", row.get("key")):
                    continue
                items.append({
                    "ts": row["sk"].split("#", 1)[0],
                    "action": row.get("action"),
                    "key": row["key"],
                    "actor": row.get("actor"),
                    "actor_kind": row.get("actor_kind"),
                    "outcome": row.get("outcome"),
                })
                if len(items) >= MAX_ITEMS:
                    return items, True
            start_key = page.get("LastEvaluatedKey")
            if not start_key:
                break
    return items, False


def handler(event, context):
    claims = http.claims_from_event(event)
    if not claims:
        http.log_request("activity", None, None, "unauthenticated", event=event)
        return http.error(401, "unauthorized")
    principal = permissions.principal_from_claims(claims)

    days = _parse_days(http.query_param(event, "days"))
    if days is None:
        http.log_request("activity", None, principal, "bad_request", event=event)
        return http.error(400, f"days must be an integer from 1 to {MAX_DAYS}")

    # Same gate as GET /files: no list prefix (e.g. a write-only CI client), no feed.
    if not permissions.allowed_prefixes(principal, "list"):
        http.log_request("activity", None, principal, "deny", event=event)
        return http.error(403, "forbidden")

    pks, since = _partitions(datetime.now(timezone.utc), days)
    items, truncated = _visible(principal, pks, since)
    http.log_request("activity", None, principal, "allow", event=event)
    return http.response(200, {"days": days, "items": items, "truncated": truncated})
