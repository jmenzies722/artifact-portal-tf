import importlib.util
import json
from pathlib import Path
from unittest import mock

LAMBDA_DIR = Path(__file__).resolve().parent.parent


class FakeClientError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


def load_handler(name):
    """Import lambda/<name>/handler.py under a unique module name."""
    spec = importlib.util.spec_from_file_location(f"{name}_handler", LAMBDA_DIR / name / "handler.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def call(module, s3, ev):
    """Run a handler with its S3 client replaced by the given mock."""
    with mock.patch.object(module, "_s3", return_value=s3):
        result = module.handler(ev, None)
    return result["statusCode"], json.loads(result["body"])


def user_claims(*groups):
    return {"token_use": "id", "cognito:username": "u1", "sub": "u1",
            "cognito:groups": "[" + " ".join(groups) + "]"}


def machine_claims(*scopes):
    return {"token_use": "access", "client_id": "ci-client", "sub": "ci-client",
            "scope": " ".join(scopes)}


def event(claims=None, query=None, body=None):
    ev = {"requestContext": {}, "queryStringParameters": query, "body": body}
    if claims is not None:
        ev["requestContext"]["authorizer"] = {"jwt": {"claims": claims}}
    return ev
