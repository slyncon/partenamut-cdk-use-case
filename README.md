# CDK Launchpad Platform

A small Python AWS CDK v2 developer-enablement demonstration. Platform owns two
reusable constructs; independent Claims and Medical Documents repositories own
application stacks and handlers. The interview workflow is **automated CI with
manual CD**: GitHub validates, then the developer reviews and deploys from WSL.
Application services are S3 and Lambda; IAM, logs, CloudFormation and bootstrap
resources support them.

## Repository ownership

```text
workspace/
├── partenamut-cdk-use-case/  # Existing local/Git Platform name, preserved
├── cdk-team-a/              # ClaimsTeamStack
└── cdk-team-b/              # MedicalDocumentsTeamStack
```

The local/Git names do not become AWS resource names. AWS names/tags remain generic;
existing stack and stateful construct IDs are preserved. There is no Platform
application stack to synthesize/deploy in this directory.

## Shared package and security

Distribution `cdk-launchpad`, version **0.1.2**; imports use `cdk_launchpad`.

- `SecureBucket`: SSE-S3, block all public access, enforce TLS, generated name, and
  demo-only DESTROY without automatic object deletion.
- `DocumentProcessor`: team's Python 3.12 handler, 128 MB, ten-second timeout,
  seven-day application logs, bucket read grant, direct `incoming/*.json` notifications.
- `cdk-launchpad-validate`: checks actual application templates for bucket encryption,
  all public-access flags, TLS and generic AWS identities/names/tags. It rejects
  insecure raw buckets too. Local paths and repository URLs are unaffected.

Both teams consume the tested release at an immutable source commit. Third-party
Python dependencies are hash-locked in Team A; action versions are full commit pins.
A new release does not automatically change an existing deployed stack.

## Local Platform validation

Prerequisites: Python 3.12, Node 24 LTS/npm, Git. AWS CLI v2 is needed only for the
human-operated cloud steps. Node runs CDK's Python bridge and CLI; handlers are Python.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m ruff check .
python -m pytest -q
python -m bandit -r src scripts -ll
python -m pip_audit --skip-editable
python -m build --wheel --outdir .build/dist
python -m pip install --force-reinstall --no-deps .build/dist/*.whl
cdk-launchpad-validate --help
python -m pytest -q
```

GitHub repeats tests/lint/scans, builds and installs the wheel, then retests it.
It has read-only repository permissions and no AWS credentials or deployment.
Vulnerability/secret scans complement tests; they do not prove complete security.
Virtual environments, dependencies, caches, generated assemblies and local assistant
instructions are ignored by Git.

## Interview target and deployment

Target account **117301763389**, region **eu-central-1**, IAM Identity Center
profile **cdk-sso**. Assume the profile is configured; authenticate with SSO rather
than creating IAM users/access keys. No GitHub AWS secrets or OIDC roles are required.

From a team directory with its environment and CDK CLI active:

```bash
aws sso login --profile cdk-sso
export AWS_REGION=eu-central-1
export AWS_DEFAULT_REGION=eu-central-1
aws sts get-caller-identity --profile cdk-sso
# One-time, manually; the target currently has no CDKToolkit stack.
cdk bootstrap aws://117301763389/eu-central-1 --profile cdk-sso --termination-protection
cdk diff ClaimsTeamStack --profile cdk-sso --change-set false
cdk deploy ClaimsTeamStack --profile cdk-sso
```

Confirm the account and wait for successful CI before deployment. The default
synthesizer uses standard CDK bootstrap roles; no deleted custom execution role
or external boundary policy is needed. Team A creates its runtime boundary inside
its stack, so application restrictions remain while IAM provisioning is self-contained.
Default bootstrap execution privileges are broader than the archived scoped role;
this is a sandbox demonstration, not production deployment isolation.

[DEPLOYMENT.md](DEPLOYMENT.md) gives the full checks, first bootstrap, upload/log
commands, account guards, replacement-risk review, permission requirements and cleanup.
Do not destroy CDKToolkit. No cloud commands were executed during this update.

## Releases and progressive adoption

Platform tests/scans/builds changes, publishes a matching version/tag at the tested
commit, and announces the full commit in release notes. Each team manually updates
its source pin, validates, reviews the live diff and deploys independently. Do not
move released tags. See [MIGRATION.md](MIGRATION.md) for ownership/release details.

Required PR checks and reviews must be configured in GitHub; CODEOWNERS alone is
not enforcement. Keep workflow/dependency/security-policy changes reviewable.
Future OIDC automation is archived outside the active workflow and is a proposal
requiring revised IAM permissions and validation before restoration. Current CI
cannot bootstrap, deploy or destroy resources.

## Short demo story

The Claims team chooses Platform's secure bucket and processor, supplies its own
handler, and proposes infrastructure in its own repository. CI rejects insecure
configuration and verifies the application. The developer reviews the diff and
manually deploys using SSO. Uploading a fictional claim causes a read/validate/log
result. Medical Documents reuses the same components independently. Platform
maintains standards without writing every team's resources.
