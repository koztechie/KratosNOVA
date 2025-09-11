import aws_cdk as core
import aws_cdk.assertions as assertions

from kratos_nova_temp.kratos_nova_temp_stack import KratosNovaTempStack

# example tests. To run these tests, uncomment this file along with the example
# resource in kratos_nova_temp/kratos_nova_temp_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = KratosNovaTempStack(app, "kratos-nova-temp")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
