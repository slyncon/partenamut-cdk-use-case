# Team A automated sandbox deployment

Team A is the pilot. Platform maintains its AWS deployment access, while Team A
owns the application pipeline. Team B remains validation-only on Platform 0.1.0.
The two application services remain S3 and Lambda. New resources are supporting
IAM/OIDC access controls, not an additional application service.

## Credentials: temporary identity, no stored AWS keys

Your laptop keeps using `partenamut-sso` for the initial setup. GitHub uses OIDC:
GitHub identifies a job to AWS, and AWS issues temporary credentials for that job.
Do not copy access keys, SSO tokens, or `~/.aws` files into GitHub or the repository.
Only the deployment job can request an OIDC token; validation has no AWS access.

GitHub's trust is limited to the exact Team A repository and `sandbox` environment.
This repository was created after GitHub introduced immutable OIDC subjects, so
its owner and repository IDs are included. The subject is:

```text
repo:slyncon@15962517/cdk-team-a@1417529910:environment:sandbox
```

The GitHub environment must restrict deployment branches to `main`. The subject
identifies the environment; that branch restriction supplies the branch control.
Do not weaken trust to `repo:slyncon/*` or a wildcard environment.

## One-time Platform setup

The existing account/region is already bootstrapped. Do not change or replace the
shared `CDKToolkit` stack. From Platform, generate and inspect the access template:

```bash
source .venv/bin/activate
python scripts/team_a_access.py \
  --subject 'repo:slyncon@15962517/cdk-team-a@1417529910:environment:sandbox'
aws sts get-caller-identity --profile partenamut-sso
aws cloudformation validate-template --template-body file://.build/team-a-access.json \
  --profile partenamut-sso --region eu-central-1
```

The first setup creates a GitHub OIDC provider, two roles, and a runtime permissions
boundary. This template expects no existing GitHub provider. If one already exists,
stop and adapt the template to reference the existing provider rather than creating
or taking ownership of it. Generated templates and account-specific outputs are
ignored by Git.

Review the template before the following human-operated setup command:

```bash
aws cloudformation deploy --stack-name CDKLaunchpadTeamAAccess \
  --template-file .build/team-a-access.json --capabilities CAPABILITY_NAMED_IAM \
  --profile partenamut-sso --region eu-central-1
aws cloudformation describe-stacks --stack-name CDKLaunchpadTeamAAccess \
  --query 'Stacks[0].Outputs' --output table \
  --profile partenamut-sso --region eu-central-1
```

For an existing Claims stack, attach the new `LambdaBoundaryArn` output to its
existing Lambda roles before enabling GitHub deployment. List the exact roles:

```bash
aws cloudformation list-stack-resources --stack-name ClaimsTeamStack \
  --query "StackResourceSummaries[?ResourceType=='AWS::IAM::Role'].PhysicalResourceId" \
  --output table --profile partenamut-sso --region eu-central-1
```

For each specifically verified Claims role, use the boundary output ARN:

```bash
aws iam put-role-permissions-boundary --role-name '<verified-Claims-role>' \
  --permissions-boundary '<LambdaBoundaryArn-output>' --profile partenamut-sso
```

This narrows existing role permissions immediately; the updated app subsequently
records the same boundaries in CloudFormation. It is a one-time migration step.
Do not apply the boundary to your SSO identity, bootstrap roles, deployment role,
or another team's roles.

## GitHub configuration, step by step

In **cdk-team-a → Settings → Environments**:

1. Create `sandbox`.
2. Under deployment branches/tags, select specific branches and allow only `main`.
3. Add environment **variables**, not secrets:
   - `AWS_ACCOUNT_ID`: the account returned by your identity check.
   - `AWS_REGION`: `eu-central-1` (deployment region, not the SSO authentication region).
   - `AWS_ROLE_ARN`: the `GitHubRoleArn` output above.
4. Optionally add a required reviewer to pause before deployment. For a solo sandbox
   demo this can be omitted; automatic deployment still remains limited to `main`.

In **Settings → Rules / Branches**, protect `main`: require pull requests and the
`Validate team` check, disallow force pushes/deletion, and restrict bypass where
supported. Require CODEOWNERS review of workflows, dependency pins, and deployment
scripts when another reviewer is available. A solo author cannot approve their own
PR. CODEOWNERS files describe ownership; settings make those reviews mandatory.

Apply equivalent protection to Platform and its `Validate platform` check. Protect
published release tags against update/deletion or use GitHub immutable releases.
Git access alone cannot configure these settings; verify them in GitHub.

## What happens when Team A runs

A PR runs validation and never deploys. A push to `main`, or **Actions → CI and
sandbox deployment → Run workflow** on `main`, runs validation and then a separate
`Deploy Claims sandbox` job. Weekly scheduled scans never deploy.

Validation installs the platform at a full commit SHA and verifies hashes of locked
third-party packages. It runs Ruff, pytest, Bandit, pip-audit, npm audit, Gitleaks,
S3 encryption/public-access/TLS policy checks, and the Claims-specific boundary and
resource checks. Vulnerability auditing contacts public advisory databases; local
unit tests and synthesis remain credential-free.

The job uploads the synthesized assembly and records its SHA-256 manifest. Deployment
checks those hashes, rechecks infrastructure policy, and deploys that assembly
without resynthesizing. It obtains AWS credentials only after dependency installation
and local validation. Artifacts expire after seven days.

Deployment then prints a diff and creates a CloudFormation change set without
executing it. A check rejects S3 bucket removal, replacement, or uncertain replacement.
A safe change set is executed; an empty one is reported as no change. Deployments
are serialized and an in-flight deployment is not cancelled by a newer push.
The Actions summary records the source commit and actual stack outputs.

The first update adds boundaries and changes handler asset keys to the scoped
`claims/` bootstrap prefix. Bucket/function logical IDs remain stable. Review the
first diff: those changes are expected; bucket replacement is not.

## AWS permission limits

`CDKLaunchpad-TeamA-GitHubDeploy` can prepare/execute Claims change sets, upload only
`claims/` assets in the existing bootstrap bucket, and pass only the dedicated Claims
CloudFormation role. It cannot assume shared bootstrap admin roles or destroy stacks.

`CDKLaunchpad-TeamA-CloudFormation` manages Claims-prefixed S3/Lambda/log resources
and Claims Lambda roles. New Lambda roles must carry the specified boundary. Runtime
roles are capped at reading Claims `incoming/` objects, writing Claims logs, and the
notification helper's Claims bucket-notification operations. There is no application
S3 object write permission. CDK's helper may request broader identity permissions,
but the boundary limits their effective access.

This is a sandbox control set, not organization-wide enforcement. Maintainers can
change repository code or AWS policies. Required protected reviews are necessary to
protect checks from being removed. The custom policy checker handles the current
flat application templates, not arbitrary nested stacks or all AWS security rules.
The change-set check prevents bucket replacement, but cannot judge every business or
application change. No scanner guarantees that all vulnerabilities or secrets are
found. Teardown remains deliberate and manual; pipeline jobs never empty buckets.
