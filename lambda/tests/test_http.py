import base64
import json

from shared import http


def test_response_is_json():
    r = http.response(201, {"a": 1})
    assert r["statusCode"] == 201
    assert r["headers"]["Content-Type"] == "application/json"
    assert json.loads(r["body"]) == {"a": 1}


def test_error():
    assert json.loads(http.error(403, "nope")["body"]) == {"error": "nope"}


def test_claims_from_event():
    claims = {"sub": "x"}
    ev = {"requestContext": {"authorizer": {"jwt": {"claims": claims}}}}
    assert http.claims_from_event(ev) == claims
    assert http.claims_from_event({"requestContext": {}}) is None
    assert http.claims_from_event({}) is None
    assert http.claims_from_event({"requestContext": {"authorizer": {"jwt": {"claims": {}}}}}) is None


def test_json_body():
    assert http.json_body({"body": '{"k": 1}'}) == {"k": 1}
    encoded = base64.b64encode(b'{"k": 2}').decode()
    assert http.json_body({"body": encoded, "isBase64Encoded": True}) == {"k": 2}
    assert http.json_body({"body": "not json"}) is None
    assert http.json_body({"body": "[1, 2]"}) is None
    assert http.json_body({}) is None


def test_log_request_has_no_token_fields(capsys):
    http.log_request("read", "public/a", {"kind": "user", "groups": {"b", "a"}, "scopes": set()}, "allow")
    line = json.loads(capsys.readouterr().out)
    assert set(line) == {"ts", "request_id", "sub", "action", "key", "kind",
                         "groups", "scopes", "decision"}  # exact field set: nothing extra leaks
    assert {k: line[k] for k in ("action", "key", "kind", "groups", "scopes", "decision")} == {
        "action": "read", "key": "public/a", "kind": "user",
        "groups": ["a", "b"], "scopes": [], "decision": "allow"}
    assert line["sub"] is None and line["request_id"] is None  # no event passed


def test_log_request_is_an_audit_record(capsys):
    event = {"requestContext": {"requestId": "req-123", "authorizer": {"jwt": {"claims": {
        "sub": "user-42", "cognito:groups": "[partner_a]", "username": "u"}}}}}
    http.log_request("read", "partners/partner_a/a.zip",
                     {"kind": "user", "groups": {"partner_a"}, "scopes": set()}, "allow", event=event)
    line = json.loads(capsys.readouterr().out)
    assert line["sub"] == "user-42"
    assert line["request_id"] == "req-123"
    assert line["ts"].endswith("+00:00")
    assert "token" not in json.dumps(line).lower()


def test_log_request_uses_client_id_for_machines(capsys):
    event = {"requestContext": {"requestId": "r", "authorizer": {"jwt": {"claims": {"client_id": "ci-abc", "scope": "artifacts/write"}}}}}
    http.log_request("write", "develop/b.zip", {"kind": "machine", "groups": set(), "scopes": {"artifacts/write"}}, "allow", event=event)
    assert json.loads(capsys.readouterr().out)["sub"] == "ci-abc"
