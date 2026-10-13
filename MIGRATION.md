# Repository ownership and versioned consumption

```text
partenamut-business-case/
├── partenamut-cdk-use-case/   # Platform library, shared security checks, AWS access setup
├── cdk-team-a/               # Claims application; automated-deployment pilot
└── cdk-team-b/               # Medical documents application; validation-only CI
```

These are three independent repositories, not branches of one repository.
The duplicate platform copy and old teams workspace were removed. The existing
Platform repository and Git history were retained. No fourth repository is needed.

Both teams install the same Python distribution, `cdk-launchpad`, and import the
same two constructs. Team A selects Platform 0.1.1; Team B retains 0.1.0.
Both source dependencies are pinned to full commit IDs, so moving a tag cannot
change the installed code. Team A additionally locks third-party dependencies
and their hashes. Each repository owns its local environment and tooling.
Environments, node_modules, caches, CDK assets, credentials, and local assistant
instructions stay out of Git.

## Platform release order

1. Update the package version and release notes; run tests, lint, security scans,
   and the package build/install check.
2. Commit and push; confirm the hosted `Validate platform` check passes.
3. Tag that tested commit with the matching version, then push the new tag.
4. A consumer updates its full source commit, reviews dependency/lock changes,
   validates, and adopts independently. Other consumers keep their chosen version.

For example, from Platform after the corresponding tested commit exists:

```bash
git tag -a v0.1.1 -m "Platform 0.1.1: S3 TLS policy validation"
git push origin v0.1.1
```

Do not move published tags. Protect release tags or enable immutable releases in
GitHub. Full source pins already protect consumer installations, even before those
server-side release settings are configured. All CI actions are also pinned to
full commits; dependency updates should be proposed and validated, not silently
applied during builds.

## Deployment account change

Team A will deploy to a **new personal AWS account**, configured through GitHub
`sandbox` environment variables. Its corporate sandbox stack is separate and
remains untouched. The account and deployment role have not yet been supplied;
no resources are created automatically as part of this preparation.

Stack names and bucket/function construct IDs are preserved. A different AWS
account/region means a separate deployment, even with the same stack name.
No corporate data is copied, deleted, or required for the new account.

See [DEPLOYMENT.md](DEPLOYMENT.md) for one-time personal-account bootstrap/IAM/OIDC
setup, GitHub protections, credentials, and the two-job workflow. Team A's README
provides local validation, fixture uploads, logs and deliberate manual teardown.

## Security demonstration

From a configured Team A development environment:

```bash
python scripts/security_demo.py secure
cdk-launchpad-validate .build/security-demo
python scripts/security_demo.py insecure
cdk-launchpad-validate .build/security-demo
```

The insecure command deliberately exits 1. Correct by rerunning `secure` and the
check. Never deploy `SecurityDemo`. For a visible failing PR, temporarily add the
insecure command/check as a workflow step on a demonstration branch; correct it
to show green, then remove that temporary step. Do not merge an intentional failure.

A claim fixture is fictional JSON containing a fake ID, category and amount.
Processing means reading, validating and logging; it does not approve or pay a
claim. The second team processes fictional document metadata. Both handlers are
read-only and safe to repeat when S3 delivers duplicate events.
