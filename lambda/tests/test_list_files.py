import datetime as dt

from helpers import call, event, load_handler, machine_claims, user_claims

mod = load_handler("list_files")
WHEN = dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.timezone.utc)


def page(*keys, next_token=None):
    return {
        "Contents": [{"Key": k, "Size": 7, "LastModified": WHEN} for k in keys],
        "IsTruncated": next_token is not None,
        "NextContinuationToken": next_token,
    }


def test_401_without_claims(s3):
    assert call(mod, s3, event())[0] == 401
    s3.list_objects_v2.assert_not_called()


def test_defaults_to_all_allowed_prefixes(s3):
    s3.list_objects_v2.side_effect = [page("partners/partner_a/x.zip"), page("public/r.txt")]
    status, body = call(mod, s3, event(user_claims("partner_a")))
    assert status == 200
    assert body["prefixes"] == ["partners/partner_a/", "public/"]
    assert [c.kwargs["Prefix"] for c in s3.list_objects_v2.call_args_list] == body["prefixes"]
    assert body["items"][0] == {"key": "partners/partner_a/x.zip", "size": 7,
                                "last_modified": "2026-01-02T03:04:05+00:00"}
    assert body["truncated"] is False


def test_requested_prefix_is_narrowed(s3):
    s3.list_objects_v2.return_value = page()
    status, body = call(mod, s3, event(user_claims("partner_b"), {"prefix": "partners/"}))
    assert status == 200
    assert body["prefixes"] == ["partners/partner_b/"]


def test_prefix_inside_allowed_is_used_as_is(s3):
    s3.list_objects_v2.return_value = page()
    _, body = call(mod, s3, event(user_claims("partner_a"), {"prefix": "public/releases/"}))
    assert body["prefixes"] == ["public/releases/"]


def test_overlapping_groups_list_each_object_once(s3):
    s3.list_objects_v2.return_value = page()
    _, body = call(mod, s3, event(user_claims("testers", "partner_a")))
    assert body["prefixes"] == ["partners/", "public/"]


def test_403_outside_allowed_prefixes(s3):
    for prefix in ("develop/", "partners/partner_b/"):
        status, _ = call(mod, s3, event(user_claims("partner_a"), {"prefix": prefix}))
        assert status == 403, prefix
    s3.list_objects_v2.assert_not_called()


def test_403_for_write_only_machine(s3):
    assert call(mod, s3, event(machine_claims("artifacts/write")))[0] == 403


def test_400_on_traversal(s3):
    assert call(mod, s3, event(user_claims("developers"), {"prefix": "public/../develop/"}))[0] == 400


def test_follows_continuation_and_caps_at_1000(s3):
    first = page(*[f"public/{i}" for i in range(600)], next_token="t1")
    second = page(*[f"public/b{i}" for i in range(400)], next_token="t2")
    s3.list_objects_v2.side_effect = [first, second]
    status, body = call(mod, s3, event(machine_claims("artifacts/read"), {"prefix": "public/"}))
    assert status == 200
    assert len(body["items"]) == 1000
    assert body["truncated"] is True
    calls = s3.list_objects_v2.call_args_list
    assert calls[0].kwargs["MaxKeys"] == 1000
    assert calls[1].kwargs == {"Bucket": "test-bucket", "Prefix": "public/",
                               "MaxKeys": 400, "ContinuationToken": "t1"}
