# CI client secret rotation

The Cognito app client `${name_prefix}-ci` authenticates CI uploads with the
client_credentials grant. Its credentials live in the Secrets Manager secret
`${name_prefix}/ci-client` as JSON. Secrets Manager rotates the secret every
30 days by calling the Lambda `${name_prefix}-rotate-ci-secret`
(`lambda/rotate_ci_secret/handler.py`, Terraform in `rotation.tf`).

## Research: does Cognito support two active client secrets?

**Yes.** This was checked against the AWS API reference and developer guide
on 2026-10-26:

- `AddUserPoolClientSecret(UserPoolId, ClientId, [ClientSecret])` adds a
  secret. It returns `ClientSecretDescriptor {ClientSecretId,
  ClientSecretValue, ClientSecretCreateDate}`. The value is returned only when
  Cognito generates it, which is how we call it.
- `ListUserPoolClientSecrets(UserPoolId, ClientId)` returns ids and creation
  dates. It never returns values.
- `DeleteUserPoolClientSecret(UserPoolId, ClientId, ClientSecretId)` deletes
  one secret. You can't delete the last one.
- The developer guide says: "Each app client can have up to two secrets at a
  time, enabling secret rotation without downtime."

So the rotation is truly zero-downtime. There is **no window** where the
secret in AWSCURRENT is rejected by Cognito.

Not verified locally: these docs were read online, not against the botocore
model installed here. The sandbox blocked running Python outside the test
command. See "Runtime boto3" below.

## What the secret holds

```json
{ "client_id": "...", "client_secret": "...", "client_secret_id": "..." }
```

CI reads `client_id` and `client_secret`, the same as before.
`client_secret_id` is new. The Lambda needs it because the list API never
returns values, so the stored id is the only way to know which Cognito secret
is live. The seed value Terraform writes has no `client_secret_id`. The
Lambda handles that (see below).

## The four steps

| Step | What it does | On retry |
|---|---|---|
| `createSecret` | If the client already has 2 secrets, delete every one except AWSCURRENT's. Then `AddUserPoolClientSecret` and store `{client_id, new secret, its id}` as AWSPENDING. | If the AWSPENDING value already exists, it does nothing. If a previous try added a Cognito secret but failed to store it, that orphan is the non-current secret at the cap, so it gets deleted and replaced. |
| `setSecret` | Nothing to do. Cognito accepts the secret as soon as it's added. | Same. |
| `testSecret` | `POST /oauth2/token` (client_credentials, scope `artifacts/write`) with the pending credentials. Retries 3 times with backoff in case a new secret takes a moment to be accepted. | Read-only. |
| `finishSecret` | Move AWSCURRENT to the new version. Secrets Manager labels the old one AWSPREVIOUS. Then delete any Cognito secret that is neither AWSCURRENT nor AWSPREVIOUS. | If the token is already AWSCURRENT, it skips the move and re-runs only the cleanup. |

Every step first checks that rotation is enabled, that the token is a known
version, and that it is staged AWSPENDING. Anything else raises an error
instead of touching Cognito.

### Why deletion happens in the next `createSecret`, not in `finishSecret`

The brief said `finishSecret` should "delete the oldest Cognito secret,
keeping the previous one valid until the next rotation". With a cap of two,
those two goals conflict. After the promotion, the client holds exactly two
secrets: the new current one and the one just demoted. Deleting the oldest at
that point would kill the demoted secret straight away. A CI job that read
the secret seconds before the rotation would then fail.

So the order is:

```
rotation N   createSecret: {prev, cur} -> delete prev -> {cur, new}
             finishSecret: AWSCURRENT=new, AWSPREVIOUS=cur, both still valid
rotation N+1 createSecret: delete cur (demoted 30 days ago) -> ...
```

A secret stays valid for a full rotation period after it stops being
AWSCURRENT. `finishSecret` still cleans up, but only removes secrets outside
{AWSCURRENT, AWSPREVIOUS}. At a cap of two, that means orphans. It keeps
working unchanged if Cognito ever raises the cap.

**Grace period caveat:** the grace period equals the time between rotations.
If you run two rotations back to back with `rotate-secret`, the second one
deletes the secret the first one demoted. Don't do that while CI jobs are
running.

### The Terraform seed value (no `client_secret_id`)

- **First rotation:** the client has one secret, so nothing needs deleting.
  The new version gets an id. Cleanup in `finishSecret` is skipped because
  AWSPREVIOUS has no id. The Lambda never deletes when it can't name what to
  keep.
- **If the client is already at 2 secrets and AWSCURRENT has no id** (someone
  added one by hand, or the first rotation failed between add and store), the
  Lambda refuses with "refusing to guess". It can't tell which secret is live.
  To fix it, delete the stray secret yourself
  (`aws cognito-idp list-user-pool-client-secrets` then
  `delete-user-pool-client-secret`), then rotate again.

## Terraform and rotation don't fight

- `aws_secretsmanager_secret_version.ci` has
  `lifecycle { ignore_changes = [secret_string] }`. After the first rotation,
  the client's first secret is eventually deleted. Without this, Terraform
  would write it back as a new AWSCURRENT and break CI.
- `aws_cognito_user_pool_client.ci` needs no `ignore_changes`. Rotation only
  calls the secret APIs, which change no configurable attribute.
  `client_secret` is computed. `generate_secret` stays true because a client
  always keeps at least one secret.
- If the CI client is ever **replaced** (a ForceNew change), the secret
  version won't update because of `ignore_changes`. Run a rotation right
  after, or `terraform apply -replace=module.auth.aws_secretsmanager_secret_version.ci`.

## IAM (role `artifact-portal-dev-rotate-ci-secret`)

- `secretsmanager:DescribeSecret`, `GetSecretValue`, `PutSecretValue` and
  `UpdateSecretVersionStage` on this secret's ARN only. The secret uses the
  default `aws/secretsmanager` key, so no KMS statement is needed.
- `cognito-idp:AddUserPoolClientSecret`, `ListUserPoolClientSecrets` and
  `DeleteUserPoolClientSecret` on this pool's ARN. Cognito's IAM resource is
  the pool, so this can't be narrowed to the one client. The handler only
  passes the `CLIENT_ID` from its environment.
- `logs:CreateLogStream` and `logs:PutLogEvents` on its own log group.
- `aws_lambda_permission` lets `secretsmanager.amazonaws.com` invoke it, with
  `source_arn` set to this secret.

## Runtime boto3

The Lambda uses the boto3 bundled with the `python3.13` runtime. If that
boto3 predates the multi-secret APIs, `_cognito()` raises
`boto3 in this runtime lacks Cognito multi-secret APIs` before touching
anything. Rotation fails safely and AWSCURRENT stays as it was. The fix would
be to ship a newer boto3 in the zip or as a layer. The first manual rotation
is where you'd see this.

## First rotation

`rotate_immediately = false`, so the apply that creates rotation doesn't also
run it unattended. After applying:

```sh
SECRET=$(terraform -chdir=envs/dev output -raw ci_secret_arn)
aws secretsmanager rotate-secret --secret-id "$SECRET"
aws logs tail /aws/lambda/artifact-portal-dev-rotate-ci-secret --follow
aws secretsmanager describe-secret --secret-id "$SECRET" --query VersionIdsToStages
```

The rotation worked when the new version is AWSCURRENT and CI can still get a
token.

## Not done here (left for other workstreams)

- An alarm on rotation failure (the Lambda's `Errors` metric, or the
  EventBridge `RotationFailed` event). The `monitoring` module was out of
  scope for this change.
- The README isn't updated. This file is the write-up.
