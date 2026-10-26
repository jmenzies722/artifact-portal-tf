import datetime as dt
import json

import pytest

from helpers import FakeClientError, call, event, load_handler, machine_claims, user_claims
from shared import audit, permissions

upload = load_handler("upload_url")
download = load_handler("download_url")
delete = load_handler("delete_file")

NOW = dt.datetime(2026, 10, 26, 4, 11, 0, 123000, tzinfo=dt.timezone.utc)


def with_context(ev, request_id="req-1", ip="203.0.113.7"):
    ev["requestContext"].update({"requestId": request_id, "http": {"sourceIp": ip}})
    return ev


def put_items(audit_db):
    return [c.kwargs["Item"] for c in audit_db.put_item.call_args_list]


# ---- build_item / record ------------------------------------------------------


def test_build_item_shape_for_user():
    claims = {**user_claims("partner_a", "testers"), "email": "a@example.com"}
    ev = with_context(event(claims))
    principal = permissions.principal_from_claims(claims)
    item = audit.build_item(ev, principal, "upload", "partners/partner_a/x.zip", now=NOW)
    assert item == {
        "pk": {"S": "DAY#2026-10-26"},
        "sk": {"S": "2026-10-26T04:11:00.123Z#req-1"},
        "action": {"S": "upload"},
        "key": {"S": "partners/partner_a/x.zip"},
        "actor": {"S": "a@example.com"},
        "actor_kind": {"S": "user"},
        "groups": {"L": [{"S": "partner_a"}, {"S": "testers"}]},
        "outcome": {"S": "url_issued"},
        "source_ip": {"S": "203.0.113.7"},
        "expires_at": {"N": str(int(NOW.timestamp()) + 90 * 86400)},
    }


def test_build_item_machine_uses_client_id_and_skips_missing_ip():
    claims = machine_claims("artifacts/read")
    item = audit.build_item(event(claims), permissions.principal_from_claims(claims), "download", "public/a", now=NOW)
    assert item["actor"] == {"S": "ci-client"}
    assert item["actor_kind"] == {"S": "machine"}
    assert item["groups"] == {"L": []}
    assert "source_ip" not in item
    # No request id (not from API Gateway): sk still unique via a random suffix.
    assert item["sk"]["S"].startswith("2026-10-26T04:11:00.123Z#") and len(item["sk"]["S"]) > 26


def test_user_without_email_falls_back_to_username():
    claims = {"token_use": "access", "client_id": "web", "username": "jdoe", "cognito:groups": ["developers"]}
    assert audit.actor_of(claims, permissions.principal_from_claims(claims)) == "jdoe"


def test_record_writes_to_the_configured_table(audit_db):
    claims = user_claims("developers")
    audit.record(event(claims), permissions.principal_from_claims(claims), "delete", "develop/x")
    audit_db.put_item.assert_called_once()
    kwargs = audit_db.put_item.call_args.kwargs
    assert kwargs["TableName"] == "test-audit"
    assert kwargs["Item"]["outcome"] == {"S": "deleted"}


@pytest.mark.parametrize("failure", [FakeClientError("ProvisionedThroughputExceededException"), TimeoutError()])
def test_record_swallows_and_logs_failures(audit_db, capsys, failure):
    audit_db.put_item.side_effect = failure
    claims = user_claims("developers")
    audit.record(event(claims), permissions.principal_from_claims(claims), "delete", "develop/x")  # no raise
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["msg"] == "audit_write_failed" and line["key"] == "develop/x"


def test_record_survives_missing_table_env(audit_db, monkeypatch):
    monkeypatch.delenv("AUDIT_TABLE")
    claims = user_claims("developers")
    audit.record(event(claims), permissions.principal_from_claims(claims), "delete", "develop/x")
    audit_db.put_item.assert_not_called()


# ---- handlers: allowed requests write, everything else doesn't ------------------


def test_allowed_upload_download_delete_are_recorded(s3, audit_db):
    s3.generate_presigned_url.return_value = "https://signed"
    dev = user_claims("developers")
    assert call(upload, s3, with_context(event(dev, body=json.dumps({"key": "develop/a.zip"}))))[0] == 200
    assert call(download, s3, with_context(event(dev, {"key": "develop/a.zip"})))[0] == 200
    assert call(delete, s3, with_context(event(dev, {"key": "develop/a.zip"})))[0] == 200
    items = put_items(audit_db)
    assert [(i["action"]["S"], i["key"]["S"], i["outcome"]["S"]) for i in items] == [
        ("upload", "develop/a.zip", "url_issued"),
        ("download", "develop/a.zip", "url_issued"),
        ("delete", "develop/a.zip", "deleted"),
    ]


def test_audit_failure_never_fails_the_request(s3, audit_db):
    audit_db.put_item.side_effect = FakeClientError("AccessDeniedException")
    status, body = call(delete, s3, event(user_claims("developers"), {"key": "develop/x"}))
    assert (status, body) == (200, {"deleted": "develop/x"})
    s3.delete_object.assert_called_once()


def test_denied_and_failed_requests_write_nothing(s3, audit_db):
    s3.head_object.side_effect = FakeClientError("404")
    partner = user_claims("partner_a")
    cases = [
        (upload, event(partner, body=json.dumps({"key": "develop/a.zip"})), 403),
        (upload, event(partner, body="not json"), 400),
        (upload, event(body=json.dumps({"key": "public/a"})), 401),
        (download, event(partner, {"key": "partners/partner_b/x"}), 403),
        (download, event(partner, {"key": "public/missing"}), 404),
        (delete, event(partner, {"key": "partners/partner_a/x"}), 403),
        (delete, event(machine_claims("artifacts/write"), {"key": "develop/x"}), 403),
        (delete, event(user_claims("developers"), {"key": "../x"}), 400),
    ]
    for mod, ev, expected in cases:
        assert call(mod, s3, ev)[0] == expected, (mod.__name__, ev)
    audit_db.put_item.assert_not_called()
