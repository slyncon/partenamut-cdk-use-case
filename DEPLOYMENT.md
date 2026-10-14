# Interview deployment: automated CI, manual CD

GitHub Actions validates the code. After a successful run, you review and deploy
from WSL using AWS IAM Identity Center (SSO) profile **`cdk-sso`**.

| Setting | Interview target |
| --- | --- |
| AWS account | `117301763389` |
| Deployment region | `eu-central-1` |
| Local profile | `cdk-sso` |
| CloudFormation stacks | `ClaimsTeamStack`, `MedicalDocumentsTeamStack` |
| Bootstrap stack | Standard `CDKToolkit` |

The local directory and Git repository `partenamut-cdk-use-case` keep their names.
AWS resource names/tags use generic identifiers; the shared validator rejects
`partenamut` in AWS identities, name properties and tags. Existing bucket/function
construct paths and logical IDs remain unchanged. No AWS resources were renamed
or changed while preparing this update.

## 1. Local setup and validation

Clone the three repositories as siblings. Platform is a Python library, not a
stack to deploy. Team A contains the app. Install Python 3.12, Node 24 LTS/npm,
Git and AWS CLI v2; create a fresh environment rather than copying another laptop's
virtual environment or node_modules.

From `cdk-team-a`:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
python -m pip install --no-deps --no-build-isolation -r requirements.txt
python -m pip check
npm ci
export PATH="$PWD/node_modules/.bin:$PATH"
python -m ruff check .
python -m pytest -q
cdk ls
cdk synth
cdk-launchpad-validate .build/cdk.out
python scripts/check_assembly.py .build/cdk.out
```

Those tests and synthesis require no AWS credentials. Security audits contact
public advisory databases; CI additionally runs Bandit, pip-audit, npm audit and
Gitleaks. After committing an application change, wait for **Validate team** in
GitHub Actions to pass. Deploy the same reviewed commit from a clean checkout;
CI does not automatically restrict what an administrative SSO user can deploy.

## 2. Authenticate and verify the account

Assume `cdk-sso` is configured for IAM Identity Center. Do not create IAM users or
long-lived access keys, copy credentials into GitHub, or modify profile files as
part of the application. Refresh the temporary SSO session:

```bash
aws sso login --profile cdk-sso
export AWS_REGION=eu-central-1
export AWS_DEFAULT_REGION=eu-central-1
aws sts get-caller-identity --profile cdk-sso
```

Confirm the returned account is **117301763389** before continuing. An optional
shell guard prevents continuing with another account:

```bash
test "$(aws sts get-caller-identity --profile cdk-sso --query Account --output text)" = "117301763389" || {
  echo "Wrong AWS account; stop before bootstrap or deployment."
  exit 1
}
```

The deployment region is independent of the SSO authentication region. Do not
change the SSO authentication region based on this guide.

## 3. Bootstrap once — human-operated only

The user reports that this account/region has no `CDKToolkit` stack. From Team A
with its environment and pinned CDK CLI active, run:

```bash
cdk bootstrap aws://117301763389/eu-central-1 --profile cdk-sso --termination-protection
```

This creates CDK's supporting asset bucket, SSM version parameter, and standard
publishing/deployment/CloudFormation roles (plus standard bootstrap infrastructure).
It is not an application deployment. It must never run in CI. Keep the bootstrap
stack; do not delete/recreate it to clean up the demonstration.

The SSO permission set must allow bootstrap provisioning and subsequent use of
the standard CDK roles. If bootstrap or AssumeRole fails, fix the SSO permission
set/trust with the account administrator. Do not invent access keys or restore
the deleted custom role as a shortcut. Default bootstrap CloudFormation permissions
are broad; they suit this disposable sandbox, not a production isolation claim.

## 4. Review, validate, then deploy Claims

```bash
cdk diff ClaimsTeamStack --profile cdk-sso --change-set false
cdk synth ClaimsTeamStack --profile cdk-sso
cdk-launchpad-validate .build/cdk.out
python scripts/check_assembly.py .build/cdk.out
cdk deploy ClaimsTeamStack --profile cdk-sso
```

The diff uses a template comparison without creating an AWS change set. Review it
and the interactive deployment approval before continuing. Stop if it proposes
unexpected removal/replacement of an existing bucket, function name changes, or
a move to a different stack/account. No stack name or stateful construct ID was
changed for this migration.

For a previously deployed custom-role stack, expected template changes include
one new stack-owned managed boundary policy and updating Lambda roles to reference
it. File assets move from the former `claims/` prefix to standard CDK hash keys,
which can update Lambda code locations without changing their logical IDs. Review
any actual replacements instead of assuming these are harmless in your live stack.

`app.py` uses the default CDK synthesizer. It does not reference a deleted custom
CloudFormation role, GitHub role or external boundary ARN. Standard CDK bootstrap
roles handle deployment; application Lambda roles are created by the stack.

## 5. Upload one fake claim and inspect logs

Use the actual CloudFormation outputs; do not guess resource names:

```bash
CLAIMS_BUCKET=$(aws cloudformation describe-stacks --stack-name ClaimsTeamStack \
  --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue | [0]" --output text \
  --profile cdk-sso --region eu-central-1)
CLAIMS_LOG_GROUP=$(aws cloudformation describe-stacks --stack-name ClaimsTeamStack \
  --query "Stacks[0].Outputs[?OutputKey=='LogGroupName'].OutputValue | [0]" --output text \
  --profile cdk-sso --region eu-central-1)

test -n "$CLAIMS_BUCKET" && test "$CLAIMS_BUCKET" != "None"
test -n "$CLAIMS_LOG_GROUP" && test "$CLAIMS_LOG_GROUP" != "None"
aws s3 cp fixtures/claim.json "s3://$CLAIMS_BUCKET/incoming/claim.json" \
  --profile cdk-sso --region eu-central-1
aws logs tail "$CLAIMS_LOG_GROUP" --since 10m \
  --profile cdk-sso --region eu-central-1
```

Notifications are asynchronous; wait briefly and repeat the log read if needed.
The handler reads and validates fictional claim JSON and logs a processing result.
It never updates objects, approves claims or pays money. Duplicate events are safe
to repeat. The current MVP has no durable dead-letter design.

Team B can be deployed independently from its own directory with
`cdk diff MedicalDocumentsTeamStack --profile cdk-sso --change-set false` and
`cdk deploy MedicalDocumentsTeamStack --profile cdk-sso` after its validation passes.
See its README for its metadata fixture and outputs.

## 6. Security that remains active

- Shared S3 defaults: SSE-S3, block-all-public-access, TLS denial, generated names.
- Shared template gate: encryption, all four public-access flags, TLS and generic
  AWS naming, including raw buckets bypassing the shared construct.
- Python/handler/infrastructure tests, Ruff, Bandit, Gitleaks, pip-audit and npm audit.
- Immutable Platform/action commit pins; Team A's hashed Python dependency lock.
- Team A's runtime permissions boundary is **created inside ClaimsTeamStack** and
  attached to both its application role and CDK notification-helper role. It caps
  reads at its exact bucket's `incoming/` objects, bucket metadata/notification
  operations, and application/helper logs. It does not grant permissions by itself.
- CI checks that boundary contents are narrow, every role references the owned
  policy, roles trust only Lambda, resources stay within the permitted services,
  and synthesis uses standard bootstrap roles/assets. Negative tests prove bypasses
  fail; a dependency-cycle test covers the new policy references.

Removing an external boundary dependency does not remove the boundary restriction.
The deleted custom deployment role and its scoped CloudFormation restrictions are
not active controls. Human deployment now relies on the SSO permission set and
standard bootstrap roles; the runtime boundary does not limit an administrator or
CloudFormation itself. Required PR checks/reviews depend on real GitHub settings.
These are demo guardrails, not a complete compliance boundary.

## 7. CI cannot deploy; OIDC is future work

All active workflows are validation-only, including manual workflow runs and
scheduled checks. Team A has no deployment job, AWS credential action, OIDC-token
permission, GitHub environment prerequisite, or deployment activation variable
in its active workflow. Existing `AWS_ROLE_ARN`/`ENABLE_SANDBOX_DEPLOYMENT` settings
cannot activate a job that no longer exists; remove obsolete settings if desired.

The previous implementation is retained at Team A's
`future/oidc-deployment.yml.disabled`, outside `.github/workflows`, and its archived
deployment job additionally has `if: ${{ false }}`. Platform's
`scripts/team_a_access.py` and the change-set/readiness helper tests are retained
as future references. None is required for manual deployment; do not provision the
old access template for this interview.

Future OIDC deployment needs a new review of trust, limited deployment/execution
permissions, stack-owned policy management, artifact promotion and approvals.
The archived workflow and old `claims/` asset permissions require adaptation to the
current standard-bootstrap path. Simply renaming/re-enabling the archive is unsafe
and is not a supported setup instruction.

## 8. Deliberate manual cleanup

Before destruction, verify identity and the exact demo bucket/output names again.
List the specifically identified bucket. Only when you intend to delete that
synthetic demo data, empty it and destroy the application stack:

```bash
aws sts get-caller-identity --profile cdk-sso
aws s3 ls "s3://$CLAIMS_BUCKET/" --recursive --profile cdk-sso --region eu-central-1
# Destructive commands: run only after verifying this is the disposable Claims bucket.
aws s3 rm "s3://$CLAIMS_BUCKET/" --recursive --profile cdk-sso --region eu-central-1
cdk destroy ClaimsTeamStack --profile cdk-sso
```

Automatic object deletion is disabled. The current bucket is not versioned; if
versioning is introduced later, remove all versions/delete markers before stack
teardown. The stack-owned boundary is cleaned up with the application; this does
not delete shared bootstrap roles. Keep `CDKToolkit`. Check budget/billing before
deployment; this example does not promise a zero-dollar bill.

No bootstrap, deployment, IAM provisioning, fixture upload or teardown was executed
while implementing this final workflow. Live SSO permissions, deployment and logs
remain to be verified by the human-operated AWS demonstration.
