from aws_cdk import (
    Stack,
    RemovalPolicy, # <-- ДОДАЙТЕ ЦЕЙ РЯДОК
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_iam as iam,
    aws_dynamodb as dynamodb # <-- ДОДАЙТЕ ЦЕЙ РЯДОК
)
from constructs import Construct

class KratosNovaStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # =================================================================
        # ==================== IAM Role Definition ========================
        # =================================================================
        
        # Create a single IAM Role for all Lambda functions in the project
        lambda_role = iam.Role(
            self, "KratosNovaLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Unified role for all KratosNOVA project Lambda functions"
        )

        # 1. Add DynamoDB Permissions (Read/Write to our tables)
        dynamodb_policy = iam.PolicyStatement(
            actions=[
                "dynamodb:Query",
                "dynamodb:Scan",
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem"
            ],
            resources=[f"arn:aws:dynamodb:{self.region}:{self.account}:table/KratosNOVA-*"],
            effect=iam.Effect.ALLOW
        )
        lambda_role.add_to_policy(dynamodb_policy)

        # 2. Add S3 Permissions (Read/Write to our project bucket)
        s3_policy = iam.PolicyStatement(
            actions=[
                "s3:GetObject",
                "s3:PutObject"
            ],
            resources=[f"arn:aws:s3:::kratosnova-*/*"], # Access to all objects in buckets starting with 'kratosnova-'
            effect=iam.Effect.ALLOW
        )
        lambda_role.add_to_policy(s3_policy)

        # 3. Add Bedrock Permissions (Invoke our specific models)
        bedrock_policy = iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[
                f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0",
                f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
                f"arn:aws:bedrock:{self.region}::foundation-model/stability.stable-image-core-v1:0"
            ],
            effect=iam.Effect.ALLOW
        )
        lambda_role.add_to_policy(bedrock_policy)
        
        # 4. Add basic Lambda permissions for logging
        lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"))
        
        # =================================================================
        # ==================== DynamoDB Table Definitions =================
        # =================================================================

        # 1. Contracts Table
        contracts_table = dynamodb.Table(
            self, "ContractsTable",
            table_name="KratosNOVA-Contracts",
            partition_key=dynamodb.Attribute(
                name="contract_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY # IMPORTANT: This will delete the table when the stack is destroyed. Good for dev/hackathon, NOT for production.
        )

        # 2. Submissions Table
        submissions_table = dynamodb.Table(
            self, "SubmissionsTable",
            table_name="KratosNOVA-Submissions",
            partition_key=dynamodb.Attribute(
                name="submission_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )
        # Note: We will add a Global Secondary Index (GSI) on `contract_id` later
        # when we need to efficiently query all submissions for a given contract.
        # For now, we are keeping the MVP simple.

        # 3. Agents Table
        agents_table = dynamodb.Table(
            self, "AgentsTable",
            table_name="KratosNOVA-Agents",
            partition_key=dynamodb.Attribute(
                name="agent_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        # =================================================================

        # =================================================================
        # ================== Lambda & API Gateway Definition ================
        # =================================================================

        # 1. Define the Lambda function
        hello_world_lambda = _lambda.Function(
            self, "HelloWorldFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="app.handler",
            code=_lambda.Code.from_asset("src/hello_world"),
            role=lambda_role
        )

        # 2. Define the API Gateway
        api = apigw.LambdaRestApi(
            self, "KratosNovaApi",
            handler=hello_world_lambda,
            proxy=False # We will define resources manually
        )

        # 3. Define the '/hello' resource and GET method
        hello_resource = api.root.add_resource("hello")
        hello_resource.add_method(
            "GET",
            apigw.LambdaIntegration(hello_world_lambda)
        )