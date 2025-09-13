"""
AWS CDK Stack for the KratosNOVA API Layer.

This stack defines the API Gateway, its Lambda handlers, and the specific
IAM permissions required for them to function.
"""
from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_iam as iam
)
from constructs import Construct
from .foundation_stack import KratosNovaFoundationStack

class KratosNovaApiStack(Stack):
    """Defines the API Gateway and its Lambda handlers."""
    def __init__(self, scope: Construct, construct_id: str, foundation_stack: KratosNovaFoundationStack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # =================================================================
        # ==================== IAM ROLE FOR API HANDLERS ==================
        # =================================================================
        api_lambda_role = iam.Role(
            self, "ApiLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for KratosNOVA API handler Lambda functions"
        )
        api_lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
        )
        
        # Grant permissions to access foundational resources
        foundation_stack.artifacts_bucket.grant_read_write(api_lambda_role)
        foundation_stack.contracts_table.grant_read_write_data(api_lambda_role)
        foundation_stack.submissions_table.grant_read_write_data(api_lambda_role)
        foundation_stack.agents_table.grant_read_write_data(api_lambda_role)

        # Grant permission to invoke the Bedrock model needed by the Agent-Manager
        api_lambda_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[
                f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"
            ],
            effect=iam.Effect.ALLOW
        ))
        
        # =================================================================
        # ===================== LAMBDA LAYER ============================
        # =================================================================
        self.common_layer = _lambda.LayerVersion(
            self, "CommonUtilsLayer",
            code=_lambda.Code.from_asset("lambda_layers/common_utils"),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_11]
        )
        
        # =================================================================
        # ================== API HANDLER LAMBDAS ========================
        # =================================================================
        api_lambda_env = {
            "CONTRACTS_TABLE_NAME": foundation_stack.contracts_table.table_name,
            "SUBMISSIONS_TABLE_NAME": foundation_stack.submissions_table.table_name,
            "AGENTS_TABLE_NAME": foundation_stack.agents_table.table_name,
            "ARTIFACTS_BUCKET_NAME": foundation_stack.artifacts_bucket.bucket_name
        }

        def create_lambda(name, folder):
            return _lambda.Function(
                self, name, runtime=_lambda.Runtime.PYTHON_3_11, handler="app.handler",
                code=_lambda.Code.from_asset(f"src/{folder}"), role=api_lambda_role,
                environment=api_lambda_env, layers=[self.common_layer]
            )

        goals_handler = create_lambda("GoalsHandler", "goals_manager")
        contracts_handler = create_lambda("ContractsHandler", "contracts_manager")
        submissions_handler = create_lambda("SubmissionsHandler", "submissions_manager")
        results_handler = create_lambda("ResultsHandler", "results_manager")
        agents_handler = create_lambda("AgentsHandler", "agents_manager")
        uploads_handler = create_lambda("UploadsHandler", "uploads_manager")
        critic_handler = create_lambda("CriticHandler", "agent_critic")

        # =================================================================
        # ================= API GATEWAY DEFINITION ========================
        # =================================================================
        self.api = apigw.RestApi(
            self, "KratosNovaApi",
            rest_api_name="KratosNOVA Service",
            description="API for the KratosNOVA agent economy",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS
            )
        )
        
        # --- API Resources and Methods ---
        goals_resource = self.api.root.add_resource("goals")
        goals_resource.add_method("POST", apigw.LambdaIntegration(goals_handler))
        goal_id_resource = goals_resource.add_resource("{goal_id}")
        goal_id_resource.add_method("GET", apigw.LambdaIntegration(results_handler))

        contracts_resource = self.api.root.add_resource("contracts")
        contracts_resource.add_method("GET", apigw.LambdaIntegration(contracts_handler))
        contract_id_resource = contracts_resource.add_resource("{contract_id}")
        contract_id_resource.add_method("GET", apigw.LambdaIntegration(contracts_handler))
        submissions_on_contract_resource = contract_id_resource.add_resource("submissions")
        submissions_on_contract_resource.add_method("POST", apigw.LambdaIntegration(submissions_handler))

        agents_resource = self.api.root.add_resource("agents")
        agents_resource.add_method("POST", apigw.LambdaIntegration(agents_handler))
        
        submissions_root_resource = self.api.root.add_resource("submissions")
        upload_url_resource = submissions_root_resource.add_resource("upload-url")
        upload_url_resource.add_method("POST", apigw.LambdaIntegration(uploads_handler))