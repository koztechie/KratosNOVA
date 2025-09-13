#!/usr/bin/env python3
import aws_cdk as cdk

from kratos_nova.foundation_stack import KratosNovaFoundationStack
from kratos_nova.api_stack import KratosNovaApiStack
from kratos_nova.agents_stack import KratosNovaAgentsStack

app = cdk.App()

foundation_stack = KratosNovaFoundationStack(app, "KratosNovaFoundationStack")
api_stack = KratosNovaApiStack(app, "KratosNovaApiStack", foundation_stack=foundation_stack)
agents_stack = KratosNovaAgentsStack(app, "KratosNovaAgentsStack", foundation_stack=foundation_stack, api_stack=api_stack)

# Explicitly set dependencies
api_stack.add_dependency(foundation_stack)
agents_stack.add_dependency(api_stack)

app.synth()