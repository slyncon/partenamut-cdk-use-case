from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_notifications as s3n
from constructs import Construct


class DocumentProcessor(Construct):
    """A team's handler behind a direct, filtered S3 notification."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        bucket: s3.IBucket,
        handler_directory: str,
        team: str,
    ) -> None:
        super().__init__(scope, construct_id)
        log_group = logs.LogGroup(
            self,
            "Logs",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.function = lambda_.Function(
            self,
            "Function",
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset(handler_directory, exclude=["__pycache__", "*.pyc"]),
            handler="index.handler",
            description=f"Synthetic document processor for {team}",
            environment={"TEAM": team},
            memory_size=128,
            timeout=Duration.seconds(10),
            log_group=log_group,
        )
        bucket.grant_read(self.function)
        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(self.function),
            s3.NotificationKeyFilter(prefix="incoming/", suffix=".json"),
        )
