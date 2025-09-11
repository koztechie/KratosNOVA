from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
)
from constructs import Construct

class KratosNovaStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. Define the Lambda function
        hello_world_lambda = _lambda.Function(
            self, "HelloWorldFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="app.handler",
            code=_lambda.Code.from_asset("src/hello_world")
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