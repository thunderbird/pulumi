"""Infrastructural patterns related to `Lambda Functions <https://docs.aws.amazon.com/lambda/latest/dg/welcome.html>`_."""

import json
import pulumi
import pulumi_aws as aws
import tb_pulumi
import tb_pulumi.constants

from copy import deepcopy


class RateInvokedLambdaFunction(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:lambda:RateInvokedLambdaFunction``

    Builds a Lambda function that executes on a recurring basis.

    Produces the following ``resources``:

        - *something* - Something here.

    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        rate: str,
        lambda_config: dict = {},
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
        **kwargs,
    ):
        super().__init__(
            'tb:lambda:RateInvokedLambdaFunction',
            name=name,
            project=project,
            opts=opts,
        )

        lambda_config = kwargs.pop('lambda_config', {})
        lambda_func = LambdaFunction(
            name=name,
            project=project,
            opts=opts,
            tags=self.tags,
            **lambda_config,
        )

        # The scheduler needs another ARP, role, and policy to invoke the function
        # The ARP is bog standard with the "scheduler" principal
        arp = deepcopy(tb_pulumi.constants.ASSUME_ROLE_POLICY)
        arp['Statement'][0]['Principal']['Service'] = 'scheduler.amazonaws.com'

        # The policy must have `lambda:InvokeFunction` on the function
        policy_doc = lambda_func.resources['lambda'].arn.apply(
            lambda lambda_arn: json.dumps(
                {
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Sid': 'AllowLambdaInvocation',
                            'Effect': 'Allow',
                            'Actions': ['lambda:InvokeFunction'],
                            'Resource': [lambda_arn],
                        }
                    ],
                }
            )
        )

        policy = aws.iam.Policy(
            f'{name}-scheduler-policy',
            name=name,
            policy=policy_doc,
            description=f'Policy for lambda scheduler {name}',
            tags=self.tags,
        )

        role = aws.iam.Role(
            f'{name}-scheduler-role',
            assume_role_policy=arp,
            description=f'Assume role policy for scheduler {name}',
            managed_policy_arns=[policy.arn],
            name=name,
            tags=self.tags,
        )

        schedule = aws.scheduler.Schedule(
            f'{name}-schedule',
            flexible_time_window={'mode': 'OFF'},
            schedule_expression=f'rate({rate})',
            target={
                'arn': lambda_func.resources['lambda'].arn,
                'role_arn': role.arn,
                # 'input': 'json formatted data passed into lambda invocation?',
            },
            description=f'Schedule for lambda {name}',
        )

        self.finish(
            outputs={
                'lambda': lambda_func,
                'policy': policy,
                'role': role,
                'schedule': schedule,
            }
        )


class LambdaFunction(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:lambda:LambdaFunction``

    Builds a Lambda function with its own IAM execution role.

    Produces the following ``resources``:

        - *something* - Something here.

    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        policies: list[aws.iam.Policy],
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
        **kwargs,
    ):
        super().__init__(
            'tb:lambda:LambdaFunction',
            name=name,
            project=project,
            opts=opts,
        )

        # Update the assume role policy's pricipal in a copy of our template
        arp = deepcopy(tb_pulumi.constants.ASSUME_ROLE_POLICY)
        arp['Statement'][0]['Principal']['Service'] = 'lambda.amazonaws.com'

        # Create the IAM role
        role = aws.iam.Role(
            f'{name}-lambda-role',
            assume_role_policy=json.dumps(arp),
            description=f'Execution role for lambda {name}',
            managed_policy_arns=[policy.arn for policy in policies],
            name=name,
            tags=self.tags,
        )

        # "lambda" is a Python reserved word, hence the underscored module name
        lambda_func = aws.lambda_.Function(
            f'{name}-lambda-function',
            role=role.arn,
            **kwargs,
        )

        self.finish(
            outputs={
                'lambda': lambda_func,
                'role': role,
            }
        )
