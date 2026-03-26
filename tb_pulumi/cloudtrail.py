import pulumi
import pulumi_aws as aws
import tb_pulumi
import tb_pulumi.cloudwatch


class EventMonitor(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type: tb:cloudtrail:EventMonitor**
    
    Creates a CloudTrail Trail, then uses a Metric Filter as a basis for alerting when certain
    events occur within AWS. This pattern is largely based on the process described in AWS's article
    `Creating CloudWatch alarms for CloudTrail events: examples
    <https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudwatch-alarms-for-cloudtrail.html>`_.

    Each CloudTrail Trail requires an S3 bucket for storing event data (even if you intend to use CloudWatch Logs to
    surface events). We provide the :py:class:`tb_pulumi.s3.S3Bucket` pattern if you need to build one.
    
    Produces the following ``resources``:

        - *whatever* - blah blah
          blah blah

    :param name: The name of the ``CloudWatchMonitoringGroup`` resource.
    :type name: str

    :param project: The ``ThunderbirdPulumiProject`` to build monitoring resources for.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param opts: Additional ``pulumi.ResourceOptions`` to apply to this resource. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param tags: Key/value pairs to merge with the default tags which get applied to all resources in this group.
        Defaults to {}.
    :type tags: dict, optional
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        log_destination: dict = {},
        s3_bucket_name: str = None,
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
    ):
        super().__init__(
            pulumi_type='tb:cloudtrail:EventMonitor',
            name=name,
            project=project,
            opts=opts,
            tags=tags,
        )

        __log_group = tb_pulumi.cloudwatch.LogDestination(
            f'{name}-logdest',
            project=self.project,
            **log_destination,
            opts=pulumi.ResourceOptions(parent=self),
            tags=self.tags,
            exclude_from_project=True,
        )

        __trail = aws.cloudtrail.Trail(
            f'{name}-trail',
            s3_bucket_name
        )

        self.finish(
            resources={
            }
        )