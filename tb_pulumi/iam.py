"""Infrastrucutural patterns related to `AWS IAM <https://docs.aws.amazon.com/iam/>`_."""

import json
import pulumi
import pulumi_aws as aws
import re
import string
import tb_pulumi.secrets

from copy import deepcopy
from tb_pulumi.constants import IAM_POLICY_DOCUMENT, IAM_RESOURCE_PATHS


class StackAccessPolicies(tb_pulumi.ProjectResourceGroup):
    """Creates two IAM policies granting read-only and full admin access to all resources in this project."""

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
        **kwargs,
    ):
        super().__init__(
            pulumi_type='tb:iam.StackAccessPolicies', name=name, project=project, opts=opts, tags=tags, **kwargs
        )

    def ready(self, outputs: list[pulumi.Resource]):
        """This function is called by the :py:class:`tb_pulumi.ProjectResourceGroup` after all outputs in the project
        have been resolved into values. Here, we go through every resource to get an exhaustive list of resource ARNs.
        Those are used to determine a list of AWS services in use by the project. An IAM policy is produced that has
        read-only access to those resources.
        """

        arns = [resource.arn for resource in self.all_resources if getattr(resource, 'arn', False)]
        pulumi.Output.all(*arns).apply(lambda arns: self.build_policies(arns))

    def build_policies(self, arns: list[str]):
        """Defines the IAM policies which govern access to the given list of resources.

        :param arns: List of resource ARNs to build policies around. This is automatically provided by the
            :py:meth:`ready` function when a stack's state has been achieved in a Pulumi run.
        :type arns: list[str]
        """

        # Start by getting a list of services in use by this project, extracted from the ARNs
        services = sorted(set([arn.split(':')[2] for arn in arns]))

        ####  WHY IS THIS SO COMPLICATED?  ####
        #
        #   There are a variety of limitations and gotchas involved with IAM and how it interacts with other AWS
        #   platforms. We must account for all of these complexities:
        #
        #   - A policy document can be no longer than 6,144 characters. This precludes the simplest of logic where all
        #     relevant actions for all resources are listed. That scales far too quickly along this metric.
        #   - A user may have no more than 10 attached policies (though this can be increased as high as 20 through a
        #     quota increase).
        #   - A user group may also have only 10 attached policies, and that cannot be extended. AWS's own advice here
        #     is to create user groups -- each with as many as 10 attached policies -- and then place users into those
        #     groups. Since users can additionally have up to 20 directly attached policies after the quota increase,
        #     this leads to a maximum of 120 policies. Ref: https://repost.aws/knowledge-center/iam-increase-policy-size
        #     https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_iam-quotas.html#reference_iam-quotas-entities
        #   - Most resources use the user-friendly names we provide as part of the ARN, meaning we can use patterns to
        #     create appropriate permission boundaries. But some legacy services (and others, like CloudFront) use
        #     randomly generated IDs instead. These can't be predicted or controlled, and we can't create safe
        #     boundaries through patterns.
        #   - Some services are global and therefore the ARNs do not have regions. Sometimes it's okay to use a "*" and
        #     sometimes it's not. That depends on a lot of apparent finnickiness on the AWS side of things, how "legacy"
        #     the service is, etc. Sometimes an ARN doesn't have an account ID. All of this is really sticky and has
        #     been worked out through trial.
        #
        #   All of these very special behaviors and the methods we use to deal with them are documented below in the
        #   hopes that this code remains maintainable.

        admin_policies = {}  # Policies granting administrative access to services
        readonly_policies = {}  # Policies granting read-only access to services
        for service in services:
            # Many ARNs can be collapsed into a single pattern, provided our tool has been used as designed and AWS is
            # uniform in its ARNs, which allows us to condense our policies quite a bit. But the Python regular
            # expression we use to identify and track those ARNs in this function differs from the pattern that means
            # the same thing in an IAM policy. Here we create a Python regex (common_arn_regex) and an IAM resource
            # pattern (common_arn_policy_pattern) that are equivalent so we can use the right format in the right place.
            if service == 'secretsmanager':
                # Secrets Manager tends to use slashes ("/") instead of dashes ("-").
                common_arn_regex = (
                    f'arn:aws:{service}:.*:{self.project.aws_account_id}:'
                    f'.*{self.project.name_prefix.replace("-", "/")}.*'
                )
            else:
                common_arn_regex = (
                    f'arn:aws:{service}:({self.project.aws_region})*:{self.project.aws_account_id}:'
                    f'.*{self.project.name_prefix}.*'
                )

            if service == 'iam':
                # Hardcode this "<path>" placeholder here; we have to expand this out to multiple resources later
                common_arn_policy_pattern = (
                    f'arn:aws:{service}::{self.project.aws_account_id}:<path>/*{self.project.name_prefix}*'
                )
            elif service == 's3':
                # S3 ARNs have no account ID in them
                common_arn_policy_pattern = f'arn:aws:{service}:::*{self.project.name_prefix}*'
            elif service == 'secretsmanager':
                # Secrets Manager tends to use slashes ("/") instead of dashes ("-").
                common_arn_policy_pattern = (
                    f'arn:aws:{service}:*:{self.project.aws_account_id}:*{self.project.name_prefix.replace("-", "/")}*'
                )
            else:
                common_arn_policy_pattern = (
                    f'arn:aws:{service}:*:{self.project.aws_account_id}:*{self.project.name_prefix}*'
                )

            # ARNs for many resources (security groups, VPCs, etc.) do not use names and must be listed out by ID. Here,
            # service_arns is all ARNs for a given service, while uncommon_arns are a subset of those ARNs which are not
            # matched by the policy pattern.
            service_arns = [arn for arn in arns if arn.split(':')[2] == service]
            uncommon_arns = [arn for arn in service_arns if not re.match(common_arn_regex, arn)]

            # "Describe" and "List" actions are typically safe for read-only access.
            readonly_actions = [
                f'{service}:Describe*',
                f'{service}:List*',
            ]

            # "Get" actions are also typically safe, but there is at least this exception: The only "Get" action that's
            # useful to a read-only user of Secrets Manager is "GetSecretValue". But these values often contain secrets
            # that allow administrative access to other systems, such as databases. Allowing a read-only user to access
            # these secrets potentially constitutes a privilege escalation, so we intentionally exclude this action from
            # Secrets Manager policies.
            if service != 'secretsmanager':
                readonly_actions.append(f'{service}:Get*')

            # To save on policy character length, only list explicitly those resources which are not matched by our
            # common pattern. First, we include that common pattern as the first resource.
            if service == 'iam':
                # ARNs for IAM resources have a "path" component after the account ID and before the resource name. You
                # cannot substitute this with a "*" in a policy; doing so yields a 400 from the API. We can wildcard the
                # rest of the ARN, but we must list a resource for every IAM resource path in the policy.
                resources = [common_arn_policy_pattern.replace('<path>', path) for path in IAM_RESOURCE_PATHS]
            else:
                resources = [common_arn_policy_pattern]
            # Now list the uncommon ones.
            resources.extend(uncommon_arns)

            # Inject our resources and actions into a readonly policy
            policy_doc = {
                'Version': '2012-10-17',
                'Statement': [{'Effect': 'Allow', 'Resource': resources, 'Action': readonly_actions}],
            }

            # Statement IDs in IAM policies must be alphanumeric. Here we normalize our inputs against that constraint.
            valid_chars = string.ascii_letters + '0123456789'
            service_sid_prefix = f'{self.project.project.title()}{self.project.stack.title()}{service.title()}'
            service_sid_prefix = ''.join([char for char in service_sid_prefix if char in valid_chars])

            # Form the read-only policy
            policy_doc['Statement'][0]['Sid'] = f'{service_sid_prefix}ReadOnly'
            policy_name = f'{self.name}-policy-{service}-readonly'
            readonly_policies[service] = aws.iam.Policy(
                policy_name,
                name=policy_name,
                description=f'Allow read-only access to {service} resources in the {self.project.name_prefix} stack',
                path='/',
                policy=json.dumps(policy_doc),
                opts=pulumi.ResourceOptions(parent=self),
                tags=self.tags,
            )

            # Also build a more permissive admin policy by updating the read-only policy doc's actions
            policy_doc['Statement'][0]['Sid'] = f'{service_sid_prefix}Admin'
            policy_doc['Statement'][0]['Action'] = ['*']
            policy_name = f'{self.name}-policy-{service}-admin'
            admin_policies[service] = aws.iam.Policy(
                policy_name,
                name=policy_name,
                description=f'Allow admin access to {service} resources in the {self.project.name_prefix} stack',
                path='/',
                policy=json.dumps(policy_doc),
                opts=pulumi.ResourceOptions(parent=self),
                tags=self.tags,
            )

        # Build a user group for admins, attaching the admin policies generated above.
        admin_group = aws.iam.Group(
            f'{self.name}-usergroup-admin',
            name=f'{self.name}-admin',
            opts=pulumi.ResourceOptions(parent=self),
        )
        admin_policy_attachments = {
            service: aws.iam.GroupPolicyAttachment(
                f'{self.name}-gpa-admin-{service}',
                group=admin_group.name,
                policy_arn=policy.arn,
                opts=pulumi.ResourceOptions(parent=self),
            )
            for service, policy in admin_policies.items()
        }

        # Build a group for read-only users, attaching the less permissive policies.
        readonly_group = aws.iam.Group(
            f'{self.name}-usergroup-readonly',
            name=f'{self.name}-readonly',
            opts=pulumi.ResourceOptions(parent=self),
        )
        readonly_policy_attachments = {
            name: aws.iam.GroupPolicyAttachment(
                f'{self.name}-gpa-readonly-{idx}',
                group=readonly_group.name,
                policy_arn=policy.arn,
                opts=pulumi.ResourceOptions(parent=self),
            )
            for idx, (name, policy) in enumerate(readonly_policies.items())
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

        - *access_key* - An `aws.iam.AccessKey <https://www.pulumi.com/registry/packages/aws/api-docs/iam/accesskey/>`_
          the user can authenticate with.
        - *group_membership* - An `aws.iam.UserGroupMembership
          <https://www.pulumi.com/registry/packages/aws/api-docs/iam/usergroupmembership/>`_ representing this user's
          membership in the provided groups.
        - *policy* - An `aws.iam.Policy <https://www.pulumi.com/registry/packages/aws/api-docs/iam/policy/>`_ granting
          the ability to retrieve this secret and its metadata.
        - *policy_attachments* A list of `aws.iam.PolicyAttachments
          <https://www.pulumi.com/registry/packages/aws/api-docs/iam/policyattachment/>`_ to include the ``policy``
          created here and any additional policies provided wiht the ``policies`` parameter.
        - *secret* - A :py:class:`tb_pulumi.secrets.SecretsManagerSecret` containing the secret authentication details.
        - *user* - The `aws.iam.User <https://www.pulumi.com/registry/packages/aws/api-docs/iam/user/>`_.

    :param name: A string identifying this set of resources.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param access_keys: Dict where the keys are arbitrary names for access keys to create for this user and the values
        are booleans indicating the key should be "Active" (True) or "Inactive" (False). To rotate an access key, first
        create a new key set to True. Then update the credentials wherever your implementation requires. Then deactivate
        the old key by setting its entry to False. If something unexpected breaks, you can still enable it again (set to
        True). When you're ready, delete the access key by removing its entry. Here's an example configuration where a
        new key ("green") has been created and an old key ("blue") is deactivated but not deleted:

        access_keys:
            blue: False
            green: True

    :param user_name: Name to give the IAM user.
    :type user_name: str

    :param enable_legacy_access_key: If ``True``, this will create an access key that is tracked outside of the dict of
        ``access_keys``. This is the way this module used to work, and it will be removed in a future version since it
        does not allow for cautious key rotation. Use it to migrate off of this feature, and afterward it should be set
        to False. Defaults to False.
    :type enable_legacy_access_key: bool

    :param groups: List of `aws.iam.Group <https://www.pulumi.com/registry/packages/aws/api-docs/iam/group/>`_ s to make
        this user a member of.
    :type groups: list[aws.iam.Group]

    :param policies: List of `aws.iam.Policy <https://www.pulumi.com/registry/packages/aws/api-docs/iam/policy/>`_
        resources to attach to the user. Defaults to [].
    :type policies: list[aws.iam.Policy], optional

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param tags: Key/value pairs to merge with the default tags which get applied to all resources in this group.
        Defaults to {}.
    :type tags: dict, optional

    :param kwargs: Any other keyword arguments which will be passed as inputs to the `aws.iam.User
      <https://www.pulumi.com/registry/packages/aws/api-docs/iam/user/>`_ resource.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        access_keys: dict,
        user_name: str,
        enable_legacy_access_key: bool = False,
        groups: list[aws.iam.Group] = [],
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
            **kwargs,
        )

        legacy_access_key = (
            aws.iam.AccessKey(
                f'{name}-key',
                user=user.name,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[user]),
            )
            if enable_legacy_access_key
            else None
        )

        keys = {
            key: aws.iam.AccessKey(
                f'{name}-key-{key}',
                user=user.name,
                status='Active' if active else 'Inactive',
                opts=pulumi.ResourceOptions(parent=self, depends_on=[user]),
            )
            for key, active in access_keys.items()
        }

        secret_base_name = f'{self.project.project}/{self.project.stack}/iam.user.{user_name}.access_key'

        # Use this function to create secrets that depend on access keys being applied
        def __access_key_secret(
            key_name: str, res_name: str, access_key: aws.iam.AccessKey, access_key_id: str, secret_access_key: str
        ):
            return tb_pulumi.secrets.SecretsManagerSecret(
                name=res_name,
                project=self.project,
                exclude_from_project=True,
                secret_name=f'{secret_base_name}{key_name}',
                secret_value=json.dumps({'access_key_id': access_key_id, 'secret_access_key': secret_access_key}),
                opts=pulumi.ResourceOptions(parent=self, depends_on=[access_key]),
            )

        legacy_secret = (
            pulumi.Output.all(access_key_id=legacy_access_key.id, secret_access_key=legacy_access_key.secret).apply(
                lambda outputs: __access_key_secret(
                    key_name='',
                    res_name=f'{name}-keysecret',
                    access_key=legacy_access_key,
                    access_key_id=outputs['access_key_id'],
                    secret_access_key=outputs['secret_access_key'],
                )
            )
            if enable_legacy_access_key
            else None
        )

        access_key_secrets = {}
        _secret_key_names = []

        def __access_key_secrets(outputs):
            # Here we merge data from the wider-scoped list of key names and the applied output values
            while len(outputs) > 0:
                key_name = _secret_key_names.pop(0)
                key_id = outputs.pop(0)
                secret_key = outputs.pop(0)

                access_key_secrets[key_name] = __access_key_secret(
                    key_name=f'.{key_name}',
                    res_name=f'{name}-keysecret-{key_name}',
                    access_key=keys[key_name],
                    access_key_id=key_id,
                    secret_access_key=secret_key,
                )

        _secret_outputs = []
        for key_name, key in keys.items():
            _secret_key_names.append(key_name)
            _secret_outputs.extend([key.id, key.secret])
        pulumi.Output.all(*_secret_outputs).apply(lambda outputs: __access_key_secrets(outputs))

        # We need the aws.secretsmanager.Secret resources to build the policy. But the secrets here are
        # ThunderbirdComponentResources, so Pulumi doesn't know it even has a `resources` member until it has been
        # applied. So we first apply the tb_pulumi.secretsmanager.SecretsManagerSecret, then Pulumi
        # can get to its `resources`. Then we pull the secret ARNs and form a policy from them.
        _policy_secrets = [secret for secret in [*access_key_secrets.values(), legacy_secret] if secret is not None]

        # Called when the SecretsManagerSecrets are applied
        def __policy_secrets_ready(policy_secrets):
            # When the secrets are ready, extract the ARNs from them
            policy_secret_arns = [secret.resources['secret'].arn for secret in policy_secrets]

            # Wait for the ARNs to be ready, then call the next stage
            return pulumi.Output.all(policy_secret_arns).apply(
                # An odd thing that happens during apply here: policy_secret_arns becomes a list of lists. We must
                # dereference that or we get a malformed policy.
                lambda policy_secret_arns: __policy_secret_arns_ready(policy_secrets, *policy_secret_arns)
            )

        # Caled when the individual secret ARNs are applied
        def __policy_secret_arns_ready(policy_secrets, policy_secret_arns):
            # For each ARN, add an extra pattern to allow for all secret versions
            all_arns = []
            for arn in policy_secret_arns:
                all_arns.extend([arn, f'{arn}*'])

            # The policy itself allows read actions on all of these ARNs
            policy_doc = deepcopy(IAM_POLICY_DOCUMENT)
            policy_doc['Statement'][0]['Sid'] = 'AllowSecretAccess'
            policy_doc['Statement'][0].update(
                {
                    'Action': [
                        'secretsmanager:DescribeSecret',
                        'secretsmanager:GetResourcePolicy',
                        'secretsmanager:GetSecretValue',
                        'secretsmanager:ListSecretVersionIds',
                    ],
                    'Resource': all_arns,
                }
            )

            return aws.iam.Policy(
                f'{self.name}-keypolicy',
                name=f'{user_name}-key-access',
                policy=json.dumps(policy_doc),
                description=f'Allows access to the secrets which store access key data for user {user_name}',
                path='/',
                tags=self.tags,
                opts=pulumi.ResourceOptions(parent=self, depends_on=policy_secrets),
            )

        secret_policy = pulumi.Output.all(*_policy_secrets).apply(
            lambda policy_secrets: __policy_secrets_ready(policy_secrets)
        )

        # Add the user to all the given groups
        group_membership = aws.iam.UserGroupMembership(
            f'{self.name}-gpmbr',
            groups=[group.name for group in groups],
            user=user.name,
        )

        # Collect all user-specified policy ARNs and attach them to the user
        user_policy_arns = [secret_policy.arn, *[pol.arn for pol in policies]]
        user_policy_attachments = [
            aws.iam.PolicyAttachment(
                f'{name}-polatt-{idx}',
                policy_arn=arn,
                users=[user.name],
                opts=pulumi.ResourceOptions(parent=self, depends_on=[user, secret_policy, *policies]),
            )
            for idx, arn in enumerate(user_policy_arns)
        ]

        self.finish(
            resources={
                'access_key': legacy_access_key,
                'access_keys': keys,
                'access_key_secrets': access_key_secrets,
                'group_membership': group_membership,
                'secret': legacy_secret,
                'policy': secret_policy,
                'policy_attachments': user_policy_attachments,
                'user': user,
            }
        )
