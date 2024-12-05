"""Infrastructural patterns related to AWS CloudWatch."""

import pulumi
import pulumi_aws as aws
import tb_pulumi
import tb_pulumi.monitoring


class CloudWatchMonitoringGroup(tb_pulumi.monitoring.MonitoringGroup):
    """A ``MonitoringGroup`` that monitors AWS-based resources using AWS's CloudWatch service. This creates an SNS topic
    to sent its alarms on.

    :param name: The name of the ``CloudWatchMonitoringGroup`` resource.
    :type name: str

    :param project: The ``ThunderbirdPulumiProject`` to build monitoring resources for.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param config: A configuration dictionary for this monitoring group. Documentation for
        :py:class:`tb_pulumi.monitoring.MonitoringGroup` defines the overall structure of this dict. The monitors are
        defined as CloudWatch Metric Alarms and can be configured with the inputs `documented here
        <https://www.pulumi.com/registry/packages/aws/api-docs/cloudwatch/metricalarm/>`_. Defaults to {}.
    :type config: dict, optional

    :param notify_emails: A list of email addresses to notify when an alarm activates.
    :type notify_emails: list, optional

    :param opts: Additional ``pulumi.ResourceOptions`` to apply to this resource. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        config: dict = {},
        notify_emails: list[str] = [],
        opts: pulumi.ResourceOptions = None,
    ):
        super().__init__(
            pulumi_type='tb:cloudwatch:CloudWatchMonitoringGroup', name=name, project=project, opts=opts, config=config
        )

        supported_types = {
            aws.lb.load_balancer.LoadBalancer: AlbAlarmGroup,
            aws.cloudfront.Distribution: CloudFrontAlarmGroup,
            aws.ecs.Service: EcsServiceAlarmGroup,
        }
        supported_resources = [
            resource for resource in self.project.flatten() if type(resource) in supported_types.keys()
        ]

        sns_topic = aws.sns.Topic(
            f'{name}-topic', name=f'{self.project.name_prefix}-alarms', opts=pulumi.ResourceOptions(parent=self)
        )

        # API details on SNS topic subscriptions can be found here:
        # https://docs.aws.amazon.com/sns/latest/api/API_Subscribe.html
        subscriptions = []
        for idx, email in enumerate(notify_emails):
            subscriptions.append(
                aws.sns.TopicSubscription(
                    f'{name}-snssub-{idx}',
                    protocol='email',
                    endpoint=email,
                    topic=sns_topic.arn,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[sns_topic]),
                )
            )

        alarms = {}
        for res in supported_resources:
            shortname = res._name.replace(f'{self.project.name_prefix}-', '')  # Make this name shorter, less redundant
            alarms[res._name] = supported_types[type(res)](
                name=f'{name}-{shortname}',
                project=self.project,
                resource=res,
                monitoring_group=self,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[res]),
            )

        self.finish(
            outputs={'sns_topic_arn': sns_topic.arn},
            resources={'sns_topic': sns_topic, 'sns_subscriptions': subscriptions, 'alarms': alarms},
        )


class AlbAlarmGroup(tb_pulumi.monitoring.AlarmGroup):
    """A set of alarms for Application Load Balancers. Contains the following configurable alarms:

        - ``fivexx``: Alarms on the number of HTTP responses with status codes in the 500-599 range, indicating a count
          of internal server errors.
        - ``response_time``: Alarms on the response time of HTTP requests. Threshold should be set in seconds.

    :param name: The name of the the ``AlbAlarmGroup`` resource.
    :type name: str

    :param monitoring_group: The ``CloudWatchMonitoringGroup`` this alarm group belongs to.
    :type monitoring_group: CloudWatchMonitoringGroup

    :param project: The ``ThunderbirdPulumiProject`` being monitored.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param resource: The ``aws.lb.load_balancer.LoadBalancer`` being monitored.
    :type resource: aws.lb.load_balancer.LoadBalancer

    :param opts: Additional ``pulumi.ResourceOptions`` to apply to this resource. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional
    """

    def __init__(
        self,
        name: str,
        monitoring_group: CloudWatchMonitoringGroup,
        project: tb_pulumi.ThunderbirdPulumiProject,
        resource: aws.lb.load_balancer.LoadBalancer,
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        super().__init__(
            pulumi_type='tb:cloudwatch:AlbAlarmGroup',
            name=name,
            monitoring_group=monitoring_group,
            project=project,
            resource=resource,
            opts=opts,
            **kwargs,
        )

        # Alert if we see sustained 5xx statuses
        fivexx_opts = {'enabled': True, 'evaluation_periods': 2, 'period': 300, 'statistic': 'Average', 'threshold': 10}
        fivexx_opts.update(self.overrides['fivexx'] if 'fivexx' in self.overrides else {})
        fivexx_enabled = fivexx_opts['enabled']
        del fivexx_opts['enabled']
        fivexx = pulumi.Output.all(res_name=resource.name, res_suffix=resource.arn_suffix).apply(
            lambda outputs: aws.cloudwatch.MetricAlarm(
                f'{self.name}-4xx',
                name=f'{self.project.name_prefix}-4xx',
                alarm_actions=[monitoring_group.resources['sns_topic'].arn],
                comparison_operator='GreaterThanOrEqualToThreshold',
                dimensions={'LoadBalancer': outputs['res_suffix']},
                metric_name='HTTPCode_ELB_5XX_Count',
                namespace='AWS/ApplicationELB',
                alarm_description=f'Elevated 4xx errors on ALB {outputs['res_name']}',
                opts=pulumi.ResourceOptions(
                    parent=self, depends_on=[resource, monitoring_group.resources['sns_topic']]
                ),
                **fivexx_opts,
            )
            if fivexx_enabled
            else None
        )
        fivexx = ()

        # Alert if response time is elevated over time
        response_time_opts = {
            'enabled': True,
            'evaluation_periods': 2,
            'period': 300,
            'statistic': 'Average',
            'threshold': 1,
        }
        response_time_opts.update(self.overrides['response_time'] if 'response_time' in self.overrides else {})
        response_time_enabled = response_time_opts['enabled']
        del response_time_opts['enabled']
        response_time = pulumi.Output.all(res_name=resource.name, res_suffix=resource.arn_suffix).apply(
            lambda outputs: aws.cloudwatch.MetricAlarm(
                f'{self.name}-responsetime',
                name=f'{self.project.name_prefix}-responsetime',
                alarm_actions=[monitoring_group.resources['sns_topic'].arn],
                comparison_operator='GreaterThanOrEqualToThreshold',
                dimensions={'LoadBalancer': outputs['res_suffix']},
                metric_name='TargetResponseTime',
                namespace='AWS/ApplicationELB',
                alarm_description=f'Average response time is over {response_time_opts['threshold']} second(s) for {response_time_opts['period']} seconds',  # noqa: E501
                opts=pulumi.ResourceOptions(
                    parent=self, depends_on=[resource, monitoring_group.resources['sns_topic']]
                ),
                **response_time_opts,
            )
            if response_time_enabled
            else None
        )

        self.finish(outputs={}, resources={'fivexx': fivexx, 'response_time': response_time})


class CloudFrontAlarmGroup(tb_pulumi.monitoring.AlarmGroup):
    """A set of alarms for CloudFront distributions and related resources. Contains the following configurable alarms:

    - ``distro_4xx``: Alarms on the number of HTTP responses with status codes in the 400-499 range, indicating an
        elevated number of calls to invalid files.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        resource: aws.ecs.Service,
        monitoring_group: CloudWatchMonitoringGroup,
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        super().__init__(
            pulumi_type='tb:cloudwatch:CloudFrontAlarmGroup',
            name=name,
            monitoring_group=monitoring_group,
            project=project,
            resource=resource,
            opts=opts,
            **kwargs,
        )

        # Alert if the distro reports an elevated error rate
        distro_4xx_opts = {
            'enabled': True,
            'evaluation_periods': 2,
            'period': 900,
            'statistic': 'Average',
            'threshold': 10,
        }
        distro_4xx_opts.update(self.overrides['distro_4xx'] if 'distro_4xx' in self.overrides else {})
        distro_4xx_enabled = distro_4xx_opts['enabled']
        del distro_4xx_opts['enabled']
        distro_4xx = pulumi.Output.all(res_id=resource.id, res_comment=resource.comment).apply(
            lambda outputs: aws.cloudwatch.MetricAlarm(
                f'{self.name}-4xx',
                name=f'{self.project.name_prefix}-4xx',
                alarm_actions=[monitoring_group.resources['sns_topic'].arn],
                comparison_operator='GreaterThanOrEqualToThreshold',
                dimensions={'DistributionId': outputs['res_id']},
                metric_name='4xxErrorRate',
                namespace='AWS/CloudFront',
                alarm_description=f'4xx error rate for CloudFront Distribution "{outputs['res_comment']}" exceeds '
                f'{distro_4xx_opts['threshold']} on average over {distro_4xx_opts['period']} seconds.',
                opts=pulumi.ResourceOptions(
                    parent=self, depends_on=[resource, monitoring_group.resources['sns_topic']]
                ),
                **distro_4xx_opts,
            )
            if distro_4xx_enabled
            else None
        )

        self.finish(outputs={}, resources={'distro_4xx': distro_4xx})


class EcsServiceAlarmGroup(tb_pulumi.monitoring.AlarmGroup):
    """A set of alarms for ECS services. Contains the following configurable alarms:

        - ``cpu_utilization``: Alarms on the overall CPU usage of the entire service, all tasks combined. Threshold is a
            percentage.
        - ``memory_utilization``: Alarms on the overall memory usage of the entire service, all tasks combined.
            Threshold is a percentage.

    :param name: The name of the ``EcsServiceAlarmGroup`` resource.
    :type name: str

    :param project: The ``ThunderbirdPulumiProject`` being monitored.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param resource: The Pulumi resource being monitored.
    :type resource: aws.ecs.Service

    :param monitoring_group: The ``CloudWatchMonitoringGroup`` this is a member of.
    :type monitoring_group: CloudWatchMonitoringGroup

    :param opts: Additional ``pulumi.ResourceOptions`` to apply to this resource. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        resource: aws.ecs.Service,
        monitoring_group: CloudWatchMonitoringGroup,
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        super().__init__(
            pulumi_type='tb:cloudwatch:EcsServiceAlarmGroup',
            name=name,
            monitoring_group=monitoring_group,
            project=project,
            resource=resource,
            opts=opts,
            **kwargs,
        )

        # Alert if we see overall elevated CPU consumption
        cpu_utilization_opts = {
            'enabled': True,
            'evaluation_periods': 2,
            'period': 300,
            'statistic': 'Average',
            'threshold': 80,
        }
        cpu_utilization_opts.update(self.overrides['cpu_utilization'] if 'cpu_utilization' in self.overrides else {})
        cpu_utilization_enabled = cpu_utilization_opts['enabled']
        del [cpu_utilization_opts['enabled']]
        cpu_utilization = pulumi.Output.all(res_name=resource.name, cluster_arn=resource.cluster).apply(
            lambda outputs: aws.cloudwatch.MetricAlarm(
                f'{self.name}-cpu',
                name=f'{self.project.name_prefix}-cpu',
                alarm_actions=[monitoring_group.resources['sns_topic'].arn],
                comparison_operator='GreaterThanOrEqualToThreshold',
                # There is no direct way to get the Cluster name from a Service, but we can get the ARN, which has the
                # name as the final portion after the last slash.
                dimensions={'ClusterName': outputs['cluster_arn'].split('/')[-1], 'ServiceName': outputs['res_name']},
                metric_name='CPUUtilization',
                namespace='AWS/ECS',
                alarm_description=f'CPU utilization on the {outputs['res_name']} cluster exceeds '
                f'{cpu_utilization_opts['threshold']}%',
                opts=pulumi.ResourceOptions(
                    parent=self, depends_on=[resource, monitoring_group.resources['sns_topic']]
                ),
                **cpu_utilization_opts,
            )
            if cpu_utilization_enabled
            else None
        )

        # Alert if we see overall elevated memory consumption
        memory_utilization_opts = {
            'enabled': True,
            'evaluation_periods': 2,
            'period': 300,
            'statistic': 'Average',
            'threshold': 80,
        }
        memory_utilization_opts.update(
            self.overrides['memory_utilization'] if 'memory_utilization' in self.overrides else {}
        )
        memory_utilization_enabled = memory_utilization_opts['enabled']
        del memory_utilization_opts['enabled']
        memory_utilization = pulumi.Output.all(res_name=resource.name, cluster_arn=resource.cluster).apply(
            lambda outputs: aws.cloudwatch.MetricAlarm(
                f'{self.name}-memory',
                name=f'{self.project.name_prefix}-memory',
                alarm_actions=[monitoring_group.resources['sns_topic'].arn],
                comparison_operator='GreaterThanOrEqualToThreshold',
                # There is no direct way to get the Cluster name from a Service, but we can get the ARN, which has the
                # name as the final portion after the last slash.
                dimensions={'ClusterName': outputs['cluster_arn'].split('/')[-1], 'ServiceName': outputs['res_name']},
                metric_name='MemoryUtilization',
                namespace='AWS/ECS',
                alarm_description=f'Memory utilization on the {outputs['res_name']} cluster exceeds '
                f'{memory_utilization_opts['threshold']}%',
                opts=pulumi.ResourceOptions(
                    parent=self, depends_on=[resource, monitoring_group.resources['sns_topic']]
                ),
                **memory_utilization_opts,
            )
            if memory_utilization_enabled
            else None
        )

        self.finish(
            outputs={},
            resources={'cpu_utilization': cpu_utilization, 'memory_utilization': memory_utilization},
        )
