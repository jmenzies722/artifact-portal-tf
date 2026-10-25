"""Who can do what, where. Pure functions: no AWS calls, fully unit-testable."""

# People: group -> action -> allowed key prefixes
GROUP_RULES = {
    "developers": {a: ["public/", "partners/", "develop/"] for a in ("list", "read", "write", "delete")},
    "operations": {a: ["public/", "partners/"] for a in ("list", "read", "write", "delete")},
    "testers": {"list": ["public/", "partners/"], "read": ["public/", "partners/"]},
    "partner_a": {
        "list": ["public/", "partners/partner_a/"],
        "read": ["public/", "partners/partner_a/"],
        "write": ["partners/partner_a/"],
    },
    "partner_b": {
        "list": ["public/", "partners/partner_b/"],
        "read": ["public/", "partners/partner_b/"],
        "write": ["partners/partner_b/"],
    },
}

# Machines: OAuth scope -> action -> allowed key prefixes
SCOPE_RULES = {
    "artifacts/write": {"write": ["develop/", "public/"]},
    "artifacts/read": {"list": ["public/", "develop/"], "read": ["public/", "develop/"]},
}


def _parse_groups(raw):
    """HTTP API may pass groups as a list, '[a b]' or 'a,b'."""
    if not raw:
        return set()
    if isinstance(raw, (list, tuple, set)):
        return {str(g) for g in raw}
    text = str(raw).strip().strip("[]")
    return {g for g in text.replace(",", " ").split() if g}


def principal_from_claims(claims):
    claims = claims or {}
    groups = _parse_groups(claims.get("cognito:groups"))
    scopes = set(str(claims.get("scope", "")).split())
    is_machine = not groups and "client_id" in claims and "username" not in claims
    return {"kind": "machine" if is_machine else "user", "groups": groups, "scopes": scopes}


def allowed_prefixes(principal, action):
    rules = SCOPE_RULES if principal["kind"] == "machine" else GROUP_RULES
    names = principal["scopes"] if principal["kind"] == "machine" else principal["groups"]
    prefixes = set()
    for name in names:
        prefixes.update(rules.get(name, {}).get(action, []))  # unknown names grant nothing
    return sorted(prefixes)


def is_safe_key(key):
    return bool(key) and not key.startswith("/") and ".." not in key


def is_allowed(principal, action, key):
    if not is_safe_key(key):
        return False
    return any(key.startswith(p) for p in allowed_prefixes(principal, action))
