"""
AWS CDK Stack for the KratosNOVA Foundation Layer.

This stack creates all the foundational, cross-functional data storage
resources that other stacks will depend on. It has no dependencies on
other stacks in this project.
"""
from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
    aws_s3 as s3
)
from constructs import Construct


class KratosNovaFoundationStack(Stack):
    """
    Defines the foundational data storage resources for the application:
    S3 bucket for artifacts and DynamoDB tables for state management.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # =================================================================
        # ==================== S3 ARTIFACT STORAGE ======================
        # =================================================================
        self.artifacts_bucket = s3.Bucket(
            self, "ArtifactsBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True
        )

        # =================================================================
        # ================= DYNAMODB STATE STORAGE ======================
        # =================================================================

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
            removal_policy=RemovalPolicy.DESTROY,
            stream=dynamodb.StreamViewType.NEW_IMAGE
        )
        self.submissions_table.add_global_secondary_index(
            index_name="contract-id-index",
            partition_key=dynamodb.Attribute(
                name="contract_id",
                type=dynamodb.AttributeType.STRING
            )
        )

        self.agents_table = dynamodb.Table(
            self, "AgentsTable",
            partition_key=dynamodb.Attribute(
                name="agent_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        # NEW: Table for storing final, selected results for each goal.
        self.results_table = dynamodb.Table(
            self, "ResultsTable",
            partition_key=dynamodb.Attribute(
                name="goal_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="contract_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )