"""Common code related to monitoring patterns."""

import pulumi
import tb_pulumi

from functools import cached_property


class MonitoringGroup(tb_pulumi.ThunderbirdComponentResource):
    """A broad-scope approach to aggregate resource monitoring. A ``MonitoringGroup`` is a very thin class that should
    be extended to provide specific monitoring solutions for the resources contained in the specified ``project``.

    :param pulumi_type: The "type" string (commonly referred to in docs as just ``t``) of the component as described
        by `Pulumi's docs <https://www.pulumi.com/docs/concepts/resources/names/#types>`_.
    :type pulumi_type: str

    :param name: The name of the ``MonitoringGroup`` resource.
    :type name: str

    :param project: The ``ThunderbirdPulumiProject`` to build monitoring resources for.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param config: A configuration dictionary. The specific format and content of this dictionary should be defined by
        classes extending this class. The dictionary should be configured in roughly the following way:
        ::

            {
                "alarms": {
                    "name-of-the-resource-being-monitored": {
                        "monitor_name": {
                            "enabled": False
                        }
                    }
                }
            }

        ``"alarms"`` should be a dictionary defining override settings for alarms. Its keys should be the names of
        Pulumi resources being monitored, and their values should also be dictionaries. The alarm group will define
        some alarms which can be tweaked. Refer to their documentation for details. All alarms should respond to a
        boolean ``"enabled"`` value such that the alarm will not be created if this is ``False``. Beyond that, configure
        each alarm as described in its alarm group documentation. Defaults to {}.
    :type config: dict, optional

    :param opts: Additional ``pulumi.ResourceOptions`` to apply to this resource. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional
    """

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


class AlarmGroup(tb_pulumi.ThunderbirdComponentResource):
    """A collection of alarms set up to monitor a particular single resource. For example, there are multiple metrics to
    alarm on pertaining to a load balancer. An ``AlarmGroup`` would collect all of those alarms under one object. This
    class should be considered a base class for building more sophisticated alarm groups.

    :param pulumi_type: The "type" string (commonly referred to in docs as just ``t``) of the component as described
        by `Pulumi's docs <https://www.pulumi.com/docs/concepts/resources/names/#types>`_.
    :type pulumi_type: str

    :param name: The name of the ``AlarmGroup`` resource.
    :type name: str

    :param monitoring_group: The ``MonitoringGroup`` that this ``AlarmGroup`` belongs to. This is how configuration
        overrides are delivered from the YAML config file to the individual alarm groups.
    :type monitoring_group: MonitoringGroup

    :param project: The ``ThunderbirdPulumiProject`` whose resources are being monitored.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param resource: The Pulumi ``Resource`` object this ``AlarmGroup`` is building alarms for.
    :type resource: pulumi.Resource

    :param opts: Additional ``pulumi.ResourceOptions`` to apply to this resource. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional
    """

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
    def overrides(self) -> dict:
        """If the user has configured any overrides for alarms related to this resource, this function returns them."""
        if self.resource._name in self.monitoring_group.config['alarms'].keys():
            return self.monitoring_group.config['alarms'][self.resource._name]
        else:
            return {}
