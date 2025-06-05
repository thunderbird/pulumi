"""Infrastrucutural patterns related to `AWS IAM <https://docs.aws.amazon.com/iam/>`_."""

import json
import pulumi
import pulumi_aws as aws
import tb_pulumi.constants
import tb_pulumi.secrets

from tb_pulumi.constants import IAM_POLICY_DOCUMENT


class StackAccessPolicies(tb_pulumi.ProjectResourceGroup):
    """Creates two IAM policies granting read-only and full admin access to all resources in this project."""

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
    ):
        super().__init__(pulumi_type='tb:iam.StackAccessPolicies', name=name, project=project, opts=opts, tags=tags)

    def ready(self, outputs: list[pulumi.Resource]):
        """This function is called by the :py:class:`tb_pulumi.ProjectResourceGroup` after all outputs in the project
        have been resolved into values. Here, we go through every resource to get an exhaustive list of resource ARNs.
        Those are used to determine a list of AWS services in use by the project. An IAM policy is produced that has
        read-only access to those resources.
        """

        arns = [resource.arn for resource in self.all_resources if getattr(resource, 'arn', False)]
        pulumi.Output.all(*arns).apply(lambda arns: self.build_policies(arns))

    def build_policies(self, arns: list[str]):
        services = set([arn.split(':')[2] for arn in arns])

        pulumi.info(f'DEBUG -- services: {sorted(services)}')
        pulumi.info(f'DEBUG -- arns: {'\n'.join(sorted(arns))}')

        # Build a read-only policy
        readonly_policy_doc = tb_pulumi.constants.IAM_POLICY_DOCUMENT.copy()
        readonly_policy_doc['Statement'][0]['Resource'] = arns
        actions = []
        for service in services:
            # The only real "Get" in secretsmanager is "GetSecretValue". But some secrets might grant admin access in
            # other systems, like databases, and we don't want that kind of escalation to happen. The
            # `PulumiSecretsManager` class creates policies that can grant this access if you would like to grant it
            # to an otherwise read-only user.
            if service == 'secretsmanager':
                actions.extend([
                    f'{service}:Describe*',
                    f'{service}:List*',
                ])
            else:
                actions.extend(
                    [
                        f'{service}:Describe*',
                        f'{service}:Get*',
                        f'{service}:List*',
                    ]
                )
        readonly_policy_doc['Statement'][0]['Action'] = actions
        self.readonly_policy = aws.iam.Policy(
            f'{self.name}-stackreadonly',
            description=f'Allow read-only access to the {self.project.name_prefix} stack',
            policy=json.dumps(readonly_policy_doc),
            tags=self.tags,
        )

        # Build an admin policy
        admin_policy_doc = tb_pulumi.constants.IAM_POLICY_DOCUMENT.copy()
        admin_policy_doc['Statement'][0]['Resource'] = arns
        admin_policy_doc['Statement'][0]['Action'] = ['*']
        self.admin_policy = aws.iam.Policy(
            f'{self.name}-stackadmin',
            description=f'Allow full admin access to the {self.project.name_prefix} stack',
            policy=json.dumps(admin_policy_doc),
            tags=self.tags,
        )

        self.finish(resources={'admin_policy': self.admin_policy, 'readonly_policy': self.readonly_policy})


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
        secret_name = f'{self.project.project}/{self.project.stack}/iam.user.{user_name}.access_key'

        def __secret(access_key_id: str, secret_access_key: str):
            return tb_pulumi.secrets.SecretsManagerSecret(
                name=f'{name}-keysecret',
                project=self.project,
                exclude_from_project=True,
                secret_name=secret_name,
                secret_value=json.dumps({'access_key_id': access_key_id, 'secret_access_key': secret_access_key}),
                opts=pulumi.ResourceOptions(parent=self, depends_on=[access_key]),
            )

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
                name=f'{user_name}-key-access',
                policy=json.dumps(policy_doc),
                description=f'Allows access to the secret which stores access key data for use {user_name}',
                path='/',
                tags=self.tags,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[secret]),
            )

        # We need the secret to build the policy. The `secret` here is a ThunderbirdComponentResource, so Pulumi doesn't
        # know it even has a `resources` member until it has been applied. So we first apply `secret`, then Pulumi can
        # get to its `resources`, then we apply the actual AWS `Secret` object to get its ARN for the policy.
        secret_policy = secret.apply(
            lambda secret_tcp: secret_tcp.resources['secret'].arn.apply(
                lambda secret_arn: __policy(secret_arn=secret_arn)
            )
        )

        # Collect all policy ARNs and attach them
        policy_arns = [secret_policy.arn, *[pol.arn for pol in policies]]
        policy_attachments = [
            aws.iam.PolicyAttachment(
                f'{name}-polatt-{idx}',
                policy_arn=arn,
                users=[user.name],
                opts=pulumi.ResourceOptions(parent=self, depends_on=[user, secret_policy, *policies]),
            )
            for idx, arn in enumerate(policy_arns)
        ]

        self.finish(
            resources={
                'user': user,
                'access_key': access_key,
                'secret': secret,
                'policy': secret_policy,
                'policy_attachments': policy_attachments,
            }
        )
