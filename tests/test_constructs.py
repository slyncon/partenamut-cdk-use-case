import json

import pytest
from aws_cdk import App, CfnOutput, Stack
from aws_cdk.assertions import Match, Template

from cdk_launchpad.constructs import DocumentProcessor, SecureBucket


@pytest.fixture(params=["claims", "medical-documents"])
def template(request, tmp_path):
    handler_directory = tmp_path / "handler"
    handler_directory.mkdir()
    (handler_directory / "index.py").write_text("def handler(event, context): return {}\n")
    app = App(outdir=str(tmp_path / "assembly"))
    stack = Stack(app, "ConstructContract")
    documents = SecureBucket(stack, "Documents")
    processor = DocumentProcessor(
        stack,
        "Processor",
        bucket=documents.bucket,
        handler_directory=str(handler_directory),
        team=request.param,
    )
    CfnOutput(stack, "BucketName", value=documents.bucket.bucket_name)
    CfnOutput(stack, "FunctionName", value=processor.function.function_name)
    CfnOutput(stack, "LogGroupName", value=processor.function.log_group.log_group_name)
    return Template.from_stack(stack)


def processor_functions(template):
    return template.find_resources(
        "AWS::Lambda::Function",
        {
            "Properties": {
                "Handler": "index.handler",
                "Environment": {"Variables": {"TEAM": Match.any_value()}},
            }
        },
    )


def test_bucket_security_and_manual_removal(template):
    template.resource_count_is("AWS::S3::Bucket", 1)
    template.has_resource(
        "AWS::S3::Bucket",
        {
            "DeletionPolicy": "Delete",
            "UpdateReplacePolicy": "Delete",
            "Properties": Match.object_like(
                {
                    "BucketEncryption": {
                        "ServerSideEncryptionConfiguration": [
                            {"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
                        ]
                    },
                    "PublicAccessBlockConfiguration": {
                        "BlockPublicAcls": True,
                        "BlockPublicPolicy": True,
                        "IgnorePublicAcls": True,
                        "RestrictPublicBuckets": True,
                    },
                    "BucketName": Match.absent(),
                    "WebsiteConfiguration": Match.absent(),
                    "AccessControl": Match.absent(),
                }
            ),
        },
    )
    template.has_resource_properties(
        "AWS::S3::BucketPolicy",
        {
            "PolicyDocument": {
                "Statement": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "Effect": "Deny",
                                "Principal": {"AWS": "*"},
                                "Action": "s3:*",
                                "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                            }
                        )
                    ]
                )
            },
        },
    )
    template.resource_count_is("Custom::S3AutoDeleteObjects", 0)


def test_processor_logging_outputs_and_services(template):
    functions = processor_functions(template)
    assert len(functions) == 1  # CDK also adds its own notification helper Lambda.
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Handler": "index.handler",
            "Runtime": "python3.12",
            "MemorySize": 128,
            "Timeout": 10,
            "VpcConfig": Match.absent(),
            "Layers": Match.absent(),
            "LoggingConfig": {"LogGroup": Match.any_value()},
        },
    )
    template.has_resource(
        "AWS::Logs::LogGroup",
        {
            "Properties": Match.object_like({"RetentionInDays": 7}),
            "DeletionPolicy": "Delete",
        },
    )
    for output in ("BucketName", "FunctionName", "LogGroupName"):
        template.has_output(output, {"Value": Match.any_value()})
    allowed_types = {
        "AWS::S3::Bucket",
        "AWS::S3::BucketPolicy",
        "AWS::Lambda::Function",
        "AWS::Lambda::Permission",
        "AWS::IAM::Role",
        "AWS::IAM::Policy",
        "AWS::Logs::LogGroup",
        "Custom::S3BucketNotifications",
        "AWS::CDK::Metadata",
    }
    assert {r["Type"] for r in template.to_json()["Resources"].values()} <= allowed_types


def test_notification_and_read_permission_target_own_resources(template):
    bucket_id = next(iter(template.find_resources("AWS::S3::Bucket")))
    function_id, function = next(iter(processor_functions(template).items()))
    log_id = next(iter(template.find_resources("AWS::Logs::LogGroup")))
    assert function["Properties"]["LoggingConfig"] == {"LogGroup": {"Ref": log_id}}
    template.has_output("BucketName", {"Value": {"Ref": bucket_id}})
    template.has_output("FunctionName", {"Value": {"Ref": function_id}})
    template.has_output("LogGroupName", {"Value": {"Ref": log_id}})
    template.has_resource_properties(
        "Custom::S3BucketNotifications",
        {
            "BucketName": {"Ref": bucket_id},
            "NotificationConfiguration": {
                "LambdaFunctionConfigurations": [
                    {
                        "Events": ["s3:ObjectCreated:*"],
                        "LambdaFunctionArn": {"Fn::GetAtt": [function_id, "Arn"]},
                        "Filter": Match.any_value(),
                    }
                ]
            },
        },
    )
    notifications = template.find_resources("Custom::S3BucketNotifications")
    assert len(notifications) == 1
    notification = next(iter(notifications.values()))["Properties"]
    configuration = notification["NotificationConfiguration"]["LambdaFunctionConfigurations"][0]
    rules = configuration["Filter"]["Key"]["FilterRules"]
    assert len(rules) == 2
    assert {rule["Name"]: rule["Value"] for rule in rules} == {
        "prefix": "incoming/",
        "suffix": ".json",
    }
    template.has_resource_properties(
        "AWS::Lambda::Permission",
        {
            "Action": "lambda:InvokeFunction",
            "Principal": "s3.amazonaws.com",
            "FunctionName": {"Fn::GetAtt": [function_id, "Arn"]},
            "SourceArn": {"Fn::GetAtt": [bucket_id, "Arn"]},
            "SourceAccount": {"Ref": "AWS::AccountId"},
        },
    )
    role_id = function["Properties"]["Role"]["Fn::GetAtt"][0]
    policies = template.find_resources("AWS::IAM::Policy").values()
    statements = [
        statement
        for policy in policies
        if {"Ref": role_id} in policy["Properties"]["Roles"]
        for statement in policy["Properties"]["PolicyDocument"]["Statement"]
    ]
    s3_statements = [
        s for s in statements if any(action.startswith("s3:") for action in s["Action"])
    ]
    assert s3_statements
    for statement in s3_statements:
        assert statement["Effect"] == "Allow"
        assert set(statement["Action"]) <= {
            "s3:GetObject*",
            "s3:GetBucket*",
            "s3:List*",
        }
        assert statement["Resource"] == [
            {"Fn::GetAtt": [bucket_id, "Arn"]},
            {"Fn::Join": ["", [{"Fn::GetAtt": [bucket_id, "Arn"]}, "/*"]]},
        ]
    assert "Fn::ImportValue" not in json.dumps(template.to_json())
