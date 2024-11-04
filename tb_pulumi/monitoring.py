"""Infrastructural patterns related to AWS CloudWatch."""

import pulumi
import tb_pulumi

from functools import cached_property


class MonitoringGroup(tb_pulumi.ThunderbirdComponentResource):
    def __init__(
        self,
        pulumi_type: str,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        config: dict = {},
        opts: pulumi.ResourceOptions = None,
    ):
        super().__init__(pulumi_type=pulumi_type, name=name, project=project, opts=opts)
        self.config = config


class AlertGroup(tb_pulumi.ThunderbirdComponentResource):
    def __init__(
        self,
        pulumi_type: str,
        name: str,
        monitoring_group: MonitoringGroup,
        project: tb_pulumi.ThunderbirdPulumiProject,
        resource: pulumi.Resource,
        opts: pulumi.ResourceOptions = None,
    ):
        super().__init__(pulumi_type=pulumi_type, name=name, project=project, opts=opts)
        self.monitoring_group = monitoring_group
        self.resource = resource

    @cached_property
    def overrides(self):
        if self.resource._name in self.monitoring_group.config['alarms'].keys():
            return self.monitoring_group.config['alarms'][self.resource._name]
