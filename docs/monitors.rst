.. _monitoring_resources:

Monitoring Resources
====================

tb_pulumi offers a tool for setting up monitoring for your entire stack at once. This comes downstream from some other
internals described better in :ref:`full_stack_patterns`. The short version of this is that:

- A :py:class:`tb_pulumi.ThunderbirdPulumiProject` tracks resources and collections of resources in an arbitrary nested
  structure.
- A :py:class:`tb_pulumi.ProjectResourceGroup` waits for a full application of the Pulumi stack before executing code
  with full context of every resource in the stack.

And now, we add that...

- A :py:class:`tb_pulumi.monitoring.MonitoringGroup` is a ProjectResourceGroup that filters resources based on known
  ability to monitor those resources. It is an abstract class which must be implemented by a class which can create
  monitors in a certain platform.
- A :py:class:`tb_pulumi.cloudwatch.CloudWatchMonitoringGroup` is a MonitoringGroup that builds monitors on the AWS
  CloudWatch platform.
- A :py:class:`tb_pulumi.monitoring.AlarmGroup` is a ThunderbirdComponentResource that creates alarms for a specific
  type of resource. This is an abstract class which is implemented in more specific alarm groups.
- More specific alarm groups, such as a :py:class:`tb_pulumi.cloudwatch.AlbAlarmGroup`, which creates CloudWatch alarms
  for application load balancers.

The overall idea is that the monitoring groups inspect the post-applied Pulumi state looking for any monitorable
resources. It creates the appropriate alarm groups for each resource it understands. If you change your infrastructure
to, as an example, create a new ALB, the monitoring group will automatically create new alarms for it. Likewise, if you
delete a monitored resource, its monitors will also get deleted. This requires no extra effort from the developer
beyond defining the monitoring group.


Set up a CloudWatchMonitoringGroup
----------------------------------

Start with a basic YAML config:

.. code-block:: yaml

  tb:cloudwatch:CloudWatchMonitoringGroup:
    monitoring:
      config:
        alarms: {}
      notify_emails:
        - your.email.here@domain.smth

And then define one in code:

.. code-block:: python

  monitoring_opts = resources.get('tb:cloudwatch:CloudWatchMonitoringGroup')
  monitoring = tb_pulumi.cloudwatch.CloudWatchMonitoringGroup(
      name=f'{project.name_prefix}-monitoring',
      project=project,
      **monitoring_opts,
  )

This will build monitors for everything the module is capable of monitoring.


Override Default Alarm Settings
-------------------------------

The :py:class:`tb_pulumi.cloudwatch.CloudWatchMonitoringGroup` class inherits from the base
:py:class:`tb_pulumi.monitoring.MonitoringGroup` class. That base class offers us a way of overriding the default options for
monitors. That is its ``config`` parameter.

This is a specially formatted dict of options. Here's a reasonable skeleton to begin with:

.. code-block:: yaml

    alarms:
      resource-name:
        alarm-name:
          enabled: True
          # ... other options here ...

The ``resource-name`` is the name of your resource as it is known to Pulumi. You can run the ``pulumi stack`` command to
get a list of these names. Here is some heavily modified sample output to refer to. The value you want is in the
``NAME`` column.

.. code-block::

    # pulumi stack
    Current stack is foobar:
        Owner: your-org
        Last updated: date/time
        Pulumi version used: v3.187.0
    Current stack resources (###):
        TYPE                                                  NAME
        pulumi:pulumi:Stack                                   project-stack
        ├─ tb:network:MultiCidrVpc                            project-stack-vpc
        │  ├─ aws:ec2/vpc:Vpc                                 project-stack-vpc
        │  ├─ tb:network:SecurityGroupWithRules               project-stack-vpc-endpoint-sg
        │  │  ├─ aws:ec2/securityGroup:SecurityGroup          project-stack-vpc-endpoint-sg-sg
        │  │  ├─ aws:ec2/securityGroupRule:SecurityGroupRule  project-stack-vpc-endpoint-sg-ingress-0
        │  │  └─ aws:ec2/securityGroupRule:SecurityGroupRule  project-stack-vpc-endpoint-sg-egress-0
        │  ├─ aws:ec2/subnet:Subnet                           project-stack-vpc-subnet-1
        │  ├─ aws:ec2/internetGateway:InternetGateway         project-stack-vpc-ig
        │  ├─ aws:ec2/subnet:Subnet                           project-stack-vpc-subnet-0
        ...

The ``alarm-name`` is defined by the AlarmGroup responding to the resource. For example, the
:py:class:`tb_pulumi.cloudwatch.Ec2InstanceAlarmGroup` docs list several, such as ``cpu_utilization``.

All alarms support the ``enabled`` option. This is implied to be ``True``, but can be set to ``False`` if you do not
wish to build that alarm. You can also supply any other options for an ``aws.cloudwatch.MetricAlarm`` here, and those
will override the defaults. For example, you could change the threshold and number of evaluation periods for an alarm:

.. code-block:: yaml

    alarms:
      my-instance:
        cpu_utilization:
            threshold: 80
            evaluation_periods: 3
