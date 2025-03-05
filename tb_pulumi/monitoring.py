"""Common code related to monitoring patterns."""

import pulumi
import tb_pulumi

from abc import abstractclassmethod
from functools import cached_property


class MonitoringGroup(tb_pulumi.ThunderbirdComponentResource):
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
        pulumi_type: str,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        type_map: dict,
        config: dict = {},
        opts: pulumi.ResourceOptions = None,
        tags: dict = {}
    ):
        super().__init__(pulumi_type=pulumi_type, name=name, project=project, opts=opts, tags=tags)
        self.config: dict = config
        self.type_map: dict = type_map

        # Start with a list of all resources; sort them out into known and unknown things
        _all_contents = self.project.flatten()

        #: All Pulumi Outputs in the project
        self.all_outputs = [res for res in _all_contents if isinstance(res, pulumi.Output)]

        #: All items in the project which are already-resolved pulumi resources
        self.all_resources = [res for res in _all_contents if not isinstance(res, pulumi.Output)]

        #: All resources in the project which have an entry in the type_map; this may contain Outputs, which will be
        #: resolved by the time :py:meth:`tb_pulumi.monitoring.MonitoringGroup.monitor` is invoked.
        self.supported_resources = []

        def __parse_resource_item(
            item: tb_pulumi.Flattenable,
        ):
            """Not all items in a project's ``resources`` dict are actually Pulumi Resources. Sometimes we build
            resources downstream of a Pulumi Output, which makes those resources (as they are known to the project)
            actually Outputs and not recognizable resource types. We can only detect what kind of thing those Outputs
            really are by asking from within code called inside an output's `apply` function. This necessitates an
            unpacking process on this end of things to recursively resolve those Outputs into Resources that we can
            build alarms around.

            This function processes and recursively "unpacks" an ``item`` , which could be any of the following things:

                - A Pulumi Resource that we may or may not be able to monitor.
                - A ``tb_pulumi.ThunderbirdComponentResource`` that potentially contains other Resources or Outputs
                    in a potentially nested structure.
                - A Pulumi Output that could represent either of the above things, or could be a collection of a
                    combination of those things.
                - A list of any of the above items.
                - A dict where the values could be any of the above items.

            Given one of these things, this function determines what kind of item it's dealing with and responds
            appropriately to unpack and resolve the item. The function doesn't return any value, but instead manipulates
            the internal resource listing directly, resulting in an ``all_resources`` list that includes the unpacked
            and resolved Outputs.

            It is important to note that this listing is **eventually resolved**. Because this function deals in Pulumi
            Outputs, the ``all_resources`` list **will still contain Outputs, even after running this function!**
            However, ``all_resources`` will contain valid, resolved values when accessed from within a function that
            relies upon the application of every item in ``all_outputs``, such as the ``monitor`` function. This is why
            we build all monitoring resources inside of the ``monitor`` function.
            """

            if type(item) is list:
                for i in item:
                    __parse_resource_item(i)
            elif type(item) is dict:
                for i in item.values():
                    __parse_resource_item(i)
            elif isinstance(item, tb_pulumi.ThunderbirdComponentResource):
                __parse_resource_item(item.resources)
            elif isinstance(item, pulumi.Resource):
                self.all_resources.append(item)
            elif isinstance(item, pulumi.Output):
                item.apply(__parse_resource_item)

        # Expand and resolve all outputs using the above parsing function
        for output in self.all_outputs:
            __parse_resource_item(output)

        # When all outputs are applied, trigger the `on_apply` event.
        pulumi.Output.all(*self.all_outputs).apply(lambda outputs: self.__on_apply(outputs))

    def __on_apply(self, outputs):
        """This function gets called only after all outputs in the project have been resolved into values. This
        function should be considered to be a post-apply stage of the ``__init__`` function.

        :param outputs: A list of resolved outputs discovered in the project.
        :type outputs: list
        """

        # From this side of an apply, we can see the resource types and look for ones we know about
        self.supported_resources = [res for res in self.all_resources if type(res) in self.type_map.keys()]

        # Call downstream monitoring setups
        self.monitor(outputs)

    @abstractclassmethod
    def monitor(self, outputs):
        """This function gets called after all of a project's outputs have been recursively unpacked and resolved, and
        after this class's post-apply construction has completed.

        This is an abstract method which must be implemented by an inheriting class. That function should construct all
        monitors for the supported resources in this project within this function. This function is essentially a
        hand-off to an implementing class, an indicator that the project has been successfully parsed, and monitors can
        now be built.

        Because this works as an extension of ``__init__``, the ``finish`` call for downstream monitoring groups should
        be made from within this function instead of the constructor.

        :param outputs: A list of resolved outputs discovered in the project.
        :type outputs: list
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
