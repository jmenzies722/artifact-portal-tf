import pytest

from helpers import FakeClientError, call, event, load_handler, machine_claims, user_claims

mod = load_handler("download_url")


def test_401_without_claims(s3):
    assert call(mod, s3, event(query={"key": "public/a"}))[0] == 401


def test_presigns_get(s3):
    s3.generate_presigned_url.return_value = "https://signed-get"
    status, body = call(mod, s3, event(user_claims("testers"), {"key": "partners/partner_a/x"}))
    assert status == 200
    assert body == {"url": "https://signed-get", "key": "partners/partner_a/x", "expires_in": 300}
    s3.head_object.assert_called_once_with(Bucket="test-bucket", Key="partners/partner_a/x")
    s3.generate_presigned_url.assert_called_once_with(
        "get_object", Params={"Bucket": "test-bucket", "Key": "partners/partner_a/x"}, ExpiresIn=300
    )


def test_404_when_missing(s3):
    s3.head_object.side_effect = FakeClientError("404")
    status, _ = call(mod, s3, event(machine_claims("artifacts/read"), {"key": "develop/gone"}))
    assert status == 404
    s3.generate_presigned_url.assert_not_called()


def test_other_s3_errors_propagate(s3):
    s3.head_object.side_effect = FakeClientError("403")
    with pytest.raises(FakeClientError):
        call(mod, s3, event(user_claims("developers"), {"key": "develop/x"}))


def test_403_checked_before_existence(s3):
    status, _ = call(mod, s3, event(user_claims("partner_a"), {"key": "partners/partner_b/x"}))
    assert status == 403
    s3.head_object.assert_not_called()


def test_400_bad_key(s3):
    for q in (None, {}, {"key": ""}, {"key": "public/../develop/x"}, {"key": "/public/a"}):
        assert call(mod, s3, event(user_claims("developers"), q))[0] == 400, q
