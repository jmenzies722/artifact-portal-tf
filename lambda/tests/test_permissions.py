import pytest

from shared.permissions import allowed_prefixes, is_allowed, is_safe_key


def user(*groups):
    return {"kind": "user", "groups": set(groups), "scopes": set()}


def machine(*scopes):
    return {"kind": "machine", "groups": set(), "scopes": set(scopes)}


ALL = ["develop/", "partners/", "public/"]
STAFF = ["partners/", "public/"]

# One row per cell of the RBAC table: (principal, action, expected prefixes).
TABLE = [
    *[(user("developers"), a, ALL) for a in ("list", "read", "write", "delete")],
    *[(user("operations"), a, STAFF) for a in ("list", "read", "write", "delete")],
    (user("testers"), "list", STAFF),
    (user("testers"), "read", STAFF),
    (user("testers"), "write", []),
    (user("testers"), "delete", []),
    (user("partner_a"), "list", ["partners/partner_a/", "public/"]),
    (user("partner_a"), "read", ["partners/partner_a/", "public/"]),
    (user("partner_a"), "write", ["partners/partner_a/"]),
    (user("partner_a"), "delete", []),
    (user("partner_b"), "list", ["partners/partner_b/", "public/"]),
    (user("partner_b"), "read", ["partners/partner_b/", "public/"]),
    (user("partner_b"), "write", ["partners/partner_b/"]),
    (user("partner_b"), "delete", []),
    (machine("artifacts/write"), "list", []),
    (machine("artifacts/write"), "read", []),
    (machine("artifacts/write"), "write", ["develop/", "public/"]),
    (machine("artifacts/write"), "delete", []),
    (machine("artifacts/read"), "list", ["develop/", "public/"]),
    (machine("artifacts/read"), "read", ["develop/", "public/"]),
    (machine("artifacts/read"), "write", []),
    (machine("artifacts/read"), "delete", []),
]


@pytest.mark.parametrize("principal,action,expected", TABLE)
def test_rbac_table(principal, action, expected):
    assert allowed_prefixes(principal, action) == expected


def test_partners_cannot_see_each_other():
    assert is_allowed(user("partner_a"), "read", "partners/partner_a/build.zip")
    assert not is_allowed(user("partner_a"), "read", "partners/partner_b/build.zip")
    assert not is_allowed(user("partner_b"), "write", "partners/partner_a/x")
    assert not is_allowed(user("partner_a"), "read", "develop/x")


def test_union_across_groups():
    p = user("testers", "partner_a")
    assert allowed_prefixes(p, "list") == ["partners/", "partners/partner_a/", "public/"]
    assert allowed_prefixes(p, "write") == ["partners/partner_a/"]
    assert allowed_prefixes(user("developers", "partner_b"), "delete") == ALL


def test_unknown_group_grants_nothing():
    for action in ("list", "read", "write", "delete"):
        assert allowed_prefixes(user("admins"), action) == []
        assert not is_allowed(user("admins"), action, "public/a.txt")


def test_groups_and_scopes_do_not_cross_over():
    # A user token carrying a machine scope gets nothing from it, and vice versa.
    assert allowed_prefixes({"kind": "user", "groups": set(), "scopes": {"artifacts/write"}}, "write") == []
    assert allowed_prefixes({"kind": "machine", "groups": {"developers"}, "scopes": set()}, "read") == []


def test_unknown_action():
    assert allowed_prefixes(user("developers"), "admin") == []


@pytest.mark.parametrize("key", [
    "", None, "/public/a.txt", "public/../develop/secret", "public/..", "..", "partners/partner_a/../partner_b/x",
])
def test_bad_keys_rejected(key):
    assert not is_safe_key(key)
    assert not is_allowed(user("developers"), "read", key)


def test_traversal_cannot_escape_partner_folder():
    assert not is_allowed(user("partner_a"), "write", "partners/partner_a/../partner_b/x")


def test_prefix_must_match_whole_segment():
    assert not is_allowed(user("developers"), "read", "publicity/a.txt")
    assert not is_allowed(user("developers"), "read", "public")
