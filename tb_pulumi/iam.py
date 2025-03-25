"""Infrastrucutural patterns related to `AWS IAM <https://docs.aws.amazon.com/iam/>`_."""

import json
import pulumi
import pulumi_aws as aws
import tb_pulumi
import tb_pulumi.secrets

from tb_pulumi.constants import IAM_POLICY_DOCUMENT


class UserWithAccessKey(tb_pulumi.ThunderbirdComponentResource):
    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        user_name: str,
        policies: list[aws.iam.Policy] = [],
        exclude_from_project: bool = False,
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
        **kwargs,
    ):
        super().__init__(
            'tb:iam:UserWithAccessKey',
            name=name,
            project=project,
            opts=opts,
            tags=tags,
        )

        user = aws.iam.User(
            f'{name}-user',
            name=user_name,
            path='/',
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        access_key = aws.iam.AccessKey(
            f'{name}-key',
            user=user.name,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[user]),
        )

        def __secret(access_key_id: str, secret_access_key: str):
            return tb_pulumi.secrets.SecretsManagerSecret(
                name=f'{name}-keysecret',
                project=self.project,
                exclude_from_project=True,
                secret_name=secret_name,
                secret_value=json.dumps({'access_key_id': access_key_id, 'secret_access_key': secret_access_key}),
                opts=pulumi.ResourceOptions(parent=self, depends_on=[access_key]),
            )

        secret_name = f'{self.project.project}/{self.project.stack}/iam.user.{user_name}.access_key'
        secret = pulumi.Output.all(access_key_id=access_key.id, secret_access_key=access_key.secret).apply(
            lambda outputs: __secret(
                access_key_id=outputs['access_key_id'], secret_access_key=outputs['secret_access_key']
            )
        )

        def __policy(
            secret_arn: str,
        ):
            pulumi.info(f'DEBUG -- secret_arn: {secret_arn}')
            policy_doc = IAM_POLICY_DOCUMENT.copy()
            policy_doc['Statement'][0]['Sid'] = 'AllowSecretAccess'
            policy_doc['Statement'][0].update(
                {
                    'Action': [
                        'secretsmanager:DescribeSecret',
                        'secretsmanager:GetResourcePolicy',
                        'secretsmanager:GetSecretValue',
                        'secretsmanager:ListSecretVersionIds',
                    ],
                    'Resource': [secret_arn, f'{secret_arn}*'],
                }
            )
            return aws.iam.Policy(
                f'{self.name}-keypolicy',
                name=f'{user_name}_KeyAccess',
                policy=json.dumps(policy_doc),
                description=f'Allows access to the secret which stores access key data for use {user_name}',
                path='/',
                tags=self.tags,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[secret]),
            )

        policy = secret.apply(
            lambda secret_tcp: secret_tcp.resources['secret'].arn.apply(
                lambda secret_arn: __policy(secret_arn=secret_arn)
            )
        )

        policy_arns = [policy.arn, *[pol.arn for pol in policies]]
        policy_attachments = [
            aws.iam.PolicyAttachment(
                f'{name}-polatt-{idx}',
                policy_arn=arn,
                users=[user.name],
                opts=pulumi.ResourceOptions(parent=self, depends_on=[user, policy, *policies]),
            )
            for idx, arn in enumerate(policy_arns)
        ]

        self.finish(
            resources={
                'user': user,
                'access_key': access_key,
                'secret': secret,
                'policy': policy,
                'policy_attachments': policy_attachments,
            }
        )
