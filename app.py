#!/usr/bin/env python3
import os

import aws_cdk as cdk

from kratos_nova.kratos_nova_stack import KratosNovaStack


app = cdk.App()
KratosNovaStack(app, "KratosNovaStack")

app.synth()
