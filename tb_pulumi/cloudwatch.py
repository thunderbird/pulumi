"""Infrastructural patterns related to AWS CloudWatch."""

import pulumi
import pulumi_aws as aws
import tb_pulumi


class CloudWatchMonitoring(tb_pulumi.ThunderbirdComponentResource):
    def __init__(
        self, name: str, project: tb_pulumi.ThunderbirdPulumiProject, opts: pulumi.ResourceOptions = None, **kwargs
    ):
        super().__init__('tb:cloudwatch:CloudWatchMonitoring', name=name, project=project, opts=opts, **kwargs)

        supported_types = {aws.lb.load_balancer.LoadBalancer: ApplicationLoadBalancerAlerts}
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
                opts=pulumi.ResourceOptions(parent=self),
            )

        self.finish(outputs={'sns_topic_arn': sns_topic.arn}, resources={'sns_topic': sns_topic, 'alerts': alerts})


class ApplicationLoadBalancerAlerts(tb_pulumi.ThunderbirdComponentResource):
    def __init__(
        self, name: str, project: tb_pulumi.ThunderbirdPulumiProject, opts: pulumi.ResourceOptions = None, **kwargs
    ):
        super().__init__('tb:cloudwatch:CloudWatchMonitoring', name=name, project=project, opts=opts, **kwargs)

        five_x_x = aws.cloudwatch.MetricAlarm(
            f'{self.name}-5xx',
            name=f'{self.project.name_prefix}-5xx',
            comparison_operator='GreaterThanOrEqualToThreshold',
            evaluation_periods=2,
            metric_name='HTTPCode_ELB_5XX_Count',
            namespace='AWS/ApplicationELB',
            period=300,
            statistic='Average',
            threshold=1,
            alarm_description='5xx errors on this ALB',
            opts=pulumi.ResourceOptions(parent=self)
        )

        self.finish(outputs={}, resources={'five_x_x': five_x_x})