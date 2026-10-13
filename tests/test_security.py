import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from aws_cdk import App, Stack
from aws_cdk import aws_s3 as s3
from aws_cdk.assertions import Template

from cdk_launchpad.constructs import SecureBucket
from cdk_launchpad.security import PUBLIC_ACCESS_FLAGS, validate_assembly, validate_template


def secure_template(tmp_path):
    stack = Stack(App(outdir=str(tmp_path / "assembly")), "Secure")
    SecureBucket(stack, "Documents")
    return Template.from_stack(stack).to_json()


def test_secure_bucket_passes(tmp_path):
    assert validate_template(secure_template(tmp_path)) == []


def test_raw_insecure_bucket_bypassing_construct_fails(tmp_path):
    stack = Stack(App(outdir=str(tmp_path / "assembly")), "Bypass")
    # New S3 service defaults do not replace explicit template security settings.
    s3.Bucket(stack, "RawBucket", encryption=s3.BucketEncryption.UNENCRYPTED)
    errors = validate_template(Template.from_stack(stack).to_json())
    assert len(errors) == 5
    assert any("BucketEncryption" in error for error in errors)
    assert all(any(flag in error for error in errors) for flag in PUBLIC_ACCESS_FLAGS)


@pytest.mark.parametrize("flag", PUBLIC_ACCESS_FLAGS)
@pytest.mark.parametrize("value", [None, False, "true", 1])
def test_all_flags_must_be_explicit_true(tmp_path, flag, value):
    template = secure_template(tmp_path)
    bucket = next(r for r in template["Resources"].values() if r["Type"] == "AWS::S3::Bucket")
    bucket["Properties"]["PublicAccessBlockConfiguration"][flag] = value
    assert any(flag in error for error in validate_template(template))


def test_encryption_must_be_explicit_and_usable(tmp_path):
    valid = secure_template(tmp_path)
    for encryption in (
        {},
        {"ServerSideEncryptionConfiguration": []},
        {"ServerSideEncryptionConfiguration": [{"ServerSideEncryptionByDefault": {}}]},
    ):
        template = copy.deepcopy(valid)
        bucket = next(r for r in template["Resources"].values() if r["Type"] == "AWS::S3::Bucket")
        bucket["Properties"]["BucketEncryption"] = encryption
        assert any("BucketEncryption" in error for error in validate_template(template))


def test_gate_reads_all_actual_application_templates(tmp_path):
    directories = []
    for stack_name in ("FirstApplication", "SecondApplication"):
        directory = tmp_path / stack_name
        app = App(outdir=str(directory))
        SecureBucket(Stack(app, stack_name), "Documents")
        app.synth()
        assert validate_assembly(directory) == 1
        directories.append(directory)
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_synth.py"
    command = [sys.executable, str(script), *(str(directory) for directory in directories)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "2 application stack templates" in result.stdout
    filename = directories[1] / "SecondApplication.template.json"
    template = json.loads(filename.read_text())
    template["Resources"]["BypassBucket"] = {"Type": "AWS::S3::Bucket"}
    filename.write_text(json.dumps(template))
    with pytest.raises(ValueError, match="SecondApplication.template.json: BypassBucket"):
        validate_assembly(directories[1])
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1
    assert "BypassBucket" in result.stderr


def test_missing_assembly_fails(tmp_path):
    with pytest.raises(FileNotFoundError):
        validate_assembly(tmp_path)


def test_empty_assembly_fails(tmp_path):
    (tmp_path / "manifest.json").write_text('{"artifacts": {}}')
    with pytest.raises(ValueError, match="No application stacks"):
        validate_assembly(tmp_path)
