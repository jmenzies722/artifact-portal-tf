import json

from helpers import call, event, load_handler, machine_claims, user_claims

mod = load_handler("upload_url")
KMS = "arn:aws:kms:us-east-1:111122223333:key/test"


def body(**kw):
    return json.dumps(kw)


def test_401_without_claims(s3):
    assert call(mod, s3, event(body=body(key="public/a")))[0] == 401


def test_presigns_put_with_kms(s3):
    s3.generate_presigned_url.return_value = "https://signed"
    ev = event(machine_claims("artifacts/write"), body=body(key="develop/app.zip", content_type="application/zip"))
    status, resp = call(mod, s3, ev)
    assert status == 200
    assert resp["url"] == "https://signed"
    assert resp["expires_in"] == 300
    assert resp["required_headers"] == {
        "Content-Type": "application/zip",
        "x-amz-server-side-encryption": "aws:kms",
        "x-amz-server-side-encryption-aws-kms-key-id": KMS,
        "If-None-Match": "*",
    }
    s3.generate_presigned_url.assert_called_once_with(
        "put_object",
        Params={"Bucket": "test-bucket", "Key": "develop/app.zip", "ContentType": "application/zip",
                "ServerSideEncryption": "aws:kms", "SSEKMSKeyId": KMS,
                "IfNoneMatch": "*"},
        ExpiresIn=300,
        HttpMethod="PUT",
    )


def test_403_for_testers(s3):
    assert call(mod, s3, event(user_claims("testers"), body=body(key="public/a")))[0] == 403
    s3.generate_presigned_url.assert_not_called()


def test_403_partner_writing_other_partner(s3):
    ev = event(user_claims("partner_a"), body=body(key="partners/partner_b/a"))
    assert call(mod, s3, ev)[0] == 403


def test_400_bad_input(s3):
    claims = user_claims("developers")
    for b in (None, "not json", body(), body(key=5), body(key="/public/a"), body(key="public/../x"),
              body(key="public/a", content_type=5)):
        assert call(mod, s3, event(claims, body=b))[0] == 400, b


def test_upload_url_never_allows_overwrite(s3):
    """Supply-chain guard: every presigned PUT is conditional on the key not existing."""
    s3.generate_presigned_url.return_value = "https://signed"
    for claims, key in [(machine_claims("artifacts/write"), "develop/app-1.0.zip"),
                        (user_claims("partner_a"), "partners/partner_a/app-1.0.zip"),
                        (user_claims("developers"), "public/app-1.0.zip")]:
        s3.generate_presigned_url.reset_mock()
        status, resp = call(mod, s3, event(claims, body=body(key=key)))
        assert status == 200
        params = s3.generate_presigned_url.call_args.kwargs["Params"]
        assert params["IfNoneMatch"] == "*"
        assert resp["required_headers"]["If-None-Match"] == "*"
