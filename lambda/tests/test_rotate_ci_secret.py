"""Rotation Lambda for the CI client secret, against in-memory fakes that keep
Secrets Manager's version stages and Cognito's two-secret limit."""
import json
import types
import urllib.error
from unittest import mock

import pytest

from helpers import load_handler

rotate = load_handler("rotate_ci_secret")

ARN = "arn:aws:secretsmanager:us-east-1:111122223333:secret:artifact-portal-dev/ci-client-AbCdEf"
CURRENT, PENDING, PREVIOUS = "AWSCURRENT", "AWSPENDING", "AWSPREVIOUS"


class NotFound(Exception):
    pass


class FakeSecretsManager:
    def __init__(self, initial):
        self.exceptions = types.SimpleNamespace(ResourceNotFoundException=NotFound)
        self.rotation_enabled = True
        self.versions = {"v0": {"stages": {CURRENT}, "value": json.dumps(initial)}}
        self.fail_next_put = False
        self.stage_moves = 0

    def start_rotation(self, token):
        """What RotateSecret does before calling the Lambda: stage an empty version."""
        for d in self.versions.values():
            d["stages"].discard(PENDING)
        self.versions[token] = {"stages": {PENDING}, "value": None}

    def describe_secret(self, SecretId):
        return {"RotationEnabled": self.rotation_enabled,
                "VersionIdsToStages": {v: sorted(d["stages"]) for v, d in self.versions.items()}}

    def get_secret_value(self, SecretId, VersionStage, VersionId=None):
        for vid, d in self.versions.items():
            if VersionStage in d["stages"] and VersionId in (None, vid) and d["value"] is not None:
                return {"VersionId": vid, "SecretString": d["value"]}
        raise NotFound(VersionStage)

    def put_secret_value(self, SecretId, ClientRequestToken, VersionStages, SecretString):
        if self.fail_next_put:
            self.fail_next_put = False
            raise RuntimeError("throttled")
        version = self.versions.setdefault(ClientRequestToken, {"stages": set(), "value": None})
        version["stages"] |= set(VersionStages)
        version["value"] = SecretString

    def update_secret_version_stage(self, SecretId, VersionStage, MoveToVersionId, RemoveFromVersionId):
        assert VersionStage in self.versions[RemoveFromVersionId]["stages"]
        self.stage_moves += 1
        self.versions[RemoveFromVersionId]["stages"].discard(VersionStage)
        self.versions[MoveToVersionId]["stages"].add(VersionStage)
        if VersionStage == CURRENT:  # Secrets Manager labels the old one AWSPREVIOUS
            for d in self.versions.values():
                d["stages"].discard(PREVIOUS)
            self.versions[RemoveFromVersionId]["stages"].add(PREVIOUS)

    def value(self, stage):
        return json.loads(self.get_secret_value(ARN, stage)["SecretString"])


class FakeCognito:
    def __init__(self):
        self.secrets = {"s0": "original-secret"}
        self.added = self.deleted = 0

    def add_user_pool_client_secret(self, UserPoolId, ClientId):
        assert (UserPoolId, ClientId) == ("us-east-1_pool", "ci-client")
        if len(self.secrets) >= 2:
            raise RuntimeError("LimitExceededException")
        self.added += 1
        sid = f"s{self.added}"
        self.secrets[sid] = f"secret-{self.added}"
        return {"ClientSecretDescriptor": {"ClientSecretId": sid, "ClientSecretValue": self.secrets[sid],
                                           "ClientSecretCreateDate": self.added}}

    def list_user_pool_client_secrets(self, UserPoolId, ClientId):
        # Like the real API: ids and dates, never values.
        return {"ClientSecrets": [{"ClientSecretId": sid} for sid in self.secrets]}

    def delete_user_pool_client_secret(self, UserPoolId, ClientId, ClientSecretId):
        if len(self.secrets) == 1:
            raise RuntimeError("cannot delete the last secret")
        del self.secrets[ClientSecretId]
        self.deleted += 1


@pytest.fixture(autouse=True)
def rotation_env(monkeypatch):
    monkeypatch.setenv("USER_POOL_ID", "us-east-1_pool")
    monkeypatch.setenv("CLIENT_ID", "ci-client")
    monkeypatch.setenv("TOKEN_URL", "https://auth.example/oauth2/token")
    monkeypatch.setenv("SCOPE", "artifacts/write")


@pytest.fixture
def sm():
    # Terraform's initial value: no client_secret_id.
    return FakeSecretsManager({"client_id": "ci-client", "client_secret": "original-secret"})


@pytest.fixture
def cognito():
    return FakeCognito()


@pytest.fixture
def tokens():
    """Records credentials sent to the token endpoint; all succeed by default."""
    with mock.patch.object(rotate, "_fetch_token") as fetch, mock.patch.object(rotate.time, "sleep"):
        yield fetch


def run(sm, cognito, step, token):
    with mock.patch.object(rotate, "_sm", return_value=sm), \
         mock.patch.object(rotate, "_cognito", return_value=cognito):
        rotate.handler({"SecretId": ARN, "ClientRequestToken": token, "Step": step}, None)


def rotate_fully(sm, cognito, token):
    sm.start_rotation(token)
    for step in ("createSecret", "setSecret", "testSecret", "finishSecret"):
        run(sm, cognito, step, token)


# --- happy path ------------------------------------------------------------

def test_first_rotation_keeps_the_old_secret_valid(sm, cognito, tokens):
    rotate_fully(sm, cognito, "t1")

    assert sm.value(CURRENT) == {"client_id": "ci-client", "client_secret": "secret-1", "client_secret_id": "s1"}
    assert sm.value(PREVIOUS)["client_secret"] == "original-secret"
    assert set(cognito.secrets) == {"s0", "s1"}  # both still accepted by Cognito
    tokens.assert_called_once_with("ci-client", "secret-1")


def test_second_rotation_retires_the_secret_from_two_rotations_ago(sm, cognito, tokens):
    rotate_fully(sm, cognito, "t1")
    rotate_fully(sm, cognito, "t2")

    assert sm.value(CURRENT)["client_secret_id"] == "s2"
    assert sm.value(PREVIOUS)["client_secret_id"] == "s1"
    assert set(cognito.secrets) == {"s1", "s2"}


def test_set_secret_touches_nothing(sm, cognito):
    sm.start_rotation("t1")
    run(sm, cognito, "createSecret", "t1")
    before = dict(cognito.secrets)
    run(sm, cognito, "setSecret", "t1")
    assert cognito.secrets == before


# --- idempotency (Secrets Manager retries steps) ----------------------------

def test_create_secret_retry_does_not_add_a_second_secret(sm, cognito):
    sm.start_rotation("t1")
    run(sm, cognito, "createSecret", "t1")
    run(sm, cognito, "createSecret", "t1")
    assert cognito.added == 1


def test_create_secret_retry_after_failed_store_clears_the_orphan(sm, cognito, tokens):
    rotate_fully(sm, cognito, "t1")  # Cognito: s0 (previous), s1 (current)
    sm.start_rotation("t2")
    sm.fail_next_put = True
    with pytest.raises(RuntimeError, match="throttled"):
        run(sm, cognito, "createSecret", "t2")  # s0 deleted, s2 added, never stored
    assert set(cognito.secrets) == {"s1", "s2"}

    run(sm, cognito, "createSecret", "t2")
    assert set(cognito.secrets) == {"s1", "s3"}  # orphan s2 gone, live s1 untouched
    assert sm.value(CURRENT)["client_secret_id"] == "s1"


def test_finish_secret_retry_does_not_move_stages_twice(sm, cognito, tokens):
    rotate_fully(sm, cognito, "t1")
    run(sm, cognito, "finishSecret", "t1")
    assert sm.stage_moves == 1
    assert sm.value(CURRENT)["client_secret_id"] == "s1"


def test_finish_secret_retry_still_cleans_up_orphans(sm, cognito, tokens):
    rotate_fully(sm, cognito, "t1")
    rotate_fully(sm, cognito, "t2")  # current s2, previous s1
    cognito.secrets = {"orphan": "x", "s2": "secret-2"}  # e.g. s1 removed by hand
    run(sm, cognito, "finishSecret", "t2")
    assert set(cognito.secrets) == {"s2"}


# --- refusing what isn't staged correctly -----------------------------------

def test_refuses_a_version_that_is_not_pending(sm, cognito):
    sm.versions["t1"] = {"stages": {PREVIOUS}, "value": "{}"}
    with pytest.raises(ValueError, match="not AWSPENDING"):
        run(sm, cognito, "createSecret", "t1")
    assert cognito.added == 0


def test_refuses_an_unknown_version(sm, cognito):
    with pytest.raises(ValueError, match="no stage"):
        run(sm, cognito, "createSecret", "nope")


def test_refuses_when_rotation_is_disabled(sm, cognito):
    sm.rotation_enabled = False
    sm.start_rotation("t1")
    with pytest.raises(ValueError, match="not enabled"):
        run(sm, cognito, "createSecret", "t1")


def test_refuses_unknown_step(sm, cognito):
    sm.start_rotation("t1")
    with pytest.raises(ValueError, match="unknown step"):
        run(sm, cognito, "dance", "t1")


def test_refuses_to_guess_which_secret_is_live(sm, cognito):
    cognito.secrets["stray"] = "added-by-hand"  # at the cap, AWSCURRENT has no id
    sm.start_rotation("t1")
    with pytest.raises(RuntimeError, match="refusing to guess"):
        run(sm, cognito, "createSecret", "t1")
    assert set(cognito.secrets) == {"s0", "stray"}


# --- testSecret -------------------------------------------------------------

def http_error(code):
    return urllib.error.HTTPError("https://auth.example/oauth2/token", code, "err", None, None)


def test_test_secret_retries_while_the_new_secret_propagates(sm, cognito, tokens):
    tokens.side_effect = [http_error(400), None]
    rotate_fully(sm, cognito, "t1")
    assert tokens.call_count == 2
    assert sm.value(CURRENT)["client_secret_id"] == "s1"


def test_test_secret_failure_leaves_current_untouched(sm, cognito, tokens):
    tokens.side_effect = http_error(400)
    sm.start_rotation("t1")
    run(sm, cognito, "createSecret", "t1")
    with pytest.raises(RuntimeError, match="rejected"):
        run(sm, cognito, "testSecret", "t1")
    assert sm.value(CURRENT)["client_secret"] == "original-secret"


def test_fetch_token_uses_client_credentials_with_basic_auth():
    resp = mock.MagicMock()
    resp.__enter__.return_value.read.return_value = b'{"access_token": "jwt"}'
    with mock.patch.object(rotate.urllib.request, "urlopen", return_value=resp) as urlopen:
        rotate._fetch_token("ci-client", "s3cret")
    req = urlopen.call_args.args[0]
    assert req.full_url == "https://auth.example/oauth2/token"
    assert req.get_header("Authorization") == "Basic Y2ktY2xpZW50OnMzY3JldA=="  # ci-client:s3cret
    assert req.data == b"grant_type=client_credentials&scope=artifacts%2Fwrite"


def test_fetch_token_rejects_a_response_without_a_token():
    resp = mock.MagicMock()
    resp.__enter__.return_value.read.return_value = b"{}"
    with mock.patch.object(rotate.urllib.request, "urlopen", return_value=resp):
        with pytest.raises(RuntimeError, match="no access_token"):
            rotate._fetch_token("ci-client", "s3cret")


def test_old_boto3_fails_before_touching_anything():
    with mock.patch.object(rotate.boto3, "client", return_value=types.SimpleNamespace()):
        with pytest.raises(RuntimeError, match="multi-secret"):
            rotate._cognito()
