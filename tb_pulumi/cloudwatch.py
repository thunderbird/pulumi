"""Infrastructural patterns related to AWS CloudWatch."""

import pulumi
import pulumi_aws as aws
import tb_pulumi
import tb_pulumi.monitoring


class CloudWatchMonitoringGroup(tb_pulumi.monitoring.MonitoringGroup):
    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        opts: pulumi.ResourceOptions = None,
        config: dict = {},
    ):
        super().__init__(
            pulumi_type='tb:cloudwatch:CloudWatchMonitoringGroup', name=name, project=project, opts=opts, config=config
        )

        supported_types = {
            # aws.lb.load_balancer.LoadBalancer: AlbAlertGroup,
            aws.ecs.Service: FargateServiceAlertGroup
        }
        supported_resources = [
            resource for resource in self.project.flatten() if type(resource) in supported_types.keys()
        ]

        sns_topic = aws.sns.Topic(
            f'{name}-topic', name=f'{self.project.name_prefix}-alerting', opts=pulumi.ResourceOptions(parent=self)
        )

        alerts = {}
        for res in supported_resources:
            pulumi.info(f'Supported resource: {res}')
            alerts[res._name] = supported_types[type(res)](
                name=f'{res._name}',
                project=self.project,
                resource=res,
                monitoring_group=self,
                opts=pulumi.ResourceOptions(parent=self),
            )

        self.finish(outputs={'sns_topic_arn': sns_topic.arn}, resources={'sns_topic': sns_topic, 'alerts': alerts})


class AlbAlertGroup(tb_pulumi.monitoring.AlertGroup):
    def __init__(
        self,
        name: str,
        monitoring_group: tb_pulumi.monitoring.MonitoringGroup,
        project: tb_pulumi.ThunderbirdPulumiProject,
        resource: pulumi.Resource,
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        super().__init__(
            'tb:cloudwatch:AlbAlertGroup', name=name, project=project, resource=resource, opts=opts, **kwargs
        )

        fivexx_opts = {'evaluation_periods': 2, 'period': 300, 'statistic': 'Average', 'threshold': 10}
        fivexx_opts.update(self.overrides['fivexx'] if 'fivexx' in self.overrides else {})
        fivexx = aws.cloudwatch.MetricAlarm(
            f'{self.name}-5xx',
            name=f'{self.project.name_prefix}-5xx',
            comparison_operator='GreaterThanOrEqualToThreshold',
            metric_name='HTTPCode_ELB_5XX_Count',
            namespace='AWS/ApplicationELB',
            alarm_description=f'Elevated 5xx errors on ALB {resource.name}',
            opts=pulumi.ResourceOptions(parent=self, depends_on=[resource]),
            **fivexx_opts,
        )

        response_time_opts = {'evaluation_periods': 2, 'period': 300, 'statistic': 'Average', 'threshold': 1}
        response_time_opts.update(self.overrides['response_time'] if 'response_time' in self.overrides else {})
        response_time = aws.cloudwatch.MetricAlarm(
            f'{self.name}-responsetime',
            name=f'{self.project.name_prefix}-responsetime',
            comparison_operator='GreaterThanOrEqualToThreshold',
            metric_name='TargetResponseTime',
            namespace='AWS/ApplicationELB',
            alarm_description=f'Average response time is over {response_time_opts['threshold']} second(s) for {response_time_opts['period']} seconds',  # noqa: E501
            opts=pulumi.ResourceOptions(parent=self, depends_on=[resource]),
        )

        self.finish(outputs={}, resources={'five_x_x': fivexx, 'response_time': response_time})


class FargateServiceAlertGroup(tb_pulumi.monitoring.AlertGroup):
    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        resource: pulumi.Resource,
        monitoring_group: tb_pulumi.monitoring.MonitoringGroup,
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        super().__init__(
            'tb:cloudwatch:FargateClusterAlertGroup',
            name=name,
            project=project,
            resource=resource,
            monitoring_group=monitoring_group,
            opts=opts,
            **kwargs,
        )

        cpu_utilization_opts = {'evaluation_periods': 2, 'period': 300, 'statistic': 'Average', 'threshold': 80}
        cpu_utilization_opts.update(self.overrides['cpu_utilization'] if 'cpu_utilization' in self.overrides else {})
        cpu_utilization_desc = resource.name.apply(
            lambda resource_name: f'CPU utilization on the {resource_name} service exceeds {cpu_utilization_opts['threshold']}%'  # noqa: E501
        )
        cpu_utilization_alarm = aws.cloudwatch.MetricAlarm(
            f'{self.name}-cpu',
            name=f'{self.project.name_prefix}-cpu',
            comparison_operator='GreaterThanOrEqualToThreshold',
            metric_name='CPUUtilization',
            namespace='AWS/ECS',
            alarm_description=cpu_utilization_desc,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[resource]),
            **cpu_utilization_opts,
        )

        memory_utilization_opts = {'evaluation_periods': 2, 'period': 300, 'statistic': 'Average', 'threshold': 80}
        memory_utilization_opts.update(
            self.overrides['memory_utilization'] if 'memory_utilization' in self.overrides else {}
        )
        memory_utilization_desc = resource.name.apply(
            lambda resource_name: f'Memory utilization on the {resource_name} cluster exceeds {memory_utilization_opts['threshold']}%'  # noqa: E501
        )
        memory_utilization = aws.cloudwatch.MetricAlarm(
            f'{self.name}-memory',
            name=f'{self.project.name_prefix}-memory',
            comparison_operator='GreaterThanOrEqualToThreshold',
            metric_name='MemoryUtilization',
            namespace='AWS/ECS',
            alarm_description=memory_utilization_desc,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[resource]),
            **memory_utilization_opts,
        )

        self.finish(
            outputs={},
            resources={'cpu_utilization': cpu_utilization_alarm, 'memory_utilization': memory_utilization},
        )
