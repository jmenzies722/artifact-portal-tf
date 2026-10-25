import pytest

from shared.permissions import principal_from_claims


@pytest.mark.parametrize("raw", [
    ["developers", "testers"],
    "[developers testers]",
    "developers,testers",
    "[developers, testers]",
    " developers testers ",
])
def test_groups_in_every_encoding(raw):
    p = principal_from_claims({"token_use": "id", "cognito:groups": raw})
    assert p == {"kind": "user", "groups": {"developers", "testers"}, "scopes": set()}


def test_single_group_string():
    assert principal_from_claims({"cognito:groups": "[operations]"})["groups"] == {"operations"}


def test_empty_groups():
    for raw in ("[]", "", None, []):
        assert principal_from_claims({"token_use": "id", "cognito:groups": raw})["groups"] == set()


def test_machine_token():
    p = principal_from_claims({
        "token_use": "access", "client_id": "abc", "scope": "artifacts/write artifacts/read",
    })
    assert p == {"kind": "machine", "groups": set(), "scopes": {"artifacts/write", "artifacts/read"}}


def test_user_access_token_is_not_machine():
    p = principal_from_claims({
        "token_use": "access", "client_id": "web", "username": "alice",
        "scope": "openid email",
    })
    assert p["kind"] == "user"
    assert p["scopes"] == {"openid", "email"}


def test_groups_claim_means_user_even_without_username():
    p = principal_from_claims({"token_use": "access", "client_id": "web", "cognito:groups": "[testers]"})
    assert p["kind"] == "user"
    assert p["groups"] == {"testers"}


def test_none_claims():
    assert principal_from_claims(None) == {"kind": "user", "groups": set(), "scopes": set()}
