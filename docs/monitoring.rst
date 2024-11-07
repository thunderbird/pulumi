Monitoring Resources
====================

When you use a ``ThunderbirdPulumiProject`` and add ``ThunderbirdComponentResource``s to it, the project tracks the
resources in an internal mapping correlating the name of the module to a collection of its resources. These resources
can have complex structures with nested lists, dicts, and ``ThunderbirdComponentResource``s. The project's
:py:meth:`tb_pulumi.ThunderbirdPulumiProject.flatten` function returns these as a flat list of unlabeled Pulumi
``Resource``s.

The ``monitoring`` module contains two base classes intended to provide common interfaces to building monitoring
patterns. The first is a ``MonitoringGroup``. This is little more than a ``ThunderbirdComponentResource`` that contains
a config dictionary. The purpose is to contain the resources involved in a monitoring solution. That is, alarms and a
notification setup.

You should extend this class such that the resources returned by ``flatten`` are iterated over. If your module
understands that a resource it comes across can be monitored, the class should create alarms via an extension of the
second class, ``AlarmGroup``. This base class should be extended such that it creates alarms for a specific single
resource. For example, a single load balancer might have many different metrics being monitored.

As an example, take a look at :py:class:`tb_pulumi.cloudwatch.CloudWatchMonitoringGroup`, a ``MonitoringGroup``
extension that uses AWS CloudWatch to alarm on metrics produced by AWS resources. It creates an
:py:class:`tb_pulumi.cloudwatch.AlbAlarmGroup` when it encounters an application load balancer. That alarm group
monitors status codes and response times.