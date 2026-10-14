"""Demo guardrail for explicit S3 encryption, public-access blocking and TLS."""

import json
from pathlib import Path

PUBLIC_ACCESS_FLAGS = (
    "BlockPublicAcls",
    "BlockPublicPolicy",
    "IgnorePublicAcls",
    "RestrictPublicBuckets",
)


def validate_resource_names(template: dict) -> list[str]:
    """Keep AWS identities/tags generic; local paths and metadata are unaffected."""
    errors = []

    def check_fields(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}"
                if (key.endswith("Name") or key == "Tags") and "partenamut" in json.dumps(
                    child
                ).casefold():
                    errors.append(f"{child_path}: AWS names and tags must be generic")
                check_fields(child, child_path)
        elif isinstance(value, list):
            for child in value:
                check_fields(child, path)

    for logical_id, resource in template["Resources"].items():
        if "partenamut" in logical_id.casefold():
            errors.append(f"{logical_id}: AWS resource identities must be generic")
        check_fields(resource.get("Properties", {}), logical_id)
    return errors


def enforces_tls(template: dict, bucket_id: str) -> bool:
    """Require a deny covering the bucket and objects for every insecure principal."""
    arn = {"Fn::GetAtt": [bucket_id, "Arn"]}
    objects = {"Fn::Join": ["", [arn, "/*"]]}
    for resource in template["Resources"].values():
        if resource["Type"] != "AWS::S3::BucketPolicy":
            continue
        properties = resource.get("Properties", {})
        if properties.get("Bucket") != {"Ref": bucket_id}:
            continue
        for statement in properties.get("PolicyDocument", {}).get("Statement", []):
            actions = statement.get("Action", [])
            resources = statement.get("Resource", [])
            transport = statement.get("Condition", {}).get("Bool", {}).get("aws:SecureTransport")
            if (
                statement.get("Effect") == "Deny"
                and statement.get("Principal") in ("*", {"AWS": "*"})
                and (actions == "s3:*" or isinstance(actions, list) and "s3:*" in actions)
                and (transport is False or transport == "false")
                and arn in resources
                and objects in resources
            ):
                return True
    return False


def validate_template(template: dict) -> list[str]:
    """Check every bucket, including resources created without SecureBucket."""
    errors = validate_resource_names(template)
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
        if not enforces_tls(template, logical_id):
            errors.append(
                f"{logical_id}: bucket policy must deny non-TLS access to bucket and objects"
            )
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
        stack_name = stack.get("properties", {}).get("stackName", "")
        if "partenamut" in f"{filename} {stack_name}".casefold():
            errors.append(f"{filename}: AWS stack names must be generic")
        if "partenamut" in json.dumps(stack["properties"].get("tags", {})).casefold():
            errors.append(f"{filename}: AWS stack tags must be generic")
        template = json.loads((directory / filename).read_text())
        errors.extend(f"{filename}: {error}" for error in validate_template(template))
    if errors:
        raise ValueError("\n".join(errors))
    return len(stacks)
