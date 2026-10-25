"""HTTP API (payload v2) helpers: responses, claims, input, audit log."""

import base64
import json
from datetime import datetime, timezone


def response(status, body_dict):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body_dict, default=str),
    }


def error(status, msg):
    return response(status, {"error": msg})


def claims_from_event(event):
    try:
        claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
    except (KeyError, TypeError):
        return None
    return claims or None


def query_param(event, name):
    return (event.get("queryStringParameters") or {}).get(name)


def json_body(event):
    """Parsed JSON object body, or None if missing/invalid."""
    raw = event.get("body")
    if not raw:
        return None
    try:
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw).decode("utf-8")
        body = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None
    return body if isinstance(body, dict) else None


def log_request(action, key, principal, decision, event=None):
    """One JSON audit line per request: who, what, when, decision.

    Never logs tokens or raw claims. `sub` is the user's (or CI client's)
    stable ID; `request_id` matches the API Gateway access log.
    """
    principal = principal or {}
    claims = claims_from_event(event) if event else None
    ctx = (event or {}).get("requestContext") or {}
    print(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "request_id": ctx.get("requestId"),
        "sub": (claims or {}).get("sub") or (claims or {}).get("client_id"),
        "action": action,
        "key": key,
        "kind": principal.get("kind"),
        "groups": sorted(principal.get("groups", ())),
        "scopes": sorted(principal.get("scopes", ())),
        "decision": decision,
    }))
