from helpers import call, event, load_handler, machine_claims, user_claims

mod = load_handler("delete_file")


def test_401_without_claims(s3):
    assert call(mod, s3, event(query={"key": "public/a"}))[0] == 401


def test_developer_deletes(s3):
    status, body = call(mod, s3, event(user_claims("developers"), {"key": "develop/old.zip"}))
    assert (status, body) == (200, {"deleted": "develop/old.zip"})
    s3.delete_object.assert_called_once_with(Bucket="test-bucket", Key="develop/old.zip")


def test_operations_cannot_delete_develop(s3):
    assert call(mod, s3, event(user_claims("operations"), {"key": "develop/x"}))[0] == 403


def test_partners_testers_and_machines_cannot_delete(s3):
    cases = [
        (user_claims("partner_a"), "partners/partner_a/x"),
        (user_claims("testers"), "public/x"),
        (machine_claims("artifacts/write", "artifacts/read"), "develop/x"),
    ]
    for claims, key in cases:
        assert call(mod, s3, event(claims, {"key": key}))[0] == 403, claims
    s3.delete_object.assert_not_called()


def test_400_bad_key(s3):
    assert call(mod, s3, event(user_claims("developers"), {"key": "develop/../public/x"}))[0] == 400
