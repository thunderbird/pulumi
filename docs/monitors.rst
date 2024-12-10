Monitoring Resources
====================
When you use a ``ThunderbirdPulumiProject`` and add ``ThunderbirdComponentResource`` s to it, the project tracks the
resources in an internal mapping correlating the name of the module to a collection of its resources. These resources
can have complex structures with nested lists, dicts, and ``ThunderbirdComponentResource`` s. The project's
:py:meth:`tb_pulumi.ThunderbirdPulumiProject.flatten` function returns these as a flat list of unlabeled Pulumi
``Resource`` s.

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
monitors status codes and response times, among other things.


CloudWatch Monitoring
---------------------

To create monitors for AWS resources, you may want to use AWS's metrics and alerting platform, CloudWatch. You can get
automatic monitoring with sensible defaults for all supported resources in your stack by setting up a
:py:class:`tb_pulumi.cloudwatch.CloudWatchMonitoringGroup`. Assume your project is set up like so:

.. code-block:: python
    :linenos:

    import tb_pulumi
    import tb_pulumi.network

    project = tb_pulumi.ThunderbirdPulumiProject()
    resources = project.config.get('resources')

    # Define various resources, adding them to the project...
    vpc_opts = resources['tb:network:MultiCidrVpc']['vpc']
    vpc = tb_pulumi.network.MultiCidrVpc('my-vpc', project, **vpc_opts)

    # ... etc ...

...you can add monitoring like this:

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
alerting for a resource, it will, using default values.
If you want to tweak the alarm's configuration, pass the desired values in through the config object. This should look
something like this:

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