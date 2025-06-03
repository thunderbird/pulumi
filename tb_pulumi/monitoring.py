"""Common code related to monitoring patterns."""

import pulumi
import tb_pulumi

from abc import abstractclassmethod
from functools import cached_property


class MonitoringGroup(tb_pulumi.ProjectResourceGroup):
    """A broad-scope approach to aggregate resource monitoring. A ``MonitoringGroup`` is a very thin class that should
    be extended to provide specific monitoring solutions for the resources contained in the specified ``project``.

    :param pulumi_type: The "type" string (commonly referred to in docs as just ``t``) of the component as described
        by `Pulumi's type docs <https://www.pulumi.com/docs/concepts/resources/names/#types>`_.
    :type pulumi_type: str

    :param name: The name of the ``MonitoringGroup`` resource.
    :type name: str

    :param project: The ``ThunderbirdPulumiProject`` to build monitoring resources for.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param type_map: A dict where the keys are ``pulumi.Resource`` derivatives representing types of resources this
        monitoring group recognizes, and where the values are ``tb_pulumi.monitoring.AlarmGroup`` derivatives which
        actually declare those monitors. For example, an ``aws.cloudfront.Distribution`` key might map to a
        ``tb_pulumi.cloudwatch.CloudFrontDistributionAlarmGroup`` value.
    :type type_map: dict[type, type]

    :param config: A configuration dictionary. The specific format and content of this dictionary is defined in part by
        classes extending this class. However, the dictionary should be configured in the following broad way, with
        downstream monitoring groups defining the specifics of the monitor configs (shown here as YAML):

        .. code-block:: yaml
            :linenos:

            ---
            alarms:
                name-of-the-resource-being-monitored:
                    monitor_name:
                        enabled: False
                        # Downstream monitoring groups tell you what else goes right here

        This config defines override settings for alarms whose default configurations are insufficient for a specific
        use case. Since each resource can have multiple alarms associated with it, the ``"alarm"`` dict's keys should be
        the names of Pulumi resources being monitored. Their values should also be dictionaries, and those keys should
        be the names of the alarms as defined in the documentation for those alarm groups.

        All alarms should respond to a boolean ``"enabled"`` value such that the alarm will not be created if this is
        ``False``. Beyond that, configure each alarm as described in its alarm group documentation. Defaults to {}.
    :type config: dict, optional

    :param opts: Additional ``pulumi.ResourceOptions`` to apply to this resource. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param tags: Key/value pairs to merge with the default tags which get applied to all resources in this group.
        Defaults to {}.
    :type tags: dict, optional
    """

    def __init__(
        self,
        pulumi_type: str,  # We have to pass this through here because this class is meant to be further extended
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        type_map: dict,
        config: dict = {},
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
    ):
        # Internalize data before calling the superconstructor since that will ultimately result in our `ready` and
        # `monitor` functions being called before code flow continues below.
        self.config: dict = config
        self.type_map: dict = type_map

        #: All resources in the project which have an entry in the type_map; this may contain Outputs, which will be
        #: resolved by the time :py:meth:`tb_pulumi.monitoring.MonitoringGroup.monitor` is invoked.
        self.supported_resources = []
        super().__init__(pulumi_type=pulumi_type, name=name, project=project, opts=opts, tags=tags)

    def ready(self, outputs: list[pulumi.Resource]):
        """This function is called by the :py:class:`tb_pulumi.ProjectResourceGroup` after all outputs in the project
        have been resolved into values. Here, we examine those resources and determine which ones this library is
        capable of building alarms for. These become our ``supported_resources``, which are to be accessed by classes
        implementing this one.

        :param outputs: A list of resolved outputs discovered in the project. This is provided primarily for reference,
            but has limited value.
        :type outputs: list[pulumi.Resource]
        """

        # From this side of an apply, we can see the resource types and look for ones we know about
        self.supported_resources = [res for res in self.all_resources + outputs if type(res) in self.type_map.keys()]

        # Call downstream monitoring setups
        self.monitor()

    @abstractclassmethod
    def monitor(self):
        """This function is called by :py:meth:`tb_pulumi.monitoring.MonitoringGroup.ready` when the ``MonitoringGroup``
        has determined what resources are supported by this library. This class is downstream from a
        :py:class:`tb_pulumi.ThunderbirdComponentResource`, and is an extension of its
        :py:meth:`tb_pulumi.ThunderbirdComponentResource.__init__` function, the ``finish`` call for downstream
        monitoring groups should be made from within this function instead of the constructor.

        Because this works as an extension of ``__init__``, the ``finish`` call for downstream monitoring groups should
        be made from within this function instead of the constructor.
        """

        raise NotImplementedError()


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

    :param tags: Key/value pairs to merge with the default tags which get applied to all resources in this group.
        Defaults to {}.
    :type tags: dict, optional
    """

    def __init__(
        self,
        pulumi_type: str,
        name: str,
        monitoring_group: MonitoringGroup,
        project: tb_pulumi.ThunderbirdPulumiProject,
        resource: pulumi.Resource,
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
    ):
        super().__init__(pulumi_type=pulumi_type, name=name, project=project, opts=opts, tags=tags)
        self.monitoring_group = monitoring_group
        self.resource = resource

        # Tag alarms with their resource names for easy reference when tweaking later
        self.tags.update({'tb_pulumi_resource_name': resource._name})

    @cached_property
    def overrides(self) -> dict:
        """If the user has configured any overrides for alarms related to this resource, this function returns them."""
        if self.resource._name in self.monitoring_group.config['alarms'].keys():
            return self.monitoring_group.config['alarms'][self.resource._name]
        else:
            return {}
