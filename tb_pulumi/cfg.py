"""Patterns related to AWS Config integration."""

import pulumi
import pulumi_aws as aws
import tb_pulumi
import tb_pulumi.s3


class AwsConfigAccount(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:cfg:ConfigAccount``
    Enable and Configure AWS Config for an account/region.

    Produces the following ``resources``:

    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        delivery_email: str = '',
        aggregator_stack: bool = False,
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
        **kwargs,
    ):
        exclude_from_project = kwargs.pop('exclude_from_project', False)
        if 'exclude_from_project' in kwargs:
            exclude_from_project = kwargs['exclude_from_project'] or False
            del kwargs['exclude_from_project']

        super().__init__(
            'tb:cfg:ConfigAccount',
            name=f'{name}-cfgacc',
            project=project,
            exclude_from_project=exclude_from_project,
            opts=opts,
            tags=tags,
        )

        # create s3 bucket for config delivery channel
        bucket_name = f'{project.project}-{project.stack}-config'
        delivery_bucket = tb_pulumi.s3.S3Bucket(
            f'{project.project}-{project.stack}-config-bucket',
            bucket_name=bucket_name,
            project=project,
            opts=pulumi.ResourceOptions(parent=self),
            tags=self.tags,
        )
        # bucket policy to allow config to write to bucket
        delivery_bucket_policy_json = tb_pulumi.constants.IAM_POLICY_DOCUMENT.copy()
        delivery_bucket_policy_json['Statement'] = [
            {
                'Effect': 'Allow',
                'Principal': {'Service': 'config.amazonaws.com'},
                'Action': [
                    's3:PutObject',
                    's3:PutObjectAcl',
                ],
                'Resource': f'arn:aws:s3:::{bucket_name}/AWSLogs/{project.aws_account_id}/*',
                'Condition': {'StringEquals': {'s3:x-amz-acl': 'bucket-owner-full-control'}},
            },
            {
                'Effect': 'Allow',
                'Principal': {'Service': 'config.amazonaws.com'},
                'Action': 's3:GetBucketAcl',
                'Resource': f'arn:aws:s3:::{bucket_name}',
            },
        ]

        delivery_bucket_policy = aws.s3.BucketPolicy(
            f'{name}-config-bucket-policy',
            bucket=bucket_name,
            policy=delivery_bucket_policy_json,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[delivery_bucket]),
        )

        # recorder config
        recording_group = {
            'all_supported': True,
            'include_global_resource_types': True,
        }
        recording_mode = {
            'recording_frequency': 'CONTINUOUS',
        }

        # Reference the existing service-linked role ARN
        config_service_linked_role_arn = (
            f'arn:aws:iam::{project.aws_account_id}:role/aws-service-role/config.amazonaws.com/AWSServiceRoleForConfig'
        )

        # create config recorder
        recorder = aws.cfg.Recorder(
            f'{project.project}-{project.stack}-config-recorder',
            role_arn=config_service_linked_role_arn,
            recording_group=recording_group,
            recording_mode=recording_mode,
            opts=pulumi.ResourceOptions(depends_on=[self]),
        )

        # enable the recorder
        recorder_status = aws.cfg.RecorderStatus(
            f'{project.project}-{project.stack}-config-recorder-status',
            name=recorder.name,
            is_enabled=True,
            opts=pulumi.ResourceOptions(parent=recorder),
        )

        # create delivery channel SNS topic
        delivery_channel_sns_topic = (
            aws.sns.Topic(
                f'{project.project}-{project.stack}-delivery-channel-sns-topic',
                display_name=f'{name} Delivery Channel SNS Topic',
                opts=pulumi.ResourceOptions(parent=self),
                tags=self.tags,
            )
            if aggregator_stack
            else None
        )

        # delivery channel sns topic email subscription if defined
        delivery_channel_email_subscription = (
            aws.sns.TopicSubscription(
                f'{project.project}-{project.stack}-delivery-channel-email-subscription',
                topic=delivery_channel_sns_topic,
                protocol='email',
                endpoint=delivery_email,
                opts=pulumi.ResourceOptions(parent=delivery_channel_sns_topic),
            )
            if delivery_email and aggregator_stack
            else None
        )

        # create delivery channel
        delivery_channel = aws.cfg.DeliveryChannel(
            f'{name}-delivery-channel',
            s3_bucket_name=bucket_name,
            snapshot_delivery_properties={},
            sns_topic_arn=delivery_channel_sns_topic.arn if delivery_channel_sns_topic else None,
            opts=pulumi.ResourceOptions(
                parent=recorder,
                depends_on=[delivery_bucket, delivery_bucket_policy, recorder],
            ),
        )

        aggregator_account = (
            aws.cfg.ConfigurationAggregator(
                f'{project.project}-{project.stack}-account-agg',
                name=f'{project.project}-{project.stack}-account-agg',
                account_aggregation_source={
                    'account_ids': [f'{project.aws_account_id}'],
                    'all_regions': True,
                    # "regions": ["us-east-1"],
                },
                tags=self.tags,
            )
            if aggregator_stack
            else None
        )

        self.finish(
            resources={
                'delivery_bucket': delivery_bucket,
                'delivery_bucket_policy': delivery_bucket_policy,
                'recorder': recorder,
                'recorder_status': recorder_status,
                'delivery_channel_sns_topic': delivery_channel_sns_topic,
                'delivery_channel_email_subscription': delivery_channel_email_subscription,
                'delivery_channel': delivery_channel,
                'aggregator_account': aggregator_account,
            }
        )
