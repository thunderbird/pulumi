"""Common code related to monitoring patterns."""

import pulumi
import tb_pulumi

from abc import abstractclassmethod
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

    :param type_map: A dict where the keys are ``pulumi.Resource`` derivatives representing types of resources this
        monitoring group recognizes and the values are ``tb_pulumi.monitoring.AlarmGroup`` derivatives which actually
        declare those monitors.
    :type type_map: dict[type, type]

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
        type_map: dict,
        config: dict = {},
        opts: pulumi.ResourceOptions = None,
    ):
        super().__init__(pulumi_type=pulumi_type, name=name, project=project, opts=opts)
        self.config: dict = config
        self.type_map: dict = type_map

        # Start with a list of all resources; sort them out into known and unknown things
        _all_contents = self.project.flatten()
        self.all_outputs = [res for res in _all_contents if isinstance(res, pulumi.Output)]
        self.all_resources = [res for res in _all_contents if not isinstance(res, pulumi.Output)]

        def __parse_resource_item(
            item: list | dict | pulumi.Output | pulumi.Resource | tb_pulumi.ThunderbirdComponentResource,
        ):
            """Not all items in a project's `resources` dict are actually Pulumi Resources. Sometimes we build resources
            downstream of a Pulumi Output, which makes those resources (as they are known to the project) actually
            Outputs and not recognizable resource types. We can only detect what kind of thing those Outputs are from
            within a function called from within an output's `apply` function. This necessitates an unpacking process on
            this end of things to recursively resolve those Outputs into Resources that we can build alarms around.

            This function processes and recursively "unpacks" an ``item`` , which could be any of the following things:

                - A Pulumi Resource that we may or may not be able to monitor.
                - A ``tb_pulumi.ThunderbirdComponentResource`` that potentially contains other Resources or Outputs
                    in a potentially nested structure.
                - A Pulumi Output that could represent either of the above things, or could be a collection of a
                    combination of those things.
                - A list of any of the above items.
                - A dict where the values could be any of the above items.

            Given a Pulumi resource or output, or a list or dict of such, this function determines what kind of item
            we're dealing with and responds appropriately to unpack and resolve the item. It doesn't return any value,
            but instead manipulates the interal resource listing directly, resulting in an ``all_resources`` list that
            includes the unpacked and resolved Outputs.

            It is important to note that this listing is **eventually resolved**. Because this function deals in Pulumi
            Outputs, the ``all_resources`` list **will still contain Outputs, even after running this function!**
            However, ``all_resources`` will contain valid, resolved values when accessed from within a function that
            relies upon the application of every item in ``all_outputs``.
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

        for output in self.all_outputs:
            __parse_resource_item(output)

        # When all outputs are applied, trigger the `on_apply` event.
        pulumi.Output.all(*self.all_outputs).apply(lambda outputs: self.on_apply(outputs))

    def on_apply(self, outputs):
        """This function gets called only after all outputs in the project have been resolved into values.

        :param outputs: A list of resolved outputs discovered in the project.
        :type outputs: list
        """

        self.supported_resources = [res for res in self.all_resources if type(res) in self.type_map.keys()]
        self.monitor(outputs)

    @abstractclassmethod
    def monitor(self, outputs):
        """This function gets called after all of a project's outputs have been recursively unpacked and resolved, and
        after this class's post-apply construction has completed.

        This is an abstract method which must be implemented by an inheriting class. That function should construct all
        monitors for the supported resources in this project.

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

        # Tag alarms with their resource names for easy reference when tweaking later
        self.tags.update({'tb_pulumi_resource_name': resource._name})

    @cached_property
    def overrides(self) -> dict:
        """If the user has configured any overrides for alarms related to this resource, this function returns them."""
        if self.resource._name in self.monitoring_group.config['alarms'].keys():
            return self.monitoring_group.config['alarms'][self.resource._name]
        else:
            return {}
