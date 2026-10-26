"""Secrets Manager rotation for the CI app client's Cognito secret.

Cognito app clients hold up to two secrets at once, so rotation never breaks
CI: the new secret works before anyone reads it, and the one it replaces stays
valid until the next rotation. See modules/auth/ROTATION.md.
"""
import base64
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import boto3

log = logging.getLogger()
log.setLevel(logging.INFO)

PENDING, CURRENT, PREVIOUS = "AWSPENDING", "AWSCURRENT", "AWSPREVIOUS"
MAX_SECRETS = 2  # Cognito's per-client limit
TOKEN_ATTEMPTS = 3  # a just-added secret can take a moment to be accepted
TOKEN_RETRY_SECONDS = 2


def _sm():
    return boto3.client("secretsmanager")


def _cognito():
    client = boto3.client("cognito-idp")
    # Fail before touching anything if the runtime's boto3 is too old.
    if not hasattr(client, "add_user_pool_client_secret"):
        raise RuntimeError("boto3 in this runtime lacks Cognito multi-secret APIs")
    return client


def _ids():
    return {"UserPoolId": os.environ["USER_POOL_ID"], "ClientId": os.environ["CLIENT_ID"]}


def handler(event, _context):
    arn, token, step = event["SecretId"], event["ClientRequestToken"], event["Step"]
    sm = _sm()

    meta = sm.describe_secret(SecretId=arn)
    if not meta.get("RotationEnabled"):
        raise ValueError(f"rotation is not enabled for {arn}")
    stages = meta.get("VersionIdsToStages", {})
    if token not in stages:
        raise ValueError(f"version {token} has no stage for {arn}")
    if CURRENT in stages[token]:
        # A retry after finishSecret already promoted this version: only the
        # cleanup may still be outstanding, and it is idempotent.
        log.info("version %s is already AWSCURRENT", token)
        if step == "finishSecret":
            _prune(sm, _cognito(), arn)
        return
    if PENDING not in stages[token]:
        raise ValueError(f"version {token} is not AWSPENDING for {arn}")

    if step == "createSecret":
        create_secret(sm, _cognito(), arn, token)
    elif step == "setSecret":
        log.info("setSecret: nothing to do, Cognito accepts the secret once added")
    elif step == "testSecret":
        test_secret(sm, arn, token)
    elif step == "finishSecret":
        finish_secret(sm, _cognito(), arn, token, stages)
    else:
        raise ValueError(f"unknown step {step}")


def create_secret(sm, cognito, arn, token):
    try:
        _value(sm, arn, PENDING, token)
        log.info("createSecret: pending value already stored")
        return
    except sm.exceptions.ResourceNotFoundException:
        pass

    # At the cap, drop everything but the live secret. That is the one AWSCURRENT
    # replaced last rotation (a full period ago), or an orphan from a failed run.
    if len(_list(cognito)) >= MAX_SECRETS:
        current_id = _value(sm, arn, CURRENT).get("client_secret_id")
        if not current_id:
            raise RuntimeError("client is at its secret limit and AWSCURRENT has no "
                               "client_secret_id; refusing to guess which to delete")
        _delete_except(cognito, {current_id})

    added = cognito.add_user_pool_client_secret(**_ids())["ClientSecretDescriptor"]
    sm.put_secret_value(
        SecretId=arn,
        ClientRequestToken=token,
        VersionStages=[PENDING],
        SecretString=json.dumps({
            "client_id": os.environ["CLIENT_ID"],
            "client_secret": added["ClientSecretValue"],
            "client_secret_id": added["ClientSecretId"],
        }),
    )
    log.info("createSecret: added Cognito secret %s", added["ClientSecretId"])


def test_secret(sm, arn, token):
    pending = _value(sm, arn, PENDING, token)
    for attempt in range(1, TOKEN_ATTEMPTS + 1):
        try:
            _fetch_token(pending["client_id"], pending["client_secret"])
            log.info("testSecret: pending secret got a token")
            return
        except urllib.error.HTTPError as err:
            if attempt == TOKEN_ATTEMPTS:
                raise RuntimeError(f"token endpoint rejected the pending secret: {err.code}") from err
            time.sleep(TOKEN_RETRY_SECONDS * attempt)


def finish_secret(sm, cognito, arn, token, stages):
    current = next(v for v, s in stages.items() if CURRENT in s)
    sm.update_secret_version_stage(
        SecretId=arn, VersionStage=CURRENT, MoveToVersionId=token, RemoveFromVersionId=current,
    )
    log.info("finishSecret: %s is now AWSCURRENT", token)
    _prune(sm, cognito, arn)


def _prune(sm, cognito, arn):
    """Delete Cognito secrets that are neither AWSCURRENT nor AWSPREVIOUS.

    AWSPREVIOUS is kept on purpose: CI jobs that read the secret just before
    the rotation keep working. With the cap at two this only clears orphans.
    """
    keep = {_value(sm, arn, CURRENT).get("client_secret_id")}
    try:
        keep.add(_value(sm, arn, PREVIOUS).get("client_secret_id"))
    except sm.exceptions.ResourceNotFoundException:
        keep.add(None)
    if None in keep:
        log.info("finishSecret: a version predates client_secret_id; skipping cleanup")
        return
    _delete_except(cognito, keep)


def _delete_except(cognito, keep):
    for s in _list(cognito):
        if s["ClientSecretId"] not in keep:
            cognito.delete_user_pool_client_secret(**_ids(), ClientSecretId=s["ClientSecretId"])
            log.info("deleted Cognito secret %s", s["ClientSecretId"])


def _list(cognito):
    return cognito.list_user_pool_client_secrets(**_ids()).get("ClientSecrets", [])


def _value(sm, arn, stage, version=None):
    kwargs = {"SecretId": arn, "VersionStage": stage}
    if version:
        kwargs["VersionId"] = version
    return json.loads(sm.get_secret_value(**kwargs)["SecretString"])


def _fetch_token(client_id, client_secret):
    """client_credentials grant against the pool's /oauth2/token endpoint."""
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req = urllib.request.Request(
        os.environ["TOKEN_URL"],
        data=urllib.parse.urlencode({"grant_type": "client_credentials", "scope": os.environ["SCOPE"]}).encode(),
        headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = json.loads(resp.read())
    if not body.get("access_token"):
        raise RuntimeError("token endpoint returned no access_token")
