# Final interview ownership and deployment approach

Three sibling repositories remain: `partenamut-cdk-use-case` (Platform),
`cdk-team-a` (Claims), and `cdk-team-b` (Medical Documents). Local directories,
GitHub repository names and Python package imports are unchanged. Do not recreate
the retired duplicate Platform directory or old teams workspace.

## Automated CI, manual CD

All active workflows validate only. Team A's prior deployment workflow is archived
outside `.github/workflows` with its deployment job also disabled unconditionally.
Neither GitHub variables nor a workflow_dispatch event can activate AWS deployment
in the active interview pipeline. Developer workflow training and future OIDC
rollout remain later phases.

The interview target is account `117301763389`, region `eu-central-1`, profile
`cdk-sso`, authenticated through IAM Identity Center. Bootstrap is a one-time
human operation; application deployment uses the standard bootstrap roles.
Read [DEPLOYMENT.md](DEPLOYMENT.md) before cloud operations.

## IAM dependency adaptation

The deleted custom role and imported boundary ARN no longer appear in Team A's
active app. Its permissions boundary remains, but is now created/managed inside
ClaimsTeamStack and checked for equivalent narrow runtime permissions. CI expects
standard deployment/execution/publishing roles instead of the deleted role and
`claims/` bootstrap asset convention. The runtime boundary does not restrict the
human administrator or the broad default bootstrap execution role.

No bucket/function identity was renamed. New managed-policy creation, runtime
boundary references and asset key changes must be reviewed in any existing stack's
diff. No AWS changes, role deletions or data migrations were performed by this work.

## Versioning

Platform 0.1.2 adds generic AWS naming validation while preserving the same two
constructs and their defaults. Both consumers explicitly adopt its tested full
source commit. This also gives Team B the shared TLS template gate introduced
in 0.1.1; its application already enforced TLS through SecureBucket.

Release order: update version and tests, validate/build/scan, commit and push,
confirm Platform CI, tag that tested commit, then update consumer pins and validate.
Tags are human-readable labels; immutable source commits determine installed code.
Never move a published tag. Team A's third-party hash lock does not need regeneration
when Platform's dependency set is unchanged. Review any actual lock/dependency changes.

## Naming and scope

AWS stack/resource identities, name properties and tags must be generic. The shared
validator catches the interview company name in those fields, including raw
resources. It does not reject the preserved local directory/repository name or
metadata paths. Use generated names to avoid global collisions; review replacement
risks instead of renaming existing deployed resources casually.

The application still uses S3 and Lambda only. IAM/Logs/CloudFormation/bootstrap
are supporting resources. Fixtures are fictional; handlers read, validate and log,
never write into the triggering prefix or claim exactly-once processing.

## Future deployment reference

Platform's IAM/OIDC generator and Team A's archived workflow/change-set helpers
remain reviewable examples. They are not required for the interview. Reintroducing
OIDC requires explicit authorization, protected environments, scoped IAM compatible
with stack-owned boundary creation and the selected synthesizer, artifact promotion,
and a live deployment proof. See Team A's `future/README.md` for the archive limits.
