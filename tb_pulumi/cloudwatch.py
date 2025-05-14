"""Infrastructural patterns related to AWS CloudWatch."""

import pulumi
import pulumi_aws as aws
import tb_pulumi
import tb_pulumi.monitoring

from tb_pulumi.constants import CLOUDWATCH_METRIC_ALARM_DEFAULTS


class CloudWatchMonitoringGroup(tb_pulumi.monitoring.MonitoringGroup):
    """**Pulumi Type:** ``tb:cloudwatch:CloudWatchMonitoringGroup``

    A ``MonitoringGroup`` that monitors AWS-based resources using AWS's CloudWatch service and sends alerts using
    SNS-to-email.

    Produces the following ``resources``:

        - *sns_topic* - `aws.sns.Topic <https://www.pulumi.com/registry/packages/aws/api-docs/sns/topic/>`_ to notify
          when an alarm in this monitoring group is triggered.
        - *sns_subscriptions* - A list of `aws.sns.TopicSubscription
          <https://www.pulumi.com/registry/packages/aws/api-docs/sns/topicsubscription/>`_s, one for each entry in
          ``notify_emails``.
        - *alarms* - A list of alarms contained in this monitoring group. These may be any kind of alarm in the
          `aws.cloudwatch <https://www.pulumi.com/registry/packages/aws/api-docs/cloudwatch/>`_ library.

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

    :param tags: Key/value pairs to merge with the default tags which get applied to all resources in this group.
        Defaults to {}.
    :type tags: dict, optional

    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        config: dict = {},
        notify_emails: list[str] = [],
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
    ):
        type_map = {
            aws.ec2.Instance: Ec2InstanceAlarmGroup,
            aws.lb.load_balancer.LoadBalancer: LoadBalancerAlarmGroup,
            aws.alb.target_group.TargetGroup: AlbTargetGroupAlarmGroup,
            aws.lb.target_group.TargetGroup: AlbTargetGroupAlarmGroup,
            aws.cloudfront.Distribution: CloudFrontDistributionAlarmGroup,
            aws.cloudfront.Function: CloudFrontFunctionAlarmGroup,
            aws.ecs.Service: EcsServiceAlarmGroup,
        }

        self.notify_emails = notify_emails

        super().__init__(
            pulumi_type='tb:cloudwatch:CloudWatchMonitoringGroup',
            name=name,
            project=project,
            type_map=type_map,
            opts=opts,
            tags=tags,
            config=config,
        )

    def monitor(self, outputs):
        """This function gets called only after all outputs in the project have been resolved into values. It constructs
        all monitors for the resources in this project.

        :param outputs: A list of resolved outputs discovered in the project.
        :type outputs: list
        """

        sns_topic = aws.sns.Topic(
            f'{self.name}-topic',
            name=f'{self.project.name_prefix}-alarms',
            opts=pulumi.ResourceOptions(parent=self),
            tags=self.tags,
        )

        # API details on SNS topic subscriptions can be found here:
        # https://docs.aws.amazon.com/sns/latest/api/API_Subscribe.html
        subscriptions = []
        for idx, email in enumerate(self.notify_emails):
            subscriptions.append(
                aws.sns.TopicSubscription(
                    f'{self.name}-snssub-{idx}',
                    protocol='email',
                    endpoint=email,
                    topic=sns_topic.arn,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[sns_topic]),
                )
            )

        alarms = {}

        for res in set(self.supported_resources):
            shortname = res._name.replace(f'{self.project.name_prefix}-', '')  # Make this name shorter, less redundant
            alarms[res._name] = self.type_map[type(res)](
                name=f'{self.name}-{shortname}',
                project=self.project,
                resource=res,
                monitoring_group=self,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[res]),
                tags=self.tags,
            )

        self.finish(
            resources={'sns_topic': sns_topic, 'sns_subscriptions': subscriptions, 'alarms': alarms},
        )


class LoadBalancerAlarmGroup(tb_pulumi.monitoring.AlarmGroup):
    """In AWS, a load balancer can have a handful of types: ``application`` , ``gateway`` , or ``network`` . The metrics
    emitted by the load balancer - and therefore the kinds of alarms we can build - depend on which type it is. However,
    all types are represented by the same class, ``aws.lb.load_balancer.LoadBalancer`` . This necessitates a class for
    disambiguation. The ``load_balancer_type`` is an Output, so here we wait until we can determine that type, then
    build the appropriate AlarmGroup class for the resource.

    :param name: The name of the alarm group resource.
    :type name: str

    :param monitoring_group: The ``MonitoringGroup`` that this ``AlarmGroup`` belongs to.
    :type monitoring_group: MonitoringGroup

    :param project: The ``ThunderbirdPulumiProject`` whose resources are being monitored.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param resource: The Pulumi ``Resource`` object this ``AlarmGroup`` is building alarms for.
    :type resource: pulumi.Resource

    :param opts: Additional ``pulumi.ResourceOptions`` to apply to this resource. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param kwargs: Any other keyword arguments which will be passed as inputs to the
        :py:class:`tb_pulumi.monitoring.AlarmGroup` superconstructor.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        resource: aws.lb.load_balancer.LoadBalancer,
        monitoring_group: CloudWatchMonitoringGroup,
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        # Internalize the data so we can access it later when we know what LB type we're dealing with
        self.name = name
        self.project = project
        self.resource = resource
        self.monitoring_group = monitoring_group
        self.opts = opts
        self.kwargs = kwargs

        resource.load_balancer_type.apply(lambda lb_type: self.__build_alarm_group(lb_type))

    def __build_alarm_group(self, lb_type: str):
        # ALBs have some useful metrics for alarms, but NLBs do not. Therefore, we don't do anything for NLBs.
        if lb_type == 'application':
            self.alarm_group = AlbAlarmGroup(
                name=self.name,
                project=self.project,
                resource=self.resource,
                monitoring_group=self.monitoring_group,
                opts=self.opts,
                **self.kwargs,
            )


class AlbAlarmGroup(tb_pulumi.monitoring.AlarmGroup):
    """**Pulumi Type:** ``tb:cloudwatch:AlbAlarmGroup``

    A set of alarms for Application Load Balancers. Contains the following configurable alarms:

        - ``alb_5xx``: Alarms on the number of HTTP responses sourced within the load balancer with status codes in the
          500-599 range, indicating a count of internal server errors. This metric concerns the load balancer itself,
          and does not contain any response codes generated by the targets. Defaults to alarming on 10 errors in 1
          minute.
        - ``target_5xx``: Alarms on the number of HTTP responses sourced within the load balancer's targets with status
          codes in the 500-599 range, indicating a count of internal server errors. This metric concerns the
          applications the load balancer points to, and does not contain any response codes generated by the load
          balancer itself. Defaults to alarming on 10 errors in 1 minute.
        - ``response_time``: Alarms on the average response time of HTTP requests. Defaults to alarming if the average
          response time over a minute is longer than 1 second.

    Further detail on these metrics and others can be found within `Amazon's ALB metrics documentation
    <https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-cloudwatch-metrics.html>`_.

    :param name: The name of the the ``AlbAlarmGroup`` resource.
    :type name: str

    :param project: The ``ThunderbirdPulumiProject`` being monitored.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param resource: The ``aws.lb.load_balancer.LoadBalancer`` being monitored.
    :type resource: aws.lb.load_balancer.LoadBalancer

    :param monitoring_group: The ``CloudWatchMonitoringGroup`` this alarm group belongs to.
    :type monitoring_group: CloudWatchMonitoringGroup

    :param opts: Additional ``pulumi.ResourceOptions`` to apply to this resource. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param kwargs: Any other keyword arguments which will be passed as inputs to the
        :py:class:`tb_pulumi.monitoring.AlarmGroup` superconstructor.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        resource: aws.lb.load_balancer.LoadBalancer,
        monitoring_group: CloudWatchMonitoringGroup,
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

        # Alert if we see sustained 5xx statuses on the ALB itself (not on the target groups)
        alb_5xx_name = 'alb_5xx'
        alb_5xx_opts = CLOUDWATCH_METRIC_ALARM_DEFAULTS.copy()
        alb_5xx_opts.update({'statistic': 'Sum', **self.overrides.get(alb_5xx_name, {})})
        alb_5xx_enabled = alb_5xx_opts['enabled']
        del alb_5xx_opts['enabled']
        alb_5xx_tags = {'tb_pulumi_alarm_name': alb_5xx_name}
        alb_5xx_tags.update(self.tags)
        alb_5xx = pulumi.Output.all(res_name=resource.name, res_suffix=resource.arn_suffix).apply(
            lambda outputs: aws.cloudwatch.MetricAlarm(
                f'{self.name}-alb5xx',
                name=f'{outputs["res_name"]}-alb5xx',
                alarm_actions=[monitoring_group.resources['sns_topic'].arn],
                comparison_operator='GreaterThanOrEqualToThreshold',
                dimensions={'LoadBalancer': outputs['res_suffix']},
                metric_name='HTTPCode_ELB_5XX_Count',
                namespace='AWS/ApplicationELB',
                alarm_description=f'Elevated 5xx errors on ALB {outputs["res_name"]}',
                tags=alb_5xx_tags,
                opts=pulumi.ResourceOptions(
                    parent=self, depends_on=[resource, monitoring_group.resources['sns_topic']]
                ),
                **alb_5xx_opts,
            )
            if alb_5xx_enabled
            else None
        )

        # Alert if we see sustained 5xx statuses on the targets of the ALB (from the application)
        target_5xx_name = 'target_5xx'
        target_5xx_opts = CLOUDWATCH_METRIC_ALARM_DEFAULTS.copy()
        target_5xx_opts.update({'statistic': 'Sum', **self.overrides.get(target_5xx_name, {})})
        target_5xx_enabled = target_5xx_opts['enabled']
        del target_5xx_opts['enabled']
        target_5xx_tags = {'tb_pulumi_alarm_name': target_5xx_name}
        target_5xx_tags.update(self.tags)
        target_5xx = pulumi.Output.all(res_name=resource.name, res_suffix=resource.arn_suffix).apply(
            lambda outputs: aws.cloudwatch.MetricAlarm(
                f'{self.name}-target5xx',
                name=f'{outputs["res_name"]}-target5xx',
                alarm_actions=[monitoring_group.resources['sns_topic'].arn],
                comparison_operator='GreaterThanOrEqualToThreshold',
                dimensions={'LoadBalancer': outputs['res_suffix']},
                metric_name='HTTPCode_ELB_5XX_Count',
                namespace='AWS/ApplicationELB',
                alarm_description=f'Elevated 5xx errors on the targets of ALB {outputs["res_name"]}',
                tags=target_5xx_tags,
                opts=pulumi.ResourceOptions(
                    parent=self, depends_on=[resource, monitoring_group.resources['sns_topic']]
                ),
                **target_5xx_opts,
            )
            if target_5xx_enabled
            else None
        )

        # Alert if response time is elevated over time
        response_time_name = 'response_time'
        response_time_opts = CLOUDWATCH_METRIC_ALARM_DEFAULTS.copy()
        response_time_opts.update({'threshold': 1, **self.overrides.get(response_time_name, {})})
        response_time_enabled = response_time_opts['enabled']
        del response_time_opts['enabled']
        response_time_tags = {'tb_pulumi_alarm_name': response_time_name}
        response_time_tags.update(self.tags)
        response_time = pulumi.Output.all(res_name=resource.name, res_suffix=resource.arn_suffix).apply(
            lambda outputs: aws.cloudwatch.MetricAlarm(
                f'{self.name}-responsetime',
                name=f'{outputs["res_name"]}-responsetime',
                alarm_actions=[monitoring_group.resources['sns_topic'].arn],
                comparison_operator='GreaterThanOrEqualToThreshold',
                dimensions={'LoadBalancer': outputs['res_suffix']},
                metric_name='TargetResponseTime',
                namespace='AWS/ApplicationELB',
                alarm_description=f'Average response time is over {response_time_opts["threshold"]} second(s) for {response_time_opts["period"]} seconds',  # noqa: E501
                tags=response_time_tags,
                opts=pulumi.ResourceOptions(
                    parent=self, depends_on=[resource, monitoring_group.resources['sns_topic']]
                ),
                **response_time_opts,
            )
            if response_time_enabled
            else None
        )

        self.finish(
            outputs={},
            resources={alb_5xx_name: alb_5xx, target_5xx_name: target_5xx, response_time_name: response_time},
        )


class AlbTargetGroupAlarmGroup(tb_pulumi.monitoring.AlarmGroup):
    """**Pulumi Type:** ``tb:cloudwatch:CloudFrontDistributionAlarmGroup``

    A set of alarms for ALB target groups. Contains the following configurable alarms:

        - ``unhealthy_hosts``: Alarms on the number of unhealthy hosts in a target group. Defaults to alarm when the
          average of unhealthy hosts is over 1 in 1 minute.

    Further detail on these metrics and others can be found within `Amazon's Target Group metric documentation
    <https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-cloudwatch-metrics.html#target-metric-table>`_.

    :param name: The name of the the ``AlbTargetGroupAlarmGroup`` resource.
    :type name: str

    :param project: The ``ThunderbirdPulumiProject`` being monitored.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param resource: The ``aws.lb.target_group.TargetGroup`` being monitored.
    :type resource: aws.lb.target_group.TargetGroup

    :param monitoring_group: The ``CloudWatchMonitoringGroup`` this alarm group belongs to.
    :type monitoring_group: CloudWatchMonitoringGroup

    :param opts: Additional ``pulumi.ResourceOptions`` to apply to this resource. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param kwargs: Any other keyword arguments which will be passed as inputs to the
        :py:class:`tb_pulumi.monitoring.AlarmGroup` superconstructor.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        resource: aws.lb.target_group.TargetGroup,
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
        unhealth_hosts_name = 'unhealthy_hosts'
        unhealthy_hosts_opts = CLOUDWATCH_METRIC_ALARM_DEFAULTS.copy()
        unhealthy_hosts_opts.update({'threshold': 1, **self.overrides.get(unhealth_hosts_name, {})})
        unhealthy_hosts_enabled = unhealthy_hosts_opts['enabled']
        del unhealthy_hosts_opts['enabled']
        unhealthy_hosts_tags = {'tb_pulumi_alarm_name': unhealth_hosts_name}
        unhealthy_hosts_tags.update(self.tags)

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
                tags=unhealthy_hosts_tags,
            )
            if unhealthy_hosts_enabled
            else []
        )

        self.finish(outputs={}, resources={unhealth_hosts_name: unhealthy_hosts})

    def __unhealthy_hosts(self, target_group_arn: str, target_group_arn_suffix: str, alarm_opts: dict, tags: dict):
        target_group = aws.lb.TargetGroup.get('tg', id=target_group_arn)
        return pulumi.Output.all(tg_suffix=target_group.arn_suffix, lb_arns=target_group.load_balancer_arns).apply(
            lambda outputs: [
                self.__unhealthy_hosts_metric_alarm(
                    target_group=target_group,
                    tg_suffix=outputs['tg_suffix'],
                    lb_suffix=lb_suffix,
                    alarm_opts=alarm_opts,
                    tags=tags,
                )
                for lb_suffix in [
                    aws.lb.LoadBalancer.get(resource_name=f'lb-{idx}', id=arn_suffix).arn_suffix
                    for idx, arn_suffix in enumerate(outputs['lb_arns'])
                ]
            ]
        )

    def __unhealthy_hosts_metric_alarm(
        self, target_group: str, tg_suffix: str, lb_suffix: str, alarm_opts: dict, tags: dict
    ):
        # An arn_suffix looks like this: targetgroup/target_group_name/0123456789abcdef; extract that name part
        return pulumi.Output.all(tg_suffix=tg_suffix, lb_suffix=lb_suffix).apply(
            lambda outputs: aws.cloudwatch.MetricAlarm(
                f'{self.name}-unhealthy-hosts',
                name=f'{outputs["tg_suffix"].split("/")[1]}-{outputs["lb_suffix"].split("/")[1]}-unhealthy-hosts',
                alarm_actions=[self.monitoring_group.resources['sns_topic'].arn],
                comparison_operator='GreaterThanOrEqualToThreshold',
                dimensions={'TargetGroup': outputs['tg_suffix'], 'LoadBalancer': outputs['lb_suffix']},
                metric_name='UnHealthyHostCount',
                namespace='AWS/ApplicationELB',
                alarm_description=f'{outputs["tg_suffix"].split("/")[1]} has detected unhealthy hosts in load balancer '
                f'{outputs["lb_suffix"].split("/")[1]}',
                tags=tags,
                opts=pulumi.ResourceOptions(
                    parent=self, depends_on=[target_group, self.monitoring_group.resources['sns_topic']]
                ),
                **alarm_opts,
            )
        )


class CloudFrontDistributionAlarmGroup(tb_pulumi.monitoring.AlarmGroup):
    """**Pulumi type:** ``tb:cloudwatch:CloudFrontDistributionAlarmGroup``

    A set of alarms for CloudFront distributions. Contains the following configurable alarms:


        - ``distro_4xx``: Alarms on the rate of HTTP responses with status codes in the 400-499 range, indicating an
          elevated number of calls to invalid files. This value is reported as a percentage of all responses. Defaults
          to alarm on at least 10% 4xx codes in 1 minute.

    Further details about these metrics and more can be found in `Amazon's CloudFront distribution documentation
    <https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/programming-cloudwatch-metrics.html#cloudfront-metrics-distribution-values>`_.

    :param name: The name of the ``CloudFrontDistributionAlarmGroup`` resource.
    :type name: str

    :param project: The ``ThunderbirdPulumiProject`` being monitored.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param resource: The ``aws.cloudfront.Distribution`` being monitored.
    :type resource: aws.cloudfront.Distribution

    :param monitoring_group: The ``CloudWatchMonitoringGroup`` this alarm group belongs to.
    :type monitoring_group: CloudWatchMonitoringGroup

    :param opts: Additional ``pulumi.ResourceOptions`` to apply to this resource. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param kwargs: Any other keyword arguments which will be passed as inputs to the
        :py:class:`tb_pulumi.monitoring.AlarmGroup` superconstructor.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        resource: aws.cloudfront.Distribution,
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
        distro_4xx_name = 'distro_4xx'
        distro_4xx_opts = CLOUDWATCH_METRIC_ALARM_DEFAULTS.copy()
        distro_4xx_opts.update(self.overrides.get(distro_4xx_name, {}))
        distro_4xx_enabled = distro_4xx_opts['enabled']
        del distro_4xx_opts['enabled']
        distro_4xx_tags = {'tb_pulumi_alarm_name': distro_4xx_name}
        distro_4xx_tags.update(self.tags)
        distro_4xx = pulumi.Output.all(res_id=resource.id, res_comment=resource.comment).apply(
            lambda outputs: aws.cloudwatch.MetricAlarm(
                f'{self.name}-4xx',
                name=f'{self.project.name_prefix}-cfdistro-{outputs["res_id"]}-4xx',
                alarm_actions=[monitoring_group.resources['sns_topic'].arn],
                comparison_operator='GreaterThanOrEqualToThreshold',
                dimensions={'DistributionId': outputs['res_id']},
                metric_name='4xxErrorRate',
                namespace='AWS/CloudFront',
                alarm_description=f'4xx error rate for CloudFront Distribution "{outputs["res_comment"]}" exceeds '
                f'{distro_4xx_opts["threshold"]} on average over {distro_4xx_opts["period"]} seconds.',
                tags=distro_4xx_tags,
                opts=pulumi.ResourceOptions(
                    parent=self, depends_on=[resource, monitoring_group.resources['sns_topic']]
                ),
                **distro_4xx_opts,
            )
            if distro_4xx_enabled
            else None
        )

        self.finish(outputs={}, resources={distro_4xx_name: distro_4xx})


class CloudFrontFunctionAlarmGroup(tb_pulumi.monitoring.AlarmGroup):
    """**Pulumi Type:** ``tb:cloudwatch:CloudFrontFunctionAlarmGroup``

    A set of alarms for CloudFront functions. Contains the following configurable alarms:

        - ``cpu_utilization``: Alarms when the function's compute utilization is excessive. This value is reported as a
          percentage of its allotted CPU. Defaults to alarm when the function's CPU usage has been over 80% on average
          for 1 minute.

    Further details about these metrics and more can be found in `Amazon's CloudFront Functions documentation
    <https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/programming-cloudwatch-metrics.html#cloudfront-metrics-function-values>`_.

    :param name: The name of the the ``CloudFrontFunctionAlarmGroup`` resource.
    :type name: str

    :param project: The ``ThunderbirdPulumiProject`` being monitored.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param resource: The ``aws.cloudfront.Function`` being monitored.
    :type resource: aws.cloudfront.Function

    :param monitoring_group: The ``CloudWatchMonitoringGroup`` this alarm group belongs to.
    :type monitoring_group: CloudWatchMonitoringGroup

    :param opts: Additional ``pulumi.ResourceOptions`` to apply to this resource. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param kwargs: Any other keyword arguments which will be passed as inputs to the
        :py:class:`tb_pulumi.monitoring.AlarmGroup` superconstructor.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        resource: aws.cloudfront.Function,
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
        cpu_utilization_name = 'cpu_utilization'
        cpu_utilization_opts = CLOUDWATCH_METRIC_ALARM_DEFAULTS.copy()
        cpu_utilization_opts.update({'threshold': 80, **self.overrides.get(cpu_utilization_name, {})})
        cpu_utilization_enabled = cpu_utilization_opts['enabled']
        del cpu_utilization_opts['enabled']
        cpu_utilization_tags = {'tb_pulumi_alarm_name': cpu_utilization_name}
        cpu_utilization_tags.update(self.tags)
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
                    f'{cpu_utilization_opts["threshold"]}.',
                    tags=cpu_utilization_tags,
                    opts=pulumi.ResourceOptions(
                        parent=self, depends_on=[resource, monitoring_group.resources['sns_topic']]
                    ),
                    **cpu_utilization_opts,
                )
            )
            if cpu_utilization_enabled
            else None
        )

        self.finish(outputs={}, resources={cpu_utilization_name: cpu_utilization})


class Ec2InstanceAlarmGroup(tb_pulumi.monitoring.AlarmGroup):
    """**Pulumi Type:** ``tb:cloudwatch:Ec2InstanceAlarmGroup``

    A set of alarms for EC2 instances. Contains the following configurable alarms:

        - ``cpu_credit_balance``: Alarms if your instance is low on CPU credits.
        - ``cpu_utilization``: Alarms on the percentage of CPU time the instance is using.
        - ``ebs_status_failed``: Alarms if the EBS volume status check fails.
        - ``instance_status_failed``: Alarms if the EC2 instance status check fails.
        - ``system_status_failed``: Alarms if the system status check fails.

    Further detail on these metrics and more can be found on `Amazon's documentation
    <https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/viewing_metrics_with_cloudwatch.html>_`.

    :param name: The name of the ``Ec2InstanceAlarmGroup`` resource.
    :type name: str

    :param project: The ``ThunderbirdPulumiProject`` being monitored.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param resource: The Pulumi resource being monitored.
    :type resource: aws.ecs.Service

    :param monitoring_group: The ``CloudWatchMonitoringGroup`` this is a member of.
    :type monitoring_group: CloudWatchMonitoringGroup

    :param opts: Additional ``pulumi.ResourceOptions`` to apply to this resource. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param kwargs: Any other keyword arguments which will be passed as inputs to the
        :py:class:`tb_pulumi.monitoring.AlarmGroup` superconstructor.

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
            pulumi_type='tb:cloudwatch:Ec2InstanceAlarmGroup',
            name=name,
            monitoring_group=monitoring_group,
            project=project,
            resource=resource,
            opts=opts,
            **kwargs,
        )

        # Alert if we are low on CPU credits
        cpu_credit_balance_name = 'cpu_credit_balance'
        cpu_credit_balance_opts = CLOUDWATCH_METRIC_ALARM_DEFAULTS.copy()
        cpu_credit_balance_opts.update(
            {'period': 300, 'threshold': 30, **self.overrides.get(cpu_credit_balance_name, {})}
        )
        cpu_credit_balance_enabled = cpu_credit_balance_opts.pop('enabled')
        cpu_credit_balance_tags = {'tb_pulumi_alarm_name': cpu_credit_balance_name}
        cpu_credit_balance_tags.update(self.tags)
        cpu_credit_balance = pulumi.Output.all(res_name=resource.tags['Name'], instance_id=resource.id).apply(
            lambda outputs: aws.cloudwatch.MetricAlarm(
                f'{self.name}-cpucredit',
                name=f'{outputs["res_name"]}-cpucredit',
                alarm_actions=[monitoring_group.resources['sns_topic'].arn],
                comparison_operator='LessThanOrEqualToThreshold',
                dimensions={'InstanceId': outputs['instance_id']},
                metric_name='CPUCreditBalance',
                namespace='AWS/EC2',
                alarm_description=f'Instance {outputs["instance_id"]} ({outputs["res_name"]}) '
                'is running low on CPU credits',
                tags=cpu_credit_balance_tags,
                opts=pulumi.ResourceOptions(
                    parent=self, depends_on=[resource, monitoring_group.resources['sns_topic']]
                ),
                **cpu_credit_balance_opts,
            )
            if cpu_credit_balance_enabled
            else None
        )

        # Alert if we see overall elevated CPU consumption
        cpu_utilization_name = 'cpu_utilization'
        cpu_utilization_opts = CLOUDWATCH_METRIC_ALARM_DEFAULTS.copy()
        cpu_utilization_opts.update({'period': 300, 'threshold': 80, **self.overrides.get(cpu_utilization_name, {})})
        cpu_utilization_enabled = cpu_utilization_opts.pop('enabled')
        cpu_utilization_tags = {'tb_pulumi_alarm_name': cpu_utilization_name}
        cpu_utilization_tags.update(self.tags)
        cpu_utilization = pulumi.Output.all(res_name=resource.tags['Name'], instance_id=resource.id).apply(
            lambda outputs: aws.cloudwatch.MetricAlarm(
                f'{self.name}-cpuutilization',
                name=f'{outputs["res_name"]}-cpuutilization',
                alarm_actions=[monitoring_group.resources['sns_topic'].arn],
                comparison_operator='GreaterThanOrEqualToThreshold',
                dimensions={'InstanceId': outputs['instance_id']},
                metric_name='CPUUtilization',
                namespace='AWS/EC2',
                alarm_description=f'CPU utilization on instance {outputs["instance_id"]} ({outputs["res_name"]}) '
                f'exceeds {cpu_utilization_opts["threshold"]}%',
                tags=cpu_utilization_tags,
                opts=pulumi.ResourceOptions(
                    parent=self, depends_on=[resource, monitoring_group.resources['sns_topic']]
                ),
                **cpu_utilization_opts,
            )
            if cpu_utilization_enabled
            else None
        )

        # Alert if the EBS volume status fails
        ebs_status_failed_name = 'ebs_status_failed'
        ebs_status_failed_opts = CLOUDWATCH_METRIC_ALARM_DEFAULTS.copy()
        ebs_status_failed_opts.update({'period': 300, 'threshold': 1, **self.overrides.get(ebs_status_failed_name, {})})
        ebs_status_failed_enabled = ebs_status_failed_opts.pop('enabled')
        ebs_status_failed_tags = {'tb_pulumi_alarm_name': ebs_status_failed_name}
        ebs_status_failed_tags.update(self.tags)
        ebs_status_failed = pulumi.Output.all(res_name=resource.tags['Name'], instance_id=resource.id).apply(
            lambda outputs: aws.cloudwatch.MetricAlarm(
                f'{self.name}-ebsstatus',
                name=f'{outputs["res_name"]}-ebsstatus',
                alarm_actions=[monitoring_group.resources['sns_topic'].arn],
                comparison_operator='GreaterThanOrEqualToThreshold',
                dimensions={'InstanceId': outputs['instance_id']},
                metric_name='StatusCheckFailed_AttachedEBS',
                namespace='AWS/EC2',
                alarm_description=f'The EBS volume status check is failing on instance {outputs["instance_id"]} '
                f'({outputs["res_name"]})',
                tags=ebs_status_failed_tags,
                opts=pulumi.ResourceOptions(
                    parent=self, depends_on=[resource, monitoring_group.resources['sns_topic']]
                ),
                **ebs_status_failed_opts,
            )
            if ebs_status_failed_enabled
            else None
        )

        # Alert if the instance check fails
        instance_status_failed_name = 'instance_status_failed'
        instance_status_failed_opts = CLOUDWATCH_METRIC_ALARM_DEFAULTS.copy()
        instance_status_failed_opts.update(
            {'period': 300, 'threshold': 1, **self.overrides.get(instance_status_failed_name, {})}
        )
        instance_status_failed_enabled = instance_status_failed_opts.pop('enabled')
        instance_status_failed_tags = {'tb_pulumi_alarm_name': instance_status_failed_name}
        instance_status_failed_tags.update(self.tags)
        instance_status_failed = pulumi.Output.all(res_name=resource.tags['Name'], instance_id=resource.id).apply(
            lambda outputs: aws.cloudwatch.MetricAlarm(
                f'{self.name}-instancestatus',
                name=f'{outputs["res_name"]}-instancestatus',
                alarm_actions=[monitoring_group.resources['sns_topic'].arn],
                comparison_operator='GreaterThanOrEqualToThreshold',
                dimensions={'InstanceId': outputs['instance_id']},
                metric_name='StatusCheckFailed_Instance',
                namespace='AWS/EC2',
                alarm_description=f'The instance status check is failing on instance {outputs["instance_id"]} '
                f'({outputs["res_name"]})',
                tags=instance_status_failed_tags,
                opts=pulumi.ResourceOptions(
                    parent=self, depends_on=[resource, monitoring_group.resources['sns_topic']]
                ),
                **instance_status_failed_opts,
            )
            if instance_status_failed_enabled
            else None
        )

        # Alert if the system status fails
        system_status_failed_name = 'system_status_failed'
        system_status_failed_opts = CLOUDWATCH_METRIC_ALARM_DEFAULTS.copy()
        system_status_failed_opts.update(
            {'period': 300, 'threshold': 1, **self.overrides.get(system_status_failed_name, {})}
        )
        system_status_failed_enabled = system_status_failed_opts.pop('enabled')
        system_status_failed_tags = {'tb_pulumi_alarm_name': system_status_failed_name}
        system_status_failed_tags.update(self.tags)
        system_status_failed = pulumi.Output.all(res_name=resource.tags['Name'], instance_id=resource.id).apply(
            lambda outputs: aws.cloudwatch.MetricAlarm(
                f'{self.name}-systemstatus',
                name=f'{outputs["res_name"]}-systemstatus',
                alarm_actions=[monitoring_group.resources['sns_topic'].arn],
                comparison_operator='GreaterThanOrEqualToThreshold',
                dimensions={'InstanceId': outputs['instance_id']},
                metric_name='StatusCheckFailed_System',
                namespace='AWS/EC2',
                alarm_description=f'The system status check is failing on instance {outputs["instance_id"]} '
                f'({outputs["res_name"]})',
                tags=system_status_failed_tags,
                opts=pulumi.ResourceOptions(
                    parent=self, depends_on=[resource, monitoring_group.resources['sns_topic']]
                ),
                **system_status_failed_opts,
            )
            if system_status_failed_enabled
            else None
        )

        self.finish(
            outputs={},
            resources={
                cpu_credit_balance_name: cpu_credit_balance,
                cpu_utilization_name: cpu_utilization,
                ebs_status_failed_name: ebs_status_failed,
                instance_status_failed_name: instance_status_failed,
                system_status_failed_name: system_status_failed,
            },
        )


class EcsServiceAlarmGroup(tb_pulumi.monitoring.AlarmGroup):
    """**Pulumi Type:** ``tb:cloudwatch:EcsServiceAlarmGroup``

    A set of alarms for ECS services. Contains the following configurable alarms:

        - ``cpu_utilization``: Alarms on the overall CPU usage of the entire service, all tasks combined. Threshold is a
          percentage.
        - ``memory_utilization``: Alarms on the overall memory usage of the entire service, all tasks combined.
          Threshold is a percentage.

    Further detail on these metrics and more can be found on `Amazon's documentation
    <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/available-metrics.html>_`.

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

    :param kwargs: Any other keyword arguments which will be passed as inputs to the
        :py:class:`tb_pulumi.monitoring.AlarmGroup` superconstructor.

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
        cpu_utilization_name = 'cpu_utilization'
        cpu_utilization_opts = CLOUDWATCH_METRIC_ALARM_DEFAULTS.copy()
        cpu_utilization_opts.update({'period': 300, 'threshold': 80, **self.overrides.get(cpu_utilization_name, {})})
        cpu_utilization_enabled = cpu_utilization_opts['enabled']
        del [cpu_utilization_opts['enabled']]
        cpu_utilization_tags = {'tb_pulumi_alarm_name': cpu_utilization_name}
        cpu_utilization_tags.update(self.tags)
        cpu_utilization = pulumi.Output.all(res_name=resource.name, cluster_arn=resource.cluster).apply(
            lambda outputs: aws.cloudwatch.MetricAlarm(
                f'{self.name}-cpu',
                name=f'{outputs["res_name"]}-cpu',
                alarm_actions=[monitoring_group.resources['sns_topic'].arn],
                comparison_operator='GreaterThanOrEqualToThreshold',
                # There is no direct way to get the Cluster name from a Service, but we can get the ARN, which has the
                # name as the final portion after the last slash.
                dimensions={'ClusterName': outputs['cluster_arn'].split('/')[-1], 'ServiceName': outputs['res_name']},
                metric_name='CPUUtilization',
                namespace='AWS/ECS',
                alarm_description=f'CPU utilization on the {outputs["res_name"]} cluster exceeds '
                f'{cpu_utilization_opts["threshold"]}%',
                tags=cpu_utilization_tags,
                opts=pulumi.ResourceOptions(
                    parent=self, depends_on=[resource, monitoring_group.resources['sns_topic']]
                ),
                **cpu_utilization_opts,
            )
            if cpu_utilization_enabled
            else None
        )

        # Alert if we see overall elevated memory consumption
        memory_utilization_name = 'memory_utilization'
        memory_utilization_opts = CLOUDWATCH_METRIC_ALARM_DEFAULTS.copy()
        memory_utilization_opts.update(
            {'period': 300, 'threshold': 80, **self.overrides.get(memory_utilization_name, {})}
        )
        memory_utilization_enabled = memory_utilization_opts['enabled']
        del memory_utilization_opts['enabled']
        memory_utilization_tags = {'tb_pulumi_alarm_name': memory_utilization_name}
        memory_utilization_tags.update(self.tags)
        memory_utilization = pulumi.Output.all(res_name=resource.name, cluster_arn=resource.cluster).apply(
            lambda outputs: aws.cloudwatch.MetricAlarm(
                f'{self.name}-memory',
                name=f'{outputs["res_name"]}-memory',
                alarm_actions=[monitoring_group.resources['sns_topic'].arn],
                comparison_operator='GreaterThanOrEqualToThreshold',
                # There is no direct way to get the Cluster name from a Service, but we can get the ARN, which has the
                # name as the final portion after the last slash.
                dimensions={'ClusterName': outputs['cluster_arn'].split('/')[-1], 'ServiceName': outputs['res_name']},
                metric_name='MemoryUtilization',
                namespace='AWS/ECS',
                alarm_description=f'Memory utilization on the {outputs["res_name"]} cluster exceeds '
                f'{memory_utilization_opts["threshold"]}%',
                tags=memory_utilization_tags,
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
            resources={cpu_utilization_name: cpu_utilization, memory_utilization_name: memory_utilization},
        )
