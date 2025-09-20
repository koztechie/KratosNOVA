"""
AWS CDK Stack for the KratosNOVA Agents Layer.

This stack defines the autonomous agents (GoalDeconstructor, Artist, etc.),
the Orchestrator that delegates tasks to them, and the event-driven
mechanisms that trigger the system. It also includes the monitoring dashboard.
"""
from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_lambda_event_sources as lambda_event_sources,
    aws_cloudwatch as cloudwatch
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
        # ========== ROLE 1: FOR GOAL DECONSTRUCTOR WORKER ===============
        # =================================================================
        deconstructor_role = iam.Role(
            self, "GoalDeconstructorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for the asynchronous Goal Deconstructor agent"
        )
        deconstructor_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
        )
        foundation_stack.contracts_table.grant_write_data(deconstructor_role)
        foundation_stack.bedrock_cache_table.grant_read_write_data(deconstructor_role)
        deconstructor_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"],
            effect=iam.Effect.ALLOW
        ))
        foundation_stack.goal_deconstruction_queue.grant_consume_messages(deconstructor_role)

        # =================================================================
        # ========== ROLE 2: FOR FREELANCER AGENTS ========================
        # =================================================================
        freelancer_role = iam.Role(
            self, "FreelancerAgentRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for KratosNOVA Freelancer Agents (Artist, etc.)"
        )
        freelancer_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
        )
        foundation_stack.artifacts_bucket.grant_read_write(freelancer_role)
        foundation_stack.submissions_table.grant_write_data(freelancer_role)
        foundation_stack.bedrock_cache_table.grant_read_write_data(freelancer_role)
        
        freelancer_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[
                f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
                f"arn:aws:bedrock:{self.region}::foundation-model/stability.stable-diffusion-xl-v1"
            ],
            effect=iam.Effect.ALLOW
        ))
        
        # =================================================================
        # ========== ROLE 3: FOR ORCHESTRATOR AGENT =======================
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
        # ========== AGENT & WORKER LAMBDA FUNCTIONS ======================
        # =================================================================
        
        agent_lambda_env = {
            "CONTRACTS_TABLE_NAME": foundation_stack.contracts_table.table_name,
            "SUBMISSIONS_TABLE_NAME": foundation_stack.submissions_table.table_name,
            "AGENTS_TABLE_NAME": foundation_stack.agents_table.table_name,
            "ARTIFACTS_BUCKET_NAME": foundation_stack.artifacts_bucket.bucket_name,
            "API_BASE_URL": api_stack.api.url,
            "BEDROCK_CACHE_TABLE_NAME": foundation_stack.bedrock_cache_table.table_name
        }
        
        goal_deconstructor_handler = _lambda.Function(
            self, "GoalDeconstructorHandler",
            runtime=_lambda.Runtime.PYTHON_3_11, handler="app.handler",
            code=_lambda.Code.from_asset("src/goal_deconstructor"), role=deconstructor_role,
            environment={
                "CONTRACTS_TABLE_NAME": foundation_stack.contracts_table.table_name,
                "BEDROCK_CACHE_TABLE_NAME": foundation_stack.bedrock_cache_table.table_name
            },
            layers=[common_layer], timeout=Duration.seconds(30)
        )
        goal_deconstructor_handler.add_event_source(
            lambda_event_sources.SqsEventSource(foundation_stack.goal_deconstruction_queue)
        )
        
        artist_agent_handler = _lambda.Function(
            self, "ArtistAgentHandler", runtime=_lambda.Runtime.PYTHON_3_11, handler="app.handler",
            code=_lambda.Code.from_asset("src/agent_artist"), role=freelancer_role,
            environment=agent_lambda_env, layers=[common_layer], timeout=Duration.seconds(30)
        )
        copywriter_agent_handler = _lambda.Function(
            self, "CopywriterAgentHandler", runtime=_lambda.Runtime.PYTHON_3_11, handler="app.handler",
            code=_lambda.Code.from_asset("src/agent_copywriter"), role=freelancer_role,
            environment=agent_lambda_env, layers=[common_layer]
        )
        analyst_agent_handler = _lambda.Function(
            self, "AnalystAgentHandler", runtime=_lambda.Runtime.PYTHON_3_11, handler="app.handler",
            code=_lambda.Code.from_asset("src/agent_analyst"), role=freelancer_role,
            environment=agent_lambda_env, layers=[common_layer]
        )
        
        # =================================================================
        # ========== ORCHESTRATOR LAMBDA & PERMISSIONS ====================
        # =================================================================
        
        orchestrator_env = agent_lambda_env.copy()
        orchestrator_env["ARTIST_AGENT_ARN"] = artist_agent_handler.function_arn
        orchestrator_env["COPYWRITER_AGENT_ARN"] = copywriter_agent_handler.function_arn
        orchestrator_env["ANALYST_AGENT_ARN"] = analyst_agent_handler.function_arn
        
        self.orchestrator_handler = _lambda.Function(
            self, "FreelancerOrchestratorHandler", runtime=_lambda.Runtime.PYTHON_3_11, handler="app.handler",
            code=_lambda.Code.from_asset("src/freelancer_orchestrator"), role=orchestrator_role,
            environment=orchestrator_env, layers=[common_layer]
        )
        
        artist_agent_handler.grant_invoke(self.orchestrator_handler)
        copywriter_agent_handler.grant_invoke(self.orchestrator_handler)
        analyst_agent_handler.grant_invoke(self.orchestrator_handler)

        # =================================================================
        # =================== EVENT TRIGGER =============================
        # =================================================================
        agent_trigger_rule = events.Rule(
            self, "AgentTriggerRule", schedule=events.Schedule.rate(Duration.minutes(5))
        )
        agent_trigger_rule.add_target(targets.LambdaFunction(self.orchestrator_handler))

        # =================================================================
        # =================== MONITORING DASHBOARD ========================
        # =================================================================
        dashboard = cloudwatch.Dashboard(
            self, "KratosNovaDashboard", dashboard_name="KratosNOVA-Monitoring"
        )

        dashboard.add_widgets(cloudwatch.TextWidget(
            markdown="# KratosNOVA Agent & Worker Metrics", width=24, height=1
        ))

        agent_functions = [
            {"name": "GoalDeconstructor", "function": goal_deconstructor_handler},
            {"name": "Orchestrator", "function": self.orchestrator_handler},
            {"name": "ArtistAgent", "function": artist_agent_handler},
            {"name": "CopywriterAgent", "function": copywriter_agent_handler},
            {"name": "AnalystAgent", "function": analyst_agent_handler},
        ]

        for item in agent_functions:
            fn = item["function"]
            name = item["name"]
            invocations_widget = cloudwatch.GraphWidget(
                title=f"{name} - Invocations",
                left=[fn.metric_invocations(period=Duration.minutes(5), statistic="Sum")],
                width=12, height=6
            )
            errors_widget = cloudwatch.GraphWidget(
                title=f"{name} - Errors",
                left=[fn.metric_errors(period=Duration.minutes(5), statistic="Sum")],
                width=12, height=6
            )
            dashboard.add_widgets(invocations_widget, errors_widget)

        dashboard.add_widgets(cloudwatch.TextWidget(
            markdown="# KratosNOVA Business Metrics", width=24, height=1
        ))

        successful_contracts_metric = cloudwatch.Metric(
            namespace="KratosNOVAMetrics", metric_name="SuccessfulContracts"
        )
        failed_contracts_metric = cloudwatch.Metric(
            namespace="KratosNOVAMetrics", metric_name="FailedContracts"
        )

        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Contract Outcomes (Sum over 1 hour)",
                left=[successful_contracts_metric.with_(
                    statistic="Sum", label="Successful", period=Duration.hours(1)
                )],
                right=[failed_contracts_metric.with_(
                    statistic="Sum", label="Failed/Reposted", period=Duration.hours(1)
                )],
                width=24, height=6
            )
        )