"""Demo guardrail for explicit S3 encryption and public-access blocking."""

import json
from pathlib import Path

PUBLIC_ACCESS_FLAGS = (
    "BlockPublicAcls",
    "BlockPublicPolicy",
    "IgnorePublicAcls",
    "RestrictPublicBuckets",
)


def validate_template(template: dict) -> list[str]:
    """Check every bucket, including resources created without SecureBucket."""
    errors = []
    for logical_id, resource in template["Resources"].items():
        if resource["Type"] != "AWS::S3::Bucket":
            continue
        properties = resource.get("Properties", {})
        encryption = properties.get("BucketEncryption", {})
        rules = encryption.get("ServerSideEncryptionConfiguration", [])
        if not rules or not all(
            rule.get("ServerSideEncryptionByDefault", {}).get("SSEAlgorithm")
            in ("AES256", "aws:kms", "aws:kms:dsse")
            for rule in rules
        ):
            errors.append(f"{logical_id}: explicit BucketEncryption is required")
        block = properties.get("PublicAccessBlockConfiguration", {})
        for flag in PUBLIC_ACCESS_FLAGS:
            if block.get(flag) is not True:
                errors.append(f"{logical_id}: {flag} must be true")
    return errors


def validate_assembly(directory: Path) -> int:
    """Read actual application stack templates selected by CDK's manifest."""
    manifest = json.loads((directory / "manifest.json").read_text())
    stacks = [
        artifact
        for artifact in manifest["artifacts"].values()
        if artifact["type"] == "aws:cloudformation:stack"
    ]
    if not stacks:
        raise ValueError("No application stacks found; run cdk synth first")
    errors = []
    for stack in stacks:
        filename = stack["properties"]["templateFile"]
        template = json.loads((directory / filename).read_text())
        errors.extend(f"{filename}: {error}" for error in validate_template(template))
    if errors:
        raise ValueError("\n".join(errors))
    return len(stacks)
