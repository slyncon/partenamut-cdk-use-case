# CDK Launchpad Platform

Reusable Python AWS CDK v2 components for Partenamut's AWS CDK Developer Enablement
interview case. Independent team repositories consume a tagged version of this
library and provide their own application handlers. Application services are S3
and Lambda; IAM, CloudFormation, logs, and bootstrap infrastructure support them.

## Package and contracts

- Distribution: **`cdk-launchpad`**, version **`0.1.0`** in `pyproject.toml`.
- Imports: `from cdk_launchpad.constructs import SecureBucket, DocumentProcessor`.
- `SecureBucket`: SSE-S3, all public-access blocks, TLS enforcement, generated name,
  demo-only `DESTROY` policy requiring manual emptying; no automatic object deletion.
- `DocumentProcessor`: the consumer's Python 3.12 handler, 128 MB, ten-second timeout,
  seven-day application logs, read access to its bucket, and direct S3 notifications
  filtered to `incoming/*.json`. CDK also generates a notification helper.
- Installed CLI: `cdk-launchpad-validate <assembly-directory> [other-directories...]`.
  `python -m cdk_launchpad.cli` is equivalent. It checks every application bucket,
  including those that bypass the construct, and exits 1 with resource-specific
  errors for missing encryption/public-access blocking. This is a demo guardrail,
  not a complete security boundary.

Source lives in `src/cdk_launchpad/`; tests in `tests/`. The optional
`scripts/validate_synth.py` is a thin compatibility wrapper, not another checker.
No team code or deployment app is included in this repository. The retained
`package.json`/lockfile pin the optional local CDK CLI; each team installs its own CLI.
Virtual environments, caches, dependencies, generated templates, and local assistant
instructions are ignored by Git and are not part of the published package.

## Local validation and package build

Prerequisites: Python 3.12, Node 24 LTS, Git. Node runs the CDK Python language
bridge. No AWS credentials are required.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m ruff check .
python -m pytest -q
python -m build --wheel --outdir .build/dist
python -m pip install --force-reinstall --no-deps .build/dist/*.whl
cdk-launchpad-validate --help
python -m pytest -q
```

`.github/workflows/ci.yml` repeats lint/tests, builds the wheel, installs it, and
retests it on PRs targeting `main` and pushes to `main`. It uses `contents: read`
and standard Ubuntu runners, and never authenticates to AWS or deploys.

## Versioned consumption

Teams install the tagged source from the existing Platform repository:

```text
cdk-launchpad @ git+https://github.com/slyncon/partenamut-cdk-use-case.git@v0.1.0
```

The Platform repository is [slyncon/partenamut-cdk-use-case](https://github.com/slyncon/partenamut-cdk-use-case).
Git is required by pip; no package registry or AWS access is needed.
See [pip VCS dependencies](https://pip.pypa.io/en/stable/topics/vcs-support/).

To release `0.1.1`, update `project.version`, validate/build, commit the change,
and create/push a new `v0.1.1` tag. Keep existing release tags immutable. A team can
change only its own dependency ref to `@v0.1.1`, reinstall with `--upgrade`, run CI
checks and `cdk diff`, and deploy manually. Other teams can remain on `v0.1.0`.
A full commit SHA may be used for stronger immutable dependency pinning.

See **[MIGRATION.md](MIGRATION.md)** for the three-repository layout, release order,
CI security demonstration, and deployment compatibility checks.

## Deployment and scope

This library repository has no AWS stack to deploy or destroy. Teams independently
run their own CDK apps using `partenamut-sso`, account `851725255087`, and
`eu-central-1`. SSO authentication is in `eu-west-1`.

Branch protection should require the `Validate platform` check after its first
successful run. Require PR review, current passing checks, and restrict bypass,
force pushes, and branch deletion where supported. GitHub Free supports protected
branches on public repositories; availability for private repositories depends
on the plan. See [GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

Standard GitHub-hosted runners for public repositories are free; private repositories
have plan-specific allowances. See [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

Deployment automation is future work: a protected deployment workflow could later
use GitHub OIDC with a narrowly scoped AWS trust policy and deployment role, plus
review/approval controls. This phase implements no OIDC, AWS keys, Secrets, or
automated deployment. Team identities/accounts are still simulated, not isolated.
