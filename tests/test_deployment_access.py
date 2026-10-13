import json

import pytest

from scripts.team_a_access import build_template

SUBJECT = "repo:example@1/claims@2:environment:sandbox"


def test_oidc_trust_is_exact_and_runtime_boundary_is_scoped():
    resources = build_template(SUBJECT)["Resources"]
    role = resources["GitHubRole"]["Properties"]
    trust = role["AssumeRolePolicyDocument"]["Statement"][0]
    assert trust["Condition"]["StringEquals"] == {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
        "token.actions.githubusercontent.com:sub": SUBJECT,
    }
    policy = resources["LambdaBoundary"]["Properties"]["PolicyDocument"]
    assert all(s["Resource"] != "*" for s in policy["Statement"])
    assert "/incoming/*" in json.dumps(policy)
    assert "MedicalDocuments" not in json.dumps(resources)


def test_deployment_cannot_pass_bootstrap_admin_role_or_destroy_stacks():
    resources = build_template(SUBJECT)["Resources"]
    policy = resources["GitHubRole"]["Properties"]["Policies"][0]["PolicyDocument"]
    actions = [action for s in policy["Statement"] for action in s["Action"]]
    assert "cloudformation:DeleteStack" not in actions
    assert "sts:AssumeRole" not in actions
    pass_role = next(s for s in policy["Statement"] if "iam:PassRole" in s["Action"])
    assert pass_role["Resource"] == {"Fn::GetAtt": ["ExecutionRole", "Arn"]}
    assert "AdministratorAccess" not in json.dumps(resources)
    execution = resources["ExecutionRole"]["Properties"]["Policies"][0]["PolicyDocument"]
    create_role = next(s for s in execution["Statement"] if "iam:CreateRole" in s["Action"])
    assert create_role["Condition"]["ArnEquals"]["iam:PermissionsBoundary"] == {
        "Ref": "LambdaBoundary"
    }
    assert not any(
        "iam:DeleteRolePermissionsBoundary" in s["Action"] for s in execution["Statement"]
    )


@pytest.mark.parametrize("subject", ["*", "repo:org/team:*", "repo:org/team:ref:refs/heads/main"])
def test_wildcard_or_wrong_environment_subject_fails(subject):
    with pytest.raises(ValueError, match="exact repository"):
        build_template(subject)
