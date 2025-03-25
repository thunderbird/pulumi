"""Infrastrucutural patterns related to `AWS IAM <https://docs.aws.amazon.com/iam/>`_."""

import json
import pulumi
import pulumi_aws as aws
import tb_pulumi
import tb_pulumi.secrets

from tb_pulumi.constants import IAM_POLICY_DOCUMENT


class UserWithAccessKey(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:iam:UserWithAccessKey``

    Builds an IAM user with a set of access key credentials, stores those values in a Secrets Manager secret, and
    creates an IAM policy granting access to that secret. The IAM user gets that policy attached as well as any
    additional policies provided.

    Produces the following ``resources``:

        - *user* - The `aws.iam.User <https://www.pulumi.com/registry/packages/aws/api-docs/iam/user/>`_.
        - *access_key* - An `aws.iam.AccessKey <https://www.pulumi.com/registry/packages/aws/api-docs/iam/accesskey/>`_
          the user can authenticate with.
        - *secret* - A :py:class:`tb_pulumi.secrets.SecretsManagerSecret` containing the secret authentication details.
        - *policy* - An `aws.iam.Policy <https://www.pulumi.com/registry/packages/aws/api-docs/iam/policy/>`_ granting
          the ability to retrieve this secret and its metadata.
        - *policy_attachments* A list of `aws.iam.PolicyAttachments
          <https://www.pulumi.com/registry/packages/aws/api-docs/iam/policyattachment/>`_ to include the ``policy``
          created here and any additional policies provided wiht the ``policies`` parameter.

    :param name: A string identifying this set of resources.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param user_name: _description_
    :type user_name: str

    :param policies: _description_, defaults to []
    :type policies: list[aws.iam.Policy], optional

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param tags: Key/value pairs to merge with the default tags which get applied to all resources in this group.
        Defaults to {}.
    :type tags: dict, optional
    """

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

        # The secret can only be created after the key has been created, so do it in a post-apply function
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

        # The policy can only be created after the secret has been created, so do it in a post-apply function
        def __policy(
            secret_arn: str,
        ):
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

        # We need the secret to build the policy. The `secret` here is a ThunderbirdComponentResource, so Pulumi doesn't
        # know it even has a `resources` member until it has been applied. So we first apply `secret`, then Pulumi can
        # get to its `resources`, then we apply the actual AWS `Secret` object to get its ARN for the policy.
        policy = secret.apply(
            lambda secret_tcp: secret_tcp.resources['secret'].arn.apply(
                lambda secret_arn: __policy(secret_arn=secret_arn)
            )
        )

        # Collect all policy ARNs and attach them
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
