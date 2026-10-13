from aws_cdk import RemovalPolicy
from aws_cdk import aws_s3 as s3
from constructs import Construct


class SecureBucket(Construct):
    """Shared bucket defaults, with explicit manual cleanup for this demo."""

    def __init__(self, scope: Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)
        self.bucket = s3.Bucket(
            self,
            "Bucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            # Demo only: empty the bucket manually before destroying the stack.
            # RETAIN is normally safer for meaningful data. No auto-delete helper.
            removal_policy=RemovalPolicy.DESTROY,
        )
