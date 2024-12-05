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
            aws.alb.target_group.TargetGroup: AlbTargetGroupAlarmGroup,
            aws.cloudfront.Distribution: CloudFrontDistributionAlarmGroup,
            aws.cloudfront.Function: CloudFrontFunctionAlarmGroup,
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
        # pulumi.info(f'All resources: {'\n'.join([str(res.__class__) for res in self.project.flatten()])}')
        # pulumi.info(f'Supported resources: {supported_resources}')
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
                f'{self.name}-5xx',
                name=f'{outputs['res_name']}-5xx',
                alarm_actions=[monitoring_group.resources['sns_topic'].arn],
                comparison_operator='GreaterThanOrEqualToThreshold',
                dimensions={'LoadBalancer': outputs['res_suffix']},
                metric_name='HTTPCode_ELB_5XX_Count',
                namespace='AWS/ApplicationELB',
                alarm_description=f'Elevated 5xx errors on ALB {outputs['res_name']}',
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
                name=f'{outputs['res_name']}-responsetime',
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


class AlbTargetGroupAlarmGroup(tb_pulumi.monitoring.AlarmGroup):
    """A set of alarms for ALB target groups. Contains the following configurable alarms:

    - ``unhealthy_hosts``: Alarms on the number of unhealthy hosts in a target group.
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
            pulumi_type='tb:cloudwatch:CloudFrontDistributionAlarmGroup',
            name=name,
            monitoring_group=monitoring_group,
            project=project,
            resource=resource,
            opts=opts,
            **kwargs,
        )

        # Alert if there are unhealthy hosts
        unhealthy_hosts_opts = {
            'enabled': True,
            'evaluation_periods': 2,
            'period': 300,
            'statistic': 'Average',
            'threshold': 1,
        }
        unhealthy_hosts_opts.update(self.overrides['unhealthy_hosts'] if 'unhealthy_hosts' in self.overrides else {})
        unhealthy_hosts_enabled = unhealthy_hosts_opts['enabled']
        print(unhealthy_hosts_enabled)
        del unhealthy_hosts_opts['enabled']

        # TargetGroups can be attached to multiple LBs. This metric depends on "ARN suffixes" (a special ID that
        # CloudWatch uses to identify certain resources) for both the target group and the load balancer. Therefore, we
        # must look up those LBs and get their ARN suffixes prior to building these alarms. Additionally complicating
        # this is the fact that the load_balancer_arns do not seem to populate as part of the resource itself, but *do*
        # populate when you make the .get() call for the resource. (This might be a bug in the AWS provider; I couldn't
        # find any existing problem reports, though.) This and the dependency on a chain of Outputs whose values are not
        # guaranteed to be available at the time these statements are called necessitates this ugly nested function
        # call structure.
        unhealthy_hosts = pulumi.Output.all(tg_arn=resource.arn, tg_arn_suffix=resource.arn_suffix).apply(
            lambda outputs: self.__unhealthy_hosts(
                target_group_arn=outputs['tg_arn'],
                target_group_arn_suffix=outputs['tg_arn_suffix'],
                alarm_opts=unhealthy_hosts_opts,
            )
            if unhealthy_hosts_enabled
            else []
        )

        self.finish(outputs={}, resources={'unhealthy_hosts': unhealthy_hosts})

    def __unhealthy_hosts(self, target_group_arn, target_group_arn_suffix, alarm_opts):
        target_group = aws.lb.TargetGroup.get('tg', id=target_group_arn)
        return pulumi.Output.all(tg_suffix=target_group.arn_suffix, lb_arns=target_group.load_balancer_arns).apply(
            lambda outputs: [
                self.__unhealthy_hosts_metric_alarm(
                    target_group=target_group,
                    tg_suffix=outputs['tg_suffix'],
                    lb_suffix=lb_suffix,
                    alarm_opts=alarm_opts,
                )
                for lb_suffix in [
                    aws.lb.LoadBalancer.get(resource_name=f'lb-{idx}', id=arn_suffix).arn_suffix
                    for idx, arn_suffix in enumerate(outputs['lb_arns'])
                ]
            ]
        )

    def __unhealthy_hosts_metric_alarm(self, target_group, tg_suffix, lb_suffix, alarm_opts):
        # An arn_suffix looks like this: targetgroup/target_group_name/0123456789abcdef; extract that name part
        return pulumi.Output.all(tg_suffix=tg_suffix, lb_suffix=lb_suffix).apply(
            lambda outputs: aws.cloudwatch.MetricAlarm(
                f'{self.name}-unhealthy-hosts',
                name=f'{outputs['tg_suffix'].split('/')[1]}-{outputs['lb_suffix'].split('/')[1]}-unhealthy-hosts',
                alarm_actions=[self.monitoring_group.resources['sns_topic'].arn],
                comparison_operator='GreaterThanOrEqualToThreshold',
                dimensions={'TargetGroup': outputs['tg_suffix'], 'LoadBalancer': outputs['lb_suffix']},
                metric_name='UnHealthyHostCount',
                namespace='AWS/ApplicationELB',
                alarm_description=f'{outputs['tg_suffix'].split('/')[1]} has detected unhealthy hosts in load balancer '
                f'{outputs['lb_suffix'].split('/')[1]}',
                opts=pulumi.ResourceOptions(
                    parent=self, depends_on=[target_group, self.monitoring_group.resources['sns_topic']]
                ),
                **alarm_opts,
            )
        )


class CloudFrontDistributionAlarmGroup(tb_pulumi.monitoring.AlarmGroup):
    """A set of alarms for CloudFront distributions. Contains the following configurable alarms:

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
            pulumi_type='tb:cloudwatch:CloudFrontDistributionAlarmGroup',
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
                name=f'{self.project.name_prefix}-cfdistro-{outputs['res_id']}-4xx',
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


class CloudFrontFunctionAlarmGroup(tb_pulumi.monitoring.AlarmGroup):
    """A set of alarms for CloudFront functions. Contains the following configurable alarms:

    - ``cpu_utilization``: Alarms when the function's compute utilization is excessive.
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
            pulumi_type='tb:cloudwatch:CloudFrontFunctionAlarmGroup',
            name=name,
            monitoring_group=monitoring_group,
            project=project,
            resource=resource,
            opts=opts,
            **kwargs,
        )

        # Alert if the function's CPU utilization is too high
        cpu_utilization_opts = {
            'enabled': True,
            'evaluation_periods': 2,
            'period': 300,
            'statistic': 'Average',
            'threshold': 80,
        }
        cpu_utilization_opts.update(self.overrides['cpu_utilization'] if 'cpu_utilization' in self.overrides else {})
        cpu_utilization_enabled = cpu_utilization_opts['enabled']
        del cpu_utilization_opts['enabled']
        cpu_utilization = (
            resource.name.apply(
                lambda res_name: aws.cloudwatch.MetricAlarm(
                    f'{self.name}-cpu',
                    name=f'{res_name}-cpu',
                    alarm_actions=[monitoring_group.resources['sns_topic'].arn],
                    comparison_operator='GreaterThanOrEqualToThreshold',
                    dimensions={'FunctionName': res_name},
                    metric_name='FunctionComputeUtilization',
                    namespace='AWS/CloudFront',
                    alarm_description=f'CPU utilization on CloudFront Function {res_name} exceeds '
                    f'{cpu_utilization_opts['threshold']}.',
                    opts=pulumi.ResourceOptions(
                        parent=self, depends_on=[resource, monitoring_group.resources['sns_topic']]
                    ),
                    **cpu_utilization_opts,
                )
            )
            if cpu_utilization_enabled
            else None
        )

        self.finish(outputs={}, resources={'cpu_utilization': cpu_utilization})


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
                name=f'{outputs['res_name']}-cpu',
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
                name=f'{outputs['res_name']}-memory',
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
