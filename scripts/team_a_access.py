"""Generate Platform-owned IAM setup; generation itself never accesses AWS."""

import argparse
import json
import re
from pathlib import Path


def statement(actions, resources, conditions=None):
    result = {"Effect": "Allow", "Action": actions, "Resource": resources}
    if conditions:
        result["Condition"] = conditions
    return result


def sub(value):
    return {"Fn::Sub": value}


def build_template(subject: str) -> dict:
    if not re.fullmatch(
        r"repo:[A-Za-z0-9_.-]+@[0-9]+/[A-Za-z0-9_.-]+@[0-9]+:environment:sandbox", subject
    ):
        raise ValueError("Use an exact repository subject for the sandbox environment")
    audience = "sts.amazonaws.com"
    iam = "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/"
    bucket = "arn:${AWS::Partition}:s3:::claimsteamstack-*"
    bootstrap = "arn:${AWS::Partition}:s3:::cdk-hnb659fds-assets-${AWS::AccountId}-${AWS::Region}"
    function = (
        "arn:${AWS::Partition}:lambda:${AWS::Region}:${AWS::AccountId}:function:ClaimsTeamStack-*"
    )
    log = "arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:"
    stack = "arn:${AWS::Partition}:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/"
    changeset = (
        "arn:${AWS::Partition}:cloudformation:${AWS::Region}:${AWS::AccountId}:changeSet/claims-*/*"
    )
    boundary = {"Ref": "LambdaBoundary"}
    execution_arn = {"Fn::GetAtt": ["ExecutionRole", "Arn"]}
    runtime_roles = sub(iam + "ClaimsTeamStack-*")
    basic_logs = sub(
        "arn:${AWS::Partition}:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
    )
    runtime_policy = {
        "Version": "2012-10-17",
        "Statement": [
            statement(
                [
                    "s3:GetBucket*",
                    "s3:ListBucket",
                    "s3:GetBucketNotification",
                    "s3:PutBucketNotification",
                ],
                sub(bucket),
            ),
            statement(["s3:GetObject*"], sub(bucket + "/incoming/*")),
            statement(
                ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                [sub(log + "ClaimsTeamStack-*"), sub(log + "/aws/lambda/ClaimsTeamStack-*")],
            ),
        ],
    }
    execution_policy = {
        "Version": "2012-10-17",
        "Statement": [
            statement(["s3:GetObject"], sub(bootstrap + "/claims/*")),
            statement(["s3:GetBucketLocation"], sub(bootstrap)),
            statement(["iam:GetPolicy", "iam:GetPolicyVersion"], [boundary, basic_logs]),
            statement(
                [
                    "s3:CreateBucket",
                    "s3:DeleteBucket",
                    "s3:Get*",
                    "s3:ListBucket",
                    "s3:PutBucketPolicy",
                    "s3:DeleteBucketPolicy",
                    "s3:PutEncryptionConfiguration",
                    "s3:PutBucketPublicAccessBlock",
                    "s3:PutBucketTagging",
                    "s3:PutBucketNotification",
                    "s3:PutBucketOwnershipControls",
                ],
                sub(bucket),
            ),
            statement(
                [
                    "lambda:CreateFunction",
                    "lambda:DeleteFunction",
                    "lambda:GetFunction",
                    "lambda:GetFunctionConfiguration",
                    "lambda:UpdateFunctionCode",
                    "lambda:UpdateFunctionConfiguration",
                    "lambda:AddPermission",
                    "lambda:RemovePermission",
                    "lambda:InvokeFunction",
                    "lambda:GetPolicy",
                    "lambda:TagResource",
                    "lambda:UntagResource",
                    "lambda:ListTags",
                    "lambda:GetFunctionCodeSigningConfig",
                    "lambda:GetRuntimeManagementConfig",
                ],
                sub(function),
            ),
            statement(
                [
                    "logs:CreateLogGroup",
                    "logs:DeleteLogGroup",
                    "logs:PutRetentionPolicy",
                    "logs:DeleteRetentionPolicy",
                    "logs:TagResource",
                    "logs:UntagResource",
                    "logs:ListTagsForResource",
                    "logs:TagLogGroup",
                    "logs:UntagLogGroup",
                ],
                sub(log + "ClaimsTeamStack-*"),
            ),
            statement(["logs:DescribeLogGroups"], "*"),
            statement(
                ["iam:CreateRole", "iam:PutRolePermissionsBoundary"],
                runtime_roles,
                {"ArnEquals": {"iam:PermissionsBoundary": boundary}},
            ),
            statement(
                [
                    "iam:GetRole",
                    "iam:DeleteRole",
                    "iam:UpdateAssumeRolePolicy",
                    "iam:GetRolePolicy",
                    "iam:PutRolePolicy",
                    "iam:DeleteRolePolicy",
                    "iam:ListRolePolicies",
                    "iam:ListAttachedRolePolicies",
                    "iam:TagRole",
                    "iam:UntagRole",
                    "iam:ListRoleTags",
                ],
                runtime_roles,
            ),
            statement(
                ["iam:AttachRolePolicy", "iam:DetachRolePolicy"],
                runtime_roles,
                {"ArnEquals": {"iam:PolicyARN": basic_logs}},
            ),
            statement(
                ["iam:PassRole"],
                runtime_roles,
                {"StringEquals": {"iam:PassedToService": "lambda.amazonaws.com"}},
            ),
        ],
    }
    deployment_policy = {
        "Version": "2012-10-17",
        "Statement": [
            statement(
                ["cloudformation:CreateChangeSet"],
                [sub(stack + "ClaimsTeamStack/*"), sub(changeset)],
                {"ArnEquals": {"cloudformation:RoleArn": execution_arn}},
            ),
            statement(
                [
                    "cloudformation:DescribeChangeSet",
                    "cloudformation:ExecuteChangeSet",
                    "cloudformation:DeleteChangeSet",
                ],
                [sub(stack + "ClaimsTeamStack/*"), sub(changeset)],
            ),
            statement(
                [
                    "cloudformation:DescribeStacks",
                    "cloudformation:DescribeStackEvents",
                    "cloudformation:DescribeStackResources",
                    "cloudformation:ListStackResources",
                    "cloudformation:GetTemplate",
                ],
                [sub(stack + "ClaimsTeamStack/*"), sub(stack + "CDKToolkit/*")],
            ),
            statement(["cloudformation:GetTemplateSummary"], "*"),
            statement(
                ["iam:PassRole"],
                execution_arn,
                {"StringEquals": {"iam:PassedToService": "cloudformation.amazonaws.com"}},
            ),
            statement(["s3:GetBucketLocation", "s3:GetBucketVersioning"], sub(bootstrap)),
            statement(
                ["s3:ListBucket"], sub(bootstrap), {"StringLike": {"s3:prefix": ["claims/*"]}}
            ),
            statement(["s3:GetObject", "s3:PutObject"], sub(bootstrap + "/claims/*")),
            statement(
                ["ssm:GetParameter"],
                sub(
                    "arn:${AWS::Partition}:ssm:${AWS::Region}:${AWS::AccountId}:parameter/cdk-bootstrap/hnb659fds/version"
                ),
            ),
        ],
    }
    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "Claims sandbox OIDC access; shared bootstrap is unchanged",
        "Resources": {
            "GitHubProvider": {
                "Type": "AWS::IAM::OIDCProvider",
                "Properties": {
                    "Url": "https://token.actions.githubusercontent.com",
                    "ClientIdList": ["sts.amazonaws.com"],
                },
            },
            "LambdaBoundary": {
                "Type": "AWS::IAM::ManagedPolicy",
                "Properties": {
                    "ManagedPolicyName": "CDKLaunchpad-TeamA-LambdaBoundary",
                    "PolicyDocument": runtime_policy,
                },
            },
            "ExecutionRole": {
                "Type": "AWS::IAM::Role",
                "Properties": {
                    "RoleName": "CDKLaunchpad-TeamA-CloudFormation",
                    "AssumeRolePolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Principal": {"Service": "cloudformation.amazonaws.com"},
                                "Action": "sts:AssumeRole",
                            }
                        ],
                    },
                    "Policies": [
                        {"PolicyName": "ClaimsResources", "PolicyDocument": execution_policy}
                    ],
                },
            },
            "GitHubRole": {
                "Type": "AWS::IAM::Role",
                "Properties": {
                    "RoleName": "CDKLaunchpad-TeamA-GitHubDeploy",
                    "MaxSessionDuration": 3600,
                    "AssumeRolePolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Principal": {"Federated": {"Ref": "GitHubProvider"}},
                                "Action": "sts:AssumeRoleWithWebIdentity",
                                "Condition": {
                                    "StringEquals": {
                                        "token.actions.githubusercontent.com:aud": audience,
                                        "token.actions.githubusercontent.com:sub": subject,
                                    }
                                },
                            }
                        ],
                    },
                    "Policies": [
                        {"PolicyName": "ClaimsDeployment", "PolicyDocument": deployment_policy}
                    ],
                },
            },
        },
        "Outputs": {
            "GitHubRoleArn": {"Value": {"Fn::GetAtt": ["GitHubRole", "Arn"]}},
            "ExecutionRoleArn": {"Value": execution_arn},
            "LambdaBoundaryArn": {"Value": boundary},
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--output", type=Path, default=Path(".build/team-a-access.json"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build_template(args.subject), indent=2) + "\n")
    print(f"Generated {args.output}; review before deploying CDKLaunchpadTeamAAccess")
