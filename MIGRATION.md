# Three repositories, one shared library

```text
partenamut-business-case/
├── partenamut-cdk-use-case/   # Platform library and security validator
├── cdk-team-a/               # ClaimsTeamStack and synthetic claims handler
└── cdk-team-b/               # MedicalDocumentsTeamStack and metadata handler
```

These are three independent Git repositories on `main`, owned by `slyncon` on
GitHub. Team A and Team B are repositories, not branches of Platform. The duplicate
`cdk-launchpad-platform/` and old `teams/` workspace are retired. The existing
Platform Git history and remote are retained; a fourth repository is unnecessary.

## Release and validation order

Validate Platform first using its README, commit the library and shared validator,
and push `main`. Create and push the first tag matching `project.version`:

```bash
git tag -a v0.1.0 -m "Platform 0.1.0"
git push origin v0.1.0
```

Both teams' `requirements.txt` consume
`cdk-launchpad @ git+https://github.com/slyncon/partenamut-cdk-use-case.git@v0.1.0`.
They install the package from GitHub rather than an editable sibling directory.
No registry or AWS authentication is involved. Each owns its environment, pinned
CDK CLI, workflow, handler, and tests. From either team directory:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
npm ci
export PATH="$PWD/node_modules/.bin:$PATH"
python -m ruff check .
python -m pytest -q
cdk ls
cdk synth
cdk-launchpad-validate .build/cdk.out
```

Push each team's code after its checks pass. The workflows validate on PRs to
`main` and pushes to `main`; they do not bootstrap, deploy, or access AWS.
Platform's job builds and tests the installed wheel; each team's job installs the
tagged dependency, tests, synthesizes, and runs the installed shared validator.

Keep release tags immutable. For a future release, update the Platform version,
test/build, commit, and publish a matching new tag. A team can update its own
dependency and deploy independently while the other team retains its old version.

## Demonstrate the security gate

From either team, after setup:

```bash
python scripts/security_demo.py secure
cdk-launchpad-validate .build/security-demo

python scripts/security_demo.py insecure
cdk-launchpad-validate .build/security-demo
```

The secure check exits 0. The intentionally insecure raw bucket is rejected with
exit 1 for missing explicit encryption and public-access flags. Rerun `secure`
and the check to show the correction. These files are ignored local synth output;
**never deploy `SecurityDemo`**. The normal team app is unchanged.

To demonstrate a red Actions check, add this temporary workflow step on a new
demonstration branch and open a PR to `main`:

```yaml
      - name: Demonstrate insecure bucket rejection
        run: |
          python scripts/security_demo.py insecure
          cdk-launchpad-validate .build/security-demo
```

Change `insecure` to `secure`, commit, and push the correction to show green.
Remove the temporary step afterward. Negative unit tests remain green because
they assert that insecure input is rejected. Do not merge the deliberate failure.

After the first successful hosted runs, configure `main` branch protection to
require PR review and the respective `Validate platform` or `Validate team` check.
Protection settings and a demonstration PR are not configured automatically.

## Manual AWS work starts in Team A

There is no Platform stack to deploy. Use the team README's existing
`partenamut-sso` profile and `eu-central-1` region instructions. Stack names,
construct IDs, outputs, shared constructs, handler code, and CDK dependency pins
are preserved. Moving a directory does not create a new CloudFormation stack.
The bucket logical ID remains `DocumentsBucket089EA665` and the application
function remains `ProcessorFunction5B2A90E2` in each independent stack.

```bash
export AWS_REGION=eu-central-1
export AWS_DEFAULT_REGION=eu-central-1
aws sts get-caller-identity --profile partenamut-sso
cdk diff ClaimsTeamStack --profile partenamut-sso
```

Review the diff before the team README's manual deployment. Stop if the existing
bucket would be removed or replaced unexpectedly. Local synthesis cannot prove
the absence of live drift. No AWS resource deletion is needed to reorganize Git
repositories, even for this first version.

After deployment, upload the tiny fixture to the bucket output's `incoming/`
prefix and read the log output. A mock claim is a JSON document containing a fake
claim ID, category, and amount. Processing means read, validate, and log a result;
it does not approve a claim or pay money. Team B processes fictional document
metadata. Neither handler writes to S3, so duplicate events are safe to repeat.

Teardown is human-operated: verify the account and actual demo bucket name, empty
that bucket, then destroy the team stack. Do not destroy shared `CDKToolkit`.
Git cleanup and local tests do not verify a live deployment, fixture delivery,
CloudWatch output, or teardown from these checkouts.
