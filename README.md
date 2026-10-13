# CDK Launchpad

A Python AWS CDK v2 proof of concept for Partenamut's **AWS CDK Developer Enablement**
business case. Cloud Platform provides reusable infrastructure components so
simulated development teams can define and deploy their own resources with shared
security defaults and local validation.

This repository contains the **platform library, tests, and validation tooling**.
The Claims and Medical Documents applications are separate projects in the sibling
`../teams/` workspace. They are not included in this Git repository or downloaded
automatically. A fresh clone can validate the platform independently; the complete
AWS demonstration requires those separately supplied consumer projects.

## Architecture

```text
             Shared Python CDK constructs
               /                     \
      ClaimsTeamStack          MedicalDocumentsTeamStack
             |                        |
       private S3 bucket        private S3 bucket
             |                        |
       incoming/*.json          incoming/*.json
             |                        |
       Claims Lambda            Medical metadata Lambda
             |                        |
       application logs         application logs
```

S3 and Lambda are the application services. IAM, CloudFormation, CloudWatch Logs,
and CDK bootstrap resources support deployment and operation. Each team has its
own stack, handler, bucket, and application log group; neither references the
other team's resources. Team isolation is simulated through code and stacks,
not separate AWS identities or accounts.

### Shared constructs

- **`SecureBucket`** creates an S3 bucket with SSE-S3 encryption, all four
  public-access blocks, and a policy denying insecure transport. AWS generates
  its name. Its demo-only `DESTROY` policy requires manually emptying the bucket
  before deletion; automatic object deletion is disabled.
- **`DocumentProcessor`** accepts a bucket, team label, and handler directory. It
  creates a Python 3.12 Lambda with 128 MB memory, a ten-second timeout, and
  seven-day application log retention. It grants read access to the supplied
  bucket and registers direct ObjectCreated notifications filtered to
  `incoming/` keys ending in `.json`.

CDK generates an additional helper Lambda/custom resource to configure S3
notifications. It is supporting deployment infrastructure, so total Lambda
resource counts include more than the team's application processor.

The consumer stacks export `BucketName`, `FunctionName`, and `LogGroupName` and
apply project, environment, and team tags. They consume this library through a
local editable dependency (`-e ../../partenamut-cdk-use-case`). Nothing is published
to a package registry.

## Repository structure

```text
src/cdk_launchpad/
  constructs/secure_bucket.py
  constructs/document_processor.py
  security.py                     synthesized-template guardrail
scripts/validate_synth.py          validation CLI
tests/                           platform contract and security tests
pyproject.toml                    package metadata and pytest/Ruff settings
requirements*.txt                 editable installation and development tools
package.json / package-lock.json  pinned CDK CLI
.github/workflows/validate.yml    platform validation only
```

In the complete local workspace, the consumer projects are arranged separately:

```text
workspace/
├── partenamut-cdk-use-case/       this repository
└── teams/
    ├── teamA/                    ClaimsTeamStack
    └── teamB/                    MedicalDocumentsTeamStack
```

Each consumer owns `app.py`, `cdk.json`, `stack.py`, `handler/`, `fixtures/`, and
`tests/`. Run CDK commands inside a consumer directory; this library repository
has no root CDK application.

## Prerequisites and installation

Use Python **3.12**, Node.js **24 LTS**, npm, Git, and a Bash-compatible shell.
AWS CLI v2 and a working SSO profile are needed only for manual AWS operations.

Node.js is required by the CDK CLI and the Python CDK language bridge, jsii.
Infrastructure definitions and application handlers remain Python.
See [the AWS Python CDK guide](https://docs.aws.amazon.com/cdk/v2/guide/work-with-cdk-python.html).

From this repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
npm ci
export PLATFORM_DIR="$PWD"
export PATH="$PLATFORM_DIR/node_modules/.bin:$PATH"
```

For an existing environment, activate `.venv` rather than recreating it.
Python dependency pins are in `pyproject.toml` and `requirements-dev.txt`; the CDK
CLI is pinned in the npm manifest and lockfile. The CLI and Python CDK library
use different version sequences. boto3 is installed for local tests; deployed
handlers use boto3 supplied by the managed Lambda Python runtime.

`.venv/`, `node_modules/`, caches, generated assemblies, and local authentication
files are ignored. They can be recreated from project configuration.

## Local validation

The platform checks need no AWS credentials:

```bash
python -m pytest -q
python -m ruff check .
```

Tests synthesize temporary stacks and assert encryption, public-access blocking,
TLS denial, Lambda settings, log retention, S3 notification wiring, scoped read
permissions, and outputs. Security tests also synthesize an insecure raw bucket
to prove that bypassing `SecureBucket` is detected.

When the external consumer workspace is available, validate both applications:

```bash
(cd ../teams/teamA && python -m pytest -q && cdk synth)
(cd ../teams/teamB && python -m pytest -q && cdk synth)
python scripts/validate_synth.py \
  ../teams/teamA/.build/cdk.out ../teams/teamB/.build/cdk.out
```

These credential-free synthesis commands intentionally omit a profile. With an
already configured profile, the CLI may make read-only account-resolution calls.
The apps perform no synthesis-time resource lookups. Each saves its template and
Lambda assets in its own `.build/cdk.out/` directory.

The guardrail examines every S3 bucket in each supplied application's templates
and rejects missing explicit encryption or any public-access flag that is not
literal `true`. Violations and missing assemblies cause a nonzero exit code.
This is a demo guardrail, not a complete security boundary; `cdk deploy` does not
automatically run it. Always synthesize and validate after infrastructure changes.

GitHub Actions runs the platform's Ruff and pytest checks, including construct
synthesis and security tests. It requires no AWS credentials and never deploys.
External consumer applications are not part of that workflow.

## AWS SSO and manual deployment

The documented sandbox target is account **851725255087**, deployment region
**`eu-central-1`**, and CLI profile **`partenamut-sso`**. The profile's SSO
authentication region is **`eu-west-1`**. Application code resolves the account
and region through the CDK CLI environment.

Use your existing configured profile. Sign in or refresh its session if needed,
then verify the returned account before creating resources:

```bash
aws sso login --profile partenamut-sso
aws sts get-caller-identity --profile partenamut-sso
export AWS_REGION=eu-central-1
export AWS_DEFAULT_REGION=eu-central-1
```

See [AWS CLI SSO authentication](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html).
No access keys or local AWS configuration belong in this repository.
Check sandbox billing/budget before deployment; small fixtures and short application
log retention do not guarantee a zero-dollar bill.

With the external consumer source available, start with Claims:

```bash
cd "$PLATFORM_DIR/../teams/teamA"
cdk ls --profile partenamut-sso
cdk synth --profile partenamut-sso
python "$PLATFORM_DIR/scripts/validate_synth.py" .build/cdk.out

# Creates supporting deployment resources once per account/region, if needed.
cdk bootstrap --profile partenamut-sso

# Review changes, then manually deploy this team.
cdk diff ClaimsTeamStack --profile partenamut-sso
cdk deploy ClaimsTeamStack --profile partenamut-sso
```

Skip bootstrapping if this account/region already has a compatible `CDKToolkit`
stack. It supplies asset storage and deployment roles. Review CDK's permission
prompt before deploying. Diff may create a temporary CloudFormation change set.

To deploy Medical Documents later, enter `../teamB`, synthesize and validate its
assembly, then run `cdk diff MedicalDocumentsTeamStack --profile partenamut-sso`
and `cdk deploy MedicalDocumentsTeamStack --profile partenamut-sso`. Claims is
not a dependency of that stack.

## Exercise the deployed Claims application

The synthetic fixture represents a fictional dental reimbursement request:

```json
{"claim_id": "CLAIM-001", "category": "dental", "amount_eur": 45.50}
```

Read the deployed outputs, then set `CLAIMS_BUCKET` and `CLAIMS_LOG_GROUP` to the
actual `BucketName` and `LogGroupName` values:

```bash
aws cloudformation describe-stacks --stack-name ClaimsTeamStack \
  --query 'Stacks[0].Outputs' --output table \
  --profile partenamut-sso --region eu-central-1

CLAIMS_BUCKET="<BucketName from outputs>"
CLAIMS_LOG_GROUP="<LogGroupName from outputs>"

# Uploads one synthetic document to the team's bucket.
aws s3 cp fixtures/claim.json "s3://$CLAIMS_BUCKET/incoming/claim.json" \
  --profile partenamut-sso --region eu-central-1
aws logs tail "$CLAIMS_LOG_GROUP" --since 10m \
  --profile partenamut-sso --region eu-central-1
```

Notifications are asynchronous; wait briefly and repeat the log read if needed.
Expected application message:

```json
{"team": "claims", "document_id": "CLAIM-001", "result": "processed"}
```

The handler reads and validates JSON and logs the synthetic ID, team, and result.
It does not assess coverage or issue payments, log the complete document, or write
objects back to S3. Duplicate/out-of-order notifications are possible; read-only
processing is safe to repeat. Invalid inputs raise errors. This MVP has no durable
failure queue or dead-letter design. Never upload real insurance or medical data.

## Manual cleanup

The demo bucket must be empty before stack deletion. Verify the account, compare
the bucket variable with the deployed output, and inspect its contents:

```bash
aws sts get-caller-identity --profile partenamut-sso
aws cloudformation describe-stacks --stack-name ClaimsTeamStack \
  --query 'Stacks[0].Outputs' --output table \
  --profile partenamut-sso --region eu-central-1
aws s3 ls "s3://$CLAIMS_BUCKET/" --recursive \
  --profile partenamut-sso --region eu-central-1
```

Only after confirming it is the disposable demo bucket:

```bash
# Destructive: empty the specifically verified demo bucket first.
aws s3 rm "s3://$CLAIMS_BUCKET/" --recursive \
  --profile partenamut-sso --region eu-central-1
cdk destroy ClaimsTeamStack --profile partenamut-sso
```

Use the same verified-bucket sequence for Medical Documents before destroying its
stack. Application log groups are removed with their stacks. For meaningful data,
`RETAIN` would normally be safer than this demo's `DESTROY` policy.

Keep the shared `CDKToolkit` stack. Bootstrap assets and notification-helper logs
may remain under the sandbox owner's shared-infrastructure lifecycle.

## Troubleshooting and limitations

- Import error: activate `.venv` and reinstall the editable platform package.
- Missing CDK command: run root `npm ci` and add its `node_modules/.bin` to `PATH`.
- Missing consumer project: obtain the separate teams workspace; this repository
  alone supplies the library and platform validation.
- Missing assembly: synthesize the selected team before running the validator.
- No processing log: check output names, region, notification delay, the exact
  `incoming/` prefix and `.json` suffix, and Lambda errors.
- Nonempty bucket deletion failure: verify and empty that demo bucket, then retry.

This interview MVP demonstrates reusable defaults and independent team stacks.
Production team IAM isolation, automated deployment controls, versioned package
distribution, and durable failure handling are outside its scope. Local validation
checks code and templates; live notifications, reads, logs, and teardown require
manual AWS verification.
