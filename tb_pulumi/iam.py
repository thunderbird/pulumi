"""Infrastrucutural patterns related to `AWS IAM <https://docs.aws.amazon.com/iam/>`_."""

import json
import pulumi
import pulumi_aws as aws
import re
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

        # AWS places heavy limitations on IAM resources. A policy can be no longer than 6,144 characters. This precludes
        # the simplest of logic where all relevant actions for all resources are listed; that scales far too quickly.
        # A user may have no more than 10 attached policies (though this can be increased as high as 20 through a quota
        # increase). A user group may also have only 10 attached policies, and that cannot be extended. AWS's own advice
        # here is to create user groups (each with as many as 10 policies) and then place users into those groups. Since
        # users can additionally have up to 20 directly attached polices after the quota increase, this leads to a
        # maximum of 120 policies. Ref: https://repost.aws/knowledge-center/iam-increase-policy-size We have to use this
        # design and some other length-saving techniques to fit all of this into AWS's permissions model.

        admin_policies = {}
        readonly_policies = {}

        for service in services:
            # Many ARNs can be collapsed into a single pattern, provided our tool has been used as designed, which
            # allows us to condense our policies quite a bit. But the Python regular expression we use to remove those
            # ARNs from the explicit listing differs from the pattern that means the same thing in an IAM policy.
            # Here we create a Python regex and an IAM resource pattern that are equivalent so we can use the right
            # format in the right place.
            common_arn_regex = (
                # PulumiSecretsManager names use slashes instead of the hyphens used elsewhere
                (f'arn:aws:{service}:.*:{self.project.aws_account_id}:.*:{self.project.name_prefix.replace("-", "/")}*')
                if service == 'secretsmanager'
                else (
                    f'arn:aws:{service}:({self.project.aws_region})*:'
                    f'{self.project.aws_account_id}:.*:{self.project.name_prefix}*'
                    # arn:aws:iam::768512802988:policy/accounts-stage-fargate-[secret]-logging
                )
            )
            common_arn_policy_pattern = (
                (f'arn:aws:{service}:*:{self.project.aws_account_id}:*:{self.project.name_prefix.replace("-", "/")}*')
                if service == 'secretsmanager'
                else (f'arn:aws:{service}:*:{self.project.aws_account_id}:*:{self.project.name_prefix}*')
            )
            # But ARNs for many old AWS products (like security groups and VPCs) do not use names and must be listed out
            service_arns = [arn for arn in arns if arn.split(':')[2] == service]
            uncommon_arns = [arn for arn in service_arns if not re.match(common_arn_regex, arn)]

            readonly_actions = [
                f'{service}:Describe*',
                f'{service}:List*',
            ]
            # The only "Get" action that's useful to a read-only user of Secrets Manager is "GetSecretValue". But these
            # values often contain secrets that allow administrative access to other systems, such as databases.
            # Allowing a read-only user to access these secrets potentially constitutes a privilege escalation, so we
            # intentionally exclude this action from Secrets Manager policies.
            if service != 'secretsmanager':
                readonly_actions.append(f'{service}:Get*')

            # To save on policy character length, only list those resources which are not matched by our common pattern
            resources = [common_arn_policy_pattern]
            resources.extend(uncommon_arns)

            # Inject our resources and actions into a readonly policy
            policy_doc = tb_pulumi.constants.IAM_POLICY_DOCUMENT.copy()
            policy_doc['Statement'][0]['Resource'] = resources
            policy_doc['Statement'][0]['Action'] = readonly_actions
            readonly_policies[service] = aws.iam.Policy(
                f'{self.name}-policy-{service}-readonly',
                description=f'Allow read-only access to {service} resources in the {self.project.name_prefix} stack',
                policy=json.dumps(policy_doc),
                tags=self.tags,
            )

            # Also build a more permissive admin policy
            policy_doc['Statement'][0]['Action'] = ['*']
            admin_policies[service] = aws.iam.Policy(
                f'{self.name}-policy-{service}-admin',
                description=f'Allow admin access to {service} resources in the {self.project.name_prefix} stack',
                policy=json.dumps(policy_doc),
                tags=self.tags,
            )

        admin_group = aws.iam.Group(
            f'{self.name}-usergroup-admin',
            name=f'{self.name}-admin',
        )
        admin_policy_attachments = {
            name: aws.iam.GroupPolicyAttachment(
                f'{self.name}-gpa-admin-{idx}',
                group=admin_group.name,
                policy_arn=policy.arn,
            )
            for idx, (name, policy) in admin_policies.items()
        }
        readonly_group = aws.iam.Group(
            f'{self.name}-usergroup-readonly',
            name=f'{self.name}-readonly',
        )
        readonly_policy_attachments = {
            name: aws.iam.GroupPolicyAttachment(
                f'{self.name}-gpa-readonly-{idx}',
                group=readonly_group.name,
                policy_arn=policy.arn,
            )
            for idx, (name, policy) in readonly_policies.items()
        }

        self.finish(
            resources={
                'admin_group': admin_group,
                'admin_policies': admin_policies,
                'admin_policy_attachments': admin_policy_attachments,
                'readonly_group': readonly_group,
                'readonly_policies': readonly_policies,
                'readonly_policy_attachments': readonly_policy_attachments,
            }
        )


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
