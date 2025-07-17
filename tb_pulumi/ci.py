"""Patterns related to continuous integration."""

import json
import pulumi
import pulumi_aws as aws
import tb_pulumi


class AwsAutomationUser(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:ci:AutomationUser``

    Creates an IAM user, then creates a keypair for it. The keypair data is stored in Secrets Manager. Several
    options, documented below, exist to provide some common permission sets for build and deployment patterns used
    in these modules. Additional policies can be added arbitrarily to expand these permissions.

    Because CI processes affect resources built across multiple environments (which can also be interpreted as
    multiple Pulumi stacks), these items are only created in a single stack.

    Produces the following ``resources``:

        - *user* - `aws.iam.User <https://www.pulumi.com/registry/packages/aws/api-docs/iam/user/>`_ to run CI
          operations.
        - *access_key* - `aws.iam.AccessKey <https://www.pulumi.com/registry/packages/aws/api-docs/iam/accesskey/>`_ for
          that user's authentication.
        - *secret* - :py:class:`tb_pulumi.secrets.SecretsManagerSecret` where the access key data is stored.
        - *ecr_image_push_policy* - `aws.iam.Policy <https://www.pulumi.com/registry/packages/aws/api-docs/iam/policy/>`_
          defining permissions required to push container images to an ECR repository, but only if
          ``enable_ecr_image_push`` is ``True``.
        - *s3_upload_policy* - `aws.iam.Policy <https://www.pulumi.com/registry/packages/aws/api-docs/iam/policy/>`_
          defining permissions required to upload files to S3 buckets, but only if ``enable_s3_bucket_upload`` is
          ``True``.
        - *s3_full_access_policy* - `aws.iam.Policy
          <https://www.pulumi.com/registry/packages/aws/api-docs/iam/policy/>`_ defining complete, unfettered access to
          S3 buckets and their contents, but only if ``enable_full_s3_access`` is ``True``.
        - *fargate_deployment_policy* - `aws.iam.Policy
          <https://www.pulumi.com/registry/packages/aws/api-docs/iam/policy/>`_ defining permissions needed to deploy
          images to a Fargate service, but only if ``enable_fargate_deployments`` is ``True``.


    :param name: Name of the IAM user to create.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param active_stack: The name of the stack to manage these single-stack resources in. Defaults to 'stage'.
        You should always set this to a stack you expect to be a permanent fixture in your infrastructure.
    :type active_stack: str, optional

    :param additional_policies: List of ARNs of IAM policies to additionally attach to the user. Defaults to [].
    :type additional_policies: list[str], optional

    :param enable_ecr_image_push: When True, attaches a policy to the user which allows it to push images to ECR
        repositories. Use this when your CI pipeline involves building a container image and pushing it to an ECR
        repo. Defaults to False.
    :type enable_ecr_image_push: bool, optional

    :param ecr_repositories: When ``enabled_ecr_image_push`` is True, permission will be granted to push images to
        these ECR repositories. Defaults to None.
    :type ecr_repositories: list[str], optional

    :param enable_fargate_deployments: When True, attaches a policy which allows new task definitions to be deployed
        to Fargate services. Use this when your CI pipeline needs to deploy new images to Fargate services. Defaults
        to False.
    :type enable_fargate_deployments: str, optional

    :param fargate_clusters: When ``enable_fargate_deployments`` is True, permission will be granted to deploy to
        this list of clusters. Defaults to None.
    :type fargate_clusters: list[str], optional

    :param fargate_task_role_arns: When ``enable_fargate_deployments`` is True, permission will be granted for the
        user to authenticate as this list of task roles. This should be a list of ARNs of task execution roles in
        the clusters you wish to deploy to. Defaults to None.
    :type fargate_task_role_arns: list[str], optional

    :param enable_full_s3_access: When True, allows the user unrestricted access to select S3 buckets. Use this when
        your CI needs to be able to run Pulumi executions. Those commands will need to run with access to the Pulumi
        state bucket. Defaults to False.
    :type enable_full_s3_access: bool, optional

    :param s3_full_access_buckets: When ``enable_full_s3_access`` is True, full permission will be granted to this
        list of buckets and all objects within them. Defaults to [].
    :type s3_full_access_buckets: list, optional

    :param enable_s3_bucket_upload: When True, allows the user to upload files into select S3 buckets. Use this when
        your CI pipeline needs to deploy files to an S3 bucket, such as when using a
        :py:class:`tb_pulumi.cloudfront.CloudFrontS3Service`. Defaults to False.
    :type enable_s3_bucket_upload: bool, optional

    :param s3_upload_buckets: When ``enable_s3_bucket_upload`` is True, allow uploading files to these buckets.
        Defaults to [].
    :type s3_upload_buckets: list, optional

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        active_stack: str = 'stage',
        additional_policies: list[str] = [],
        enable_ecr_image_push: bool = False,
        ecr_repositories: list[str] = None,
        enable_fargate_deployments: str = False,
        fargate_clusters: list[str] = None,
        fargate_task_role_arns: list[str] = None,
        enable_full_s3_access: bool = False,
        s3_full_access_buckets: list = [],
        enable_s3_bucket_upload: bool = False,
        s3_upload_buckets: list[str] = [],
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        super().__init__('tb:ci:AutomationUser', name=name, project=project, opts=opts, **kwargs)

        if project.stack == active_stack:
            user = aws.iam.User(
                f'{name}-user',
                name=f'{self.project.project}-ci',
                tags=self.tags,
                opts=pulumi.ResourceOptions(parent=self),
            )

            access_key = aws.iam.AccessKey(
                f'{name}-accesskey',
                user=user.name,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[user]),
            )

            secret_value = pulumi.Output.all(id=access_key.id, secret=access_key.secret).apply(
                lambda args: json.dumps({'aws_access_key_id': args['id'], 'aws_secret_access_key': args['secret']})
            )
            secret = tb_pulumi.secrets.SecretsManagerSecret(
                f'{name}-secret-accesskey',
                project=project,
                secret_name=f'{project.project}/{project.stack}/ci-access-keys',
                secret_value=secret_value,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[access_key]),
                tags=self.tags,
            )

            if enable_ecr_image_push:
                policy_dict = {
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Sid': 'ImageActions',
                            'Effect': 'Allow',
                            'Action': [
                                'ecr:BatchCheckLayerAvailability',
                                'ecr:BatchGetImage',
                                'ecr:CompleteLayerUpload',
                                'ecr:DescribeImages',
                                'ecr:InitiateLayerUpload',
                                'ecr:GetDownloadUrlForLayer',
                                'ecr:ListImages',
                                'ecr:UploadLayerPart',
                                'ecr:PutImage',
                            ],
                            'Resource': [
                                f'arn:aws:ecr:{project.aws_region}:{project.aws_account_id}:repository/{repo}*'
                                for repo in ecr_repositories
                            ],
                        },
                        {
                            'Sid': 'AuthActions',
                            'Effect': 'Allow',
                            'Action': ['ecr:GetAuthorizationToken'],
                            'Resource': ['*'],
                        },
                    ],
                }
                policy_json = json.dumps(policy_dict)
                ecr_image_push_policy = aws.iam.Policy(
                    f'{name}-policy-ecrpush',
                    name=f'{name}-ecr-push',
                    description=f'Allows CI automation for {project.project} to push container images to ECR.',
                    policy=policy_json,
                    opts=pulumi.ResourceOptions(parent=self),
                    tags=self.tags,
                )

                # Ignore unused variable rules for attachments like this using "noqa" statements for rule F841.
                # Ref: https://docs.astral.sh/ruff/rules/unused-variable/
                ecr_image_push_policy_attachment = aws.iam.PolicyAttachment(  # noqa: F841
                    f'{name}-polatt-ecrpush',
                    users=[user],
                    policy_arn=ecr_image_push_policy.arn,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[ecr_image_push_policy, user]),
                )

            if enable_s3_bucket_upload:
                policy_resources = []
                for bucket in s3_upload_buckets:
                    policy_resources.extend([f'arn:aws:s3:::{bucket}', f'arn:aws:s3:::{bucket}/*'])
                policy_dict = {
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Sid': 'S3BucketAndObjectAccess',
                            'Effect': 'Allow',
                            'Action': ['s3:PutObject', 's3:ListBucket'],
                            'Resource': policy_resources
                        }
                    ],
                }
                policy_json = json.dumps(policy_dict)
                s3_upload_policy = aws.iam.Policy(
                    f'{name}-policy-s3upload',
                    name=f'{name}-s3-upload',
                    description=f'Allows CI automation for {project.project} to upload files to certain S3 buckets.',
                    policy=policy_json,
                    opts=pulumi.ResourceOptions(parent=self),
                    tags=self.tags,
                )
                s3_upload_policy_attachment = aws.iam.PolicyAttachment(  # noqa: F841
                    f'{name}-polatt-s3upload',
                    users=[user],
                    policy_arn=s3_upload_policy.arn,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[s3_upload_policy, user]),
                )

            if enable_full_s3_access:
                resources = []
                for bucket in s3_full_access_buckets:
                    resources.append(f'arn:aws:s3:::{bucket}')
                    resources.append(f'arn:aws:s3:::{bucket}/*')
                policy_dict = {
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Sid': 'S3FullAccess',
                            'Effect': 'Allow',
                            'Action': ['s3:*'],
                            'Resource': resources,
                        }
                    ],
                }
                policy_json = json.dumps(policy_dict)
                s3_full_access_policy = aws.iam.Policy(
                    f'{name}-policy-s3fullaccess',
                    name=f'{name}-ci-s3-fullaccess',
                    description=f'Allows CI automation for {project.project} to do anything with certain S3 buckets.',
                    policy=policy_json,
                    opts=pulumi.ResourceOptions(parent=self),
                    tags=self.tags,
                )
                s3_full_access_policy_attachment = aws.iam.PolicyAttachment(  # noqa: F841
                    f'{name}-polatt-s3fullaccess',
                    users=[user],
                    policy_arn=s3_full_access_policy.arn,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[s3_full_access_policy, user]),
                )

            if enable_fargate_deployments:
                ecs_write_resources = []
                for cluster in fargate_clusters:
                    ecs_write_resources.append(
                        f'arn:aws:ecs:{project.aws_region}:{project.aws_account_id}:*/{cluster}*'
                    )
                    ecs_write_resources.append(
                        f'arn:aws:ecs:{project.aws_region}:{project.aws_account_id}:*/{cluster}/*'
                    )

                policy_dict = {
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Sid': 'EcsWriteAccess',
                            'Effect': 'Allow',
                            'Action': ['ecs:*'],
                            'Resource': ecs_write_resources,
                        },
                        {
                            'Sid': 'DescribeTaskDefs',
                            'Effect': 'Allow',
                            'Action': ['ecs:DescribeTaskDefinition'],
                            'Resource': ['*'],
                        },
                        {
                            'Sid': 'RegisterTaskDef',
                            'Effect': 'Allow',
                            'Action': ['ecs:RegisterTaskDefinition'],
                            'Resource': [
                                f'arn:aws:ecs:{project.aws_region}:{project.aws_account_id}:task-definition/{cluster}:*'
                                for cluster in fargate_clusters
                            ],
                        },
                        {
                            'Sid': 'GlobalObjectReadAccess',
                            'Effect': 'Allow',
                            'Action': [
                                'cloudwatch:Describe*',
                                'cloudwatch:List*',
                                'cloudwatch:TagResource',
                                'ec2:List*',
                                'ec2:Get*',
                                'ec2:Describe*',
                                'ecs:DeregisterTaskDefinition',
                                'elasticloadbalancing:Describe*',
                                's3:ListAllMyBuckets',
                            ],
                            'Resource': ['*'],
                        },
                        {
                            'Sid': 'IamFargateAuth',
                            'Effect': 'Allow',
                            'Action': ['iam:PassRole'],
                            'Resource': fargate_task_role_arns,
                        },
                    ],
                }
                policy_json = json.dumps(policy_dict)
                fargate_deployment_policy = aws.iam.Policy(
                    f'{name}-policy-fargatedeploy',
                    name=f'{name}-s3-fargatedeploy',
                    description=f'Allows CI automation for {project.project} to deploy images to Fargate clusters.',
                    policy=policy_json,
                    opts=pulumi.ResourceOptions(parent=self),
                    tags=self.tags,
                )
                fargate_deployment_policy_attachment = aws.iam.PolicyAttachment(  # noqa: F841
                    f'{name}-polatt-fargatedeploy',
                    users=[user],
                    policy_arn=fargate_deployment_policy.arn,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[fargate_deployment_policy, user]),
                )

                # Attach all other policies
                for idx, policy in enumerate(additional_policies):
                    aws.iam.PolicyAttachment(
                        f'{name}-polatt-additional-{idx}',
                        users=[user],
                        policy_arn=policy,
                        opts=pulumi.ResourceOptions(parent=self, depends_on=[user]),
                    )

            self.finish(
                resources={
                    'user': user,
                    'access_key': access_key,
                    'secret': secret,
                    'ecr_image_push_policy': ecr_image_push_policy if enable_ecr_image_push else None,
                    's3_upload_policy': s3_upload_policy if enable_s3_bucket_upload else None,
                    's3_full_access_policy': s3_full_access_policy if enable_full_s3_access else None,
                    'fargate_deployment_policy': fargate_deployment_policy if enable_fargate_deployments else None,
                },
            )
        else:
            msg = (
                f'The current stack is "{project.stack}", but CI components are associated with the '
                + f'"{active_stack}" stack. These resources will be skipped on this run.'
            )
            pulumi.info(msg)
            self.finish(
                outputs={'user_name': None},
                resources={
                    'user': None,
                    'access_key': None,
                    'secret': None,
                    'ecr_image_push_policy': None,
                    's3_upload_policy': None,
                    's3_full_access_policy': None,
                    'fargate_deployment_policy': None,
                },
            )
