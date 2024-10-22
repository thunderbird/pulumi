"""Patterns related to continuous integration."""

import json
import pulumi
import pulumi_aws as aws
import tb_pulumi


class AwsAutomationUser(tb_pulumi.ThunderbirdComponentResource):
    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        active_stack: str = 'staging',
        enable_ecr_image_push: bool = False,
        ecr_repositories: str = None,
        enable_fargate_deployments: str = None,
        fargate_clusters: str = None,
        fargate_task_role_arns: str = None,
        enable_full_s3_access: bool = False,
        s3_full_access_buckets: list = [],
        enable_s3_bucket_upload: bool = False,
        s3_upload_buckets: list = [],
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        super().__init__('tb:ci:Automationuser', name=name, project=project, opts=opts, **kwargs)

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
                                'ecr:ListImages',
                                'ecr:UploadLayerPart',
                                'ecr:PutImage',
                            ],
                            'Resource': [
                                f'arn:aws:ecr:{project.aws_region}:{project.aws_account_id}:repository/{repo}'
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
                    name=f'{name}-ci-ecr-push',
                    description=f'Allows CI automation for {project.project} to push container images to ECR.',
                    policy=policy_json,
                    opts=pulumi.ResourceOptions(parent=self),
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
                policy_dict = {
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Sid': 'PutObjects',
                            'Effect': 'Allow',
                            'Action': ['s3:PutObject'],
                            'Resource': [f'arn:aws:s3:::{bucket}/*' for bucket in s3_upload_buckets],
                        }
                    ],
                }
                policy_json = json.dumps(policy_dict)
                s3_upload_policy = aws.iam.Policy(
                    f'{name}-policy-s3upload',
                    name=f'{name}-ci-s3-upload',
                    description=f'Allows CI automation for {project.project} to upload files to certain S3 buckets.',
                    policy=policy_json,
                    opts=pulumi.ResourceOptions(parent=self),
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
                    ecs_write_resources.append(f'arn:aws:ecs:{project.aws_region}:{project.aws_account_id}:*/{cluster}')
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
                            'Sid': 'RegisterTaskDef',
                            'Effect': 'Allow',
                            'Action': ['ecs:RegisterTaskDefinition'],
                            'Resource': [
                                f'arn:aws:ecs:{project.aws_region}:{project.aws_account_id}:task-definition/{cluster}'
                                for cluster in fargate_clusters
                            ],
                        },
                        {
                            'Sid': 'GlobalObjectReadAccess',
                            'Effect': 'Allow',
                            'Action': [
                                'ec2:List*',
                                'ec2:Get*',
                                'ec2:Describe*',
                                'ecs:DeregisterTaskDefinition',
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
                    name=f'{name}-ci-s3-fargatedeploy',
                    description=f'Allggows CI automation for {project.project} to deploy images to Fargate clusters.',
                    policy=policy_json,
                    opts=pulumi.ResourceOptions(parent=self),
                )
                fargate_deployment_policy_attachment = aws.iam.PolicyAttachment(  # noqa: F841
                    f'{name}-polatt-fargatedeploy',
                    users=[user],
                    policy_arn=fargate_deployment_policy.arn,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[fargate_deployment_policy, user]),
                )
            self.finish(
                outputs={'user_name': user.name},
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
                f'The current stack is "{project.stack}", but CI components are associated with the'
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
