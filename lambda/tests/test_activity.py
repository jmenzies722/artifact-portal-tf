import datetime as dt
import json
from unittest import mock

import pytest

from helpers import event, load_handler, machine_claims, user_claims

mod = load_handler("activity")

KEYS = ["develop/app-1.2.zip", "partners/partner_b/b.zip", "partners/partner_a/a.zip", "public/readme.txt"]


def item(key, ts, action="upload"):
    return {"sk": {"S": f"{ts}#r-{key}"}, "key": {"S": key}, "action": {"S": action},
            "actor": {"S": "dev@example.com"}, "actor_kind": {"S": "user"}, "outcome": {"S": "url_issued"}}


def one_of_each():
    """Newest first, as DynamoDB returns with ScanIndexForward=False."""
    return [item(k, f"2026-10-26T04:0{9 - i}:00.000Z") for i, k in enumerate(KEYS)]


@pytest.fixture
def db():
    client = mock.MagicMock()
    # Today's partition has one item per area; older partitions are empty.
    client.query.side_effect = [{"Items": one_of_each()}] + [{"Items": []}] * 7
    return client


def run(db, claims, query=None):
    with mock.patch.object(mod, "_dynamodb", return_value=db):
        result = mod.handler(event(claims, query), None)
    return result["statusCode"], json.loads(result["body"])


def keys_seen(body):
    return {i["key"] for i in body["items"]}


def test_401_without_claims(db):
    assert run(db, None)[0] == 401
    db.query.assert_not_called()


def test_partner_a_never_sees_partner_b_or_develop(db):
    status, body = run(db, user_claims("partner_a"))
    assert status == 200
    assert keys_seen(body) == {"partners/partner_a/a.zip", "public/readme.txt"}


def test_partner_b_never_sees_partner_a_or_develop(db):
    _, body = run(db, user_claims("partner_b"))
    assert keys_seen(body) == {"partners/partner_b/b.zip", "public/readme.txt"}


def test_developers_see_all_three_areas(db):
    _, body = run(db, user_claims("developers"))
    assert keys_seen(body) == set(KEYS)


def test_read_machine_sees_public_and_develop_only(db):
    _, body = run(db, machine_claims("artifacts/read"))
    assert keys_seen(body) == {"develop/app-1.2.zip", "public/readme.txt"}


def test_write_only_machine_gets_403(db):
    assert run(db, machine_claims("artifacts/write"))[0] == 403
    db.query.assert_not_called()


def test_user_without_role_gets_403(db):
    assert run(db, user_claims())[0] == 403


def test_items_are_newest_first_with_safe_fields(db):
    _, body = run(db, user_claims("developers"))
    first = body["items"][0]
    assert first == {"ts": "2026-10-26T04:09:00.000Z", "action": "upload", "key": "develop/app-1.2.zip",
                     "actor": "dev@example.com", "actor_kind": "user", "outcome": "url_issued"}
    assert [i["ts"] for i in body["items"]] == sorted((i["ts"] for i in body["items"]), reverse=True)
    # source_ip and groups are never even read from the table.
    assert "source_ip" not in db.query.call_args.kwargs["ProjectionExpression"]


@pytest.mark.parametrize("raw", ["0", "8", "-1", "abc", "1.5"])
def test_400_on_bad_days(db, raw):
    assert run(db, user_claims("developers"), {"days": raw})[0] == 400


def test_days_queries_each_partition_newest_first(db):
    fixed = dt.datetime(2026, 10, 26, 4, 11, 0, tzinfo=dt.timezone.utc)
    with mock.patch.object(mod, "datetime") as clock:
        clock.now.return_value = fixed
        status, body = run(db, user_claims("developers"), {"days": "3"})
    assert (status, body["days"]) == (200, 3)
    pks = [c.kwargs["ExpressionAttributeValues"][":pk"]["S"] for c in db.query.call_args_list]
    assert pks == ["DAY#2026-10-26", "DAY#2026-10-25", "DAY#2026-10-24", "DAY#2026-10-23"]
    since = db.query.call_args.kwargs["ExpressionAttributeValues"][":since"]["S"]
    assert since == "2026-10-23T04:11:00.000Z"
    assert all(c.kwargs["ScanIndexForward"] is False for c in db.query.call_args_list)


def test_default_is_one_day(db):
    _, body = run(db, user_claims("developers"))
    assert body["days"] == 1
    assert db.query.call_count == 2  # today + yesterday cover the last 24h


def test_follows_pagination_and_caps_at_100(db):
    page1 = {"Items": [item(f"public/{i}", f"2026-10-26T03:{59 - i % 60:02d}:00.000Z") for i in range(80)],
             "LastEvaluatedKey": {"pk": {"S": "x"}}}
    page2 = {"Items": [item(f"develop/{i}", "2026-10-26T01:00:00.000Z") for i in range(80)]}
    db.query.side_effect = [page1, page2]
    _, body = run(db, user_claims("developers"))
    assert len(body["items"]) == 100 and body["truncated"] is True
    assert db.query.call_args_list[1].kwargs["ExclusiveStartKey"] == {"pk": {"S": "x"}}


def test_filtering_happens_before_the_cap(db):
    """A partner's 100 items aren't eaten up by rows they can't see."""
    hidden = [item(f"develop/{i}", "2026-10-26T04:00:00.000Z") for i in range(150)]
    db.query.side_effect = [{"Items": hidden + [item("public/ok", "2026-10-26T03:00:00.000Z")]}, {"Items": []}]
    _, body = run(db, user_claims("partner_a"))
    assert keys_seen(body) == {"public/ok"} and body["truncated"] is False
