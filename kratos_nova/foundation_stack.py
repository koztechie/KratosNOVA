"""
AWS CDK Stack for the KratosNOVA Foundation Layer.
This stack creates all the foundational, cross-functional data storage 
resources that other stacks will depend on.
"""
from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
    aws_s3 as s3
)
from constructs import Construct

class KratosNovaFoundationStack(Stack):
    """Defines the foundational data storage resources for the application."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.artifacts_bucket = s3.Bucket(
            self, "ArtifactsBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True
        )

        self.contracts_table = dynamodb.Table(
            self, "ContractsTable",
            partition_key=dynamodb.Attribute(
                name="contract_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        self.submissions_table = dynamodb.Table(
            self, "SubmissionsTable",
            partition_key=dynamodb.Attribute(
                name="submission_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        self.agents_table = dynamodb.Table(
            self, "AgentsTable",
            partition_key=dynamodb.Attribute(
                name="agent_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )