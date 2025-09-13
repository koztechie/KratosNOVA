from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam
)
from constructs import Construct
from .foundation_stack import KratosNovaFoundationStack
from .api_stack import KratosNovaApiStack

class KratosNovaAgentsStack(Stack):
    """Defines the agent and orchestrator layer of the application."""
    def __init__(
        self, scope: Construct, construct_id: str,
        foundation_stack: KratosNovaFoundationStack,
        api_stack: KratosNovaApiStack,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        common_layer = api_stack.common_layer
        
        # =================================================================
        # ========== ROLE 1: FOR FREELANCER AGENTS (ARTIST, COPYWRITER) =====
        # =================================================================
        freelancer_role = iam.Role(
            self, "FreelancerAgentRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for KratosNOVA Freelancer Agents (Artist, Copywriter)"
        )
        freelancer_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
        )
        foundation_stack.artifacts_bucket.grant_read_write(freelancer_role)
        # Freelancers only need to submit, they don't read contracts directly anymore
        foundation_stack.submissions_table.grant_write_data(freelancer_role)
        
        freelancer_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[
                f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
                f"arn:aws:bedrock:{self.region}::foundation-model/stability.stable-diffusion-xl-v1"
            ],
            effect=iam.Effect.ALLOW
        ))
        
        # =================================================================
        # ========== ROLE 2: FOR ORCHESTRATOR AGENT =====================
        # =================================================================
        orchestrator_role = iam.Role(
            self, "OrchestratorAgentRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for KratosNOVA Orchestrator Agent"
        )
        orchestrator_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
        )

        # =================================================================
        # ========== AGENT LAMBDA FUNCTIONS ===============================
        # =================================================================
        
        agent_lambda_env = {
            "CONTRACTS_TABLE_NAME": foundation_stack.contracts_table.table_name,
            "SUBMISSIONS_TABLE_NAME": foundation_stack.submissions_table.table_name,
            "AGENTS_TABLE_NAME": foundation_stack.agents_table.table_name,
            "ARTIFACTS_BUCKET_NAME": foundation_stack.artifacts_bucket.bucket_name,
            "API_BASE_URL": api_stack.api.url
        }
        
        artist_agent_handler = _lambda.Function(
            self, "ArtistAgentHandler", runtime=_lambda.Runtime.PYTHON_3_11,
            handler="app.handler", code=_lambda.Code.from_asset("src/agent_artist"),
            role=freelancer_role,  # <-- Use dedicated freelancer role
            environment=agent_lambda_env, layers=[common_layer], timeout=Duration.seconds(30)
        )
        copywriter_agent_handler = _lambda.Function(
            self, "CopywriterAgentHandler", runtime=_lambda.Runtime.PYTHON_3_11,
            handler="app.handler", code=_lambda.Code.from_asset("src/agent_copywriter"),
            role=freelancer_role, # <-- Use dedicated freelancer role
            environment=agent_lambda_env, layers=[common_layer]
        )
        
        # =================================================================
        # ========== ORCHESTRATOR LAMBDA & PERMISSIONS ====================
        # =================================================================
        
        orchestrator_env = agent_lambda_env.copy()
        orchestrator_env["ARTIST_AGENT_ARN"] = artist_agent_handler.function_arn
        orchestrator_env["COPYWRITER_AGENT_ARN"] = copywriter_agent_handler.function_arn
        
        orchestrator_handler = _lambda.Function(
            self, "FreelancerOrchestratorHandler", runtime=_lambda.Runtime.PYTHON_3_11,
            handler="app.handler", code=_lambda.Code.from_asset("src/freelancer_orchestrator"),
            role=orchestrator_role, # <-- Use dedicated orchestrator role
            environment=orchestrator_env, layers=[common_layer]
        )
        
        # Grant Orchestrator permission to invoke the other agents
        artist_agent_handler.grant_invoke(orchestrator_handler)
        copywriter_agent_handler.grant_invoke(orchestrator_handler)

        # --- Event Trigger ---
        agent_trigger_rule = events.Rule(
            self, "AgentTriggerRule", schedule=events.Schedule.rate(Duration.minutes(5))
        )
        agent_trigger_rule.add_target(targets.LambdaFunction(orchestrator_handler))