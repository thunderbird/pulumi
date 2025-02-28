.. _monitoring_resources:

Monitoring Resources
====================

When monitoring an environment with tb_pulumi, we want to make sure alarms get set up against critical metrics for all
resources being managed in a project. The monitoring tools in this module are designed to track your infrastructure as
you build it and set up monitors for everything automatically. The alarms can then be tweaked or disabled entirely as
needed.

When you add ``ThunderbirdComponentResource`` s to a ``ThunderbirdPulumiProject``, the project tracks the resources in
an internal mapping correlating the name of the component resource to the collection of resources it contains. These
resources can have complex structures with nested lists, dicts, and ``ThunderbirdComponentResource`` s. The project's
:py:meth:`tb_pulumi.ThunderbirdPulumiProject.flatten` function returns these as a flat list of unlabeled Pulumi
``Resource`` s and ``Output`` s.

However, it is the nature of Pulumi Outputs that we do not know what type they will become when they are resolved. This
presents a hurdle for the auto-detection of resources to monitor, which is resolved through implementations of the
:py:class:`tb_pulumi.monitoring.MonitoringGroup` class. This class works by finding all the ``Output`` s in the
``flatten`` ed resources, then applying them. Once applied, the resolved outputs and previously known resources are
iterated to find supported resources of known types. The outputs are then passed into a function called ``monitor``.
When you implement the ``MonitoringGroup`` class, the alarms you build must be defined in an implementation of
``monitor``, not in ``__init__`` as in typical Pulumi patterns.

In addition to providing this post-apply access to all monitorable resources, the ``MonitoringGroup`` also sets up a
configuration of overrides (allowing you to tweak or disable any alarm) and provides a method of notification for
tripped alarms.

A ``MonitoringGroup`` 's alarms are organized and made configurable through a second class, the
:py:class:`tb_pulumi.monitoring.AlarmGroup`. This represents an overridable set of alarms for a
single resource (which may produce any number of metrics which we want to monitor). ``MonitoringGroup`` s must map
resource types to ``AlarmGroup`` types that handle those resources in their ``monitor`` functions.

As an example, take a look at :py:class:`tb_pulumi.cloudwatch.CloudWatchMonitoringGroup`, a ``MonitoringGroup``
implementation that uses AWS CloudWatch to alarm on metrics produced by AWS resources. It creates an
:py:class:`tb_pulumi.cloudwatch.LoadBalancerAlarmGroup` when it encounters a resource of type
``aws.lb.load_balancer.LoadBalancer``. That alarm group monitors status codes and response times, among other things.


CloudWatch Monitoring
---------------------

To create monitors for AWS resources, you may want to use AWS's metrics and alerting platform, CloudWatch. You can get
automatic monitoring with sensible defaults for all supported resources in your stack by setting up a
:py:class:`tb_pulumi.cloudwatch.CloudWatchMonitoringGroup`. Assuming your project is set up like in the
:ref:`quickstart` section, you can add monitoring like this:

.. code-block:: python
    :linenos:

    monitoring_opts = resources['tb:cloudwatch:CloudWatchMonitoringGroup']
    monitoring = tb_pulumi.cloudwatch.CloudWatchMonitoringGroup(
        name='my-monitoring',
        project=project,
        notify_emails=['your_alerting_email_here@host.tld'],
        config=monitoring_opts,
    )

The ``CloudWatchMonitoringGroup`` will look at every resource in your ``project`` . If it is capable of setting up
alerting for a resource, it will, using default values. If you want to tweak the alarm's configuration, pass the desired
values in through the config object. This should look something like this:

.. code-block:: yaml
    :linenos:

    tb:cloudwatch:CloudWatchMonitoringGroup:
        alarms:
            resource-name:
                alarm-name:
                    options: values


The ``options: values`` settings can contain any valid inputs to the ``aws.cloudwatch.MetricAlarm`` constructor
as `defined here <https://www.pulumi.com/registry/packages/aws/api-docs/cloudwatch/metricalarm/#inputs>`_. It also
supports a special ``enabled`` option, which can be set to ``False`` to prevent the creation of the alarm.

The ``resource-name`` is the name of the resource to which the alarm applies, as it is known to Pulumi. To see a list of
these values within your stack, you can set up your Pulumi environment and run ``pulumi stack``. You'll see output like
this (which is heavily truncated):
::

    Current stack is mystack:
        Managed by mymachine
        Last updated: 9 seconds ago (2024-12-10 09:31:13.157002687 -0700 MST)
        Pulumi version used: v3.142.0
    Current stack resources (137):
        TYPE                                                          NAME
        pulumi:pulumi:Stack                                           myproject-mystack
            ...
        ├─ tb:fargate:FargateClusterWithLogging                       myproject-mystack-fargate
        │  ├─ aws:kms/key:Key                                         myproject-mystack-fargate-logging
        │  ├─ aws:iam/policy:Policy                                   myproject-mystack-fargate-policy-exec
        │  ├─ tb:fargate:FargateServiceAlb                            myproject-mystack-fargate-fargateservicealb
        │  │  ├─ aws:alb/targetGroup:TargetGroup                      myproject-mystack-fargate-fargateservicealb-targetgroup-myapp
        │  │  ├─ aws:lb/loadBalancer:LoadBalancer                     myproject-mystack-fargate-fargateservicealb-alb-myapp
        │  │  └─ aws:lb/listener:Listener                             myproject-mystack-fargate-fargateservicealb-listener-myapp
        │  ├─ aws:cloudwatch/logGroup:LogGroup                        myproject-mystack-fargate-fargate-logs
        │  ├─ aws:iam/policy:Policy                                   myproject-mystack-fargate-policy-logs
        │  ├─ aws:ecs/cluster:Cluster                                 myproject-mystack-fargate-cluster
        │  ├─ aws:iam/role:Role                                       myproject-mystack-fargate-taskrole
        │  ├─ aws:ecs/taskDefinition:TaskDefinition                   myproject-mystack-fargate-taskdef
        │  └─ aws:ecs/service:Service                                 myproject-mystack-fargate-service
            ...

If you wanted to change the threshold for alerting on 5xx errors in the target group, you would use
``myproject-mystack-fargate-fargateservicealb-targetgroup-myapp`` as the ``resource-name`` in the config.

The ``alarm-name`` key should be the name of an alarm that is supported by the relevant alarm group. For example,
:py:class:`tb_pulumi.cloudwatch.AlbAlarmGroup` describes the ``target_5xx`` and ``alb_5xx`` alarms. To change a
config for one alarm and disable another, you could write the following config:

.. code-block:: yaml
    :linenos:

    tb:cloudwatch:CloudWatchMonitoringGroup:
        alarms:
            myproject-mystack-fargate-fargateservicealb-targetgroup-myapp:
                target_5xx:
                    threshold: 123
                    evaluation_periods: 3
                alb_5xx:
                    enabled: False

Both of these pieces of data are available as tags on the alarms themselves. If you discover an alarm which needs to be
tweaked, note the `tb_pulumi_resource_name` and `tb_pulumi_alarm_name` tags.