.. _patterns_of_use:

Patterns of Use
===============

The patterns contained in this module support our use cases for services hosted by Thunderbird Pro Services. To
summarize a bit from the :ref:`getting_started` page:

- We extend the ``pulumi.ComponentResource`` class into a ``tb_pulumi.ThunderbirdComponentResource`` class, which
  exposes the resources contained within it to higher-order code.
- These are organized into ``tb_pulumi.ThunderbirdPulumiProject`` s, which connect YAML configuration files to Pulumi
  code files and provide programmatic access to all components within it.

This page explains these conventions in clearer detail and describes the common code patterns that follow from adhering
to them.


Patterns for Managing Projects
------------------------------

One primary goal of this project is to reduce most infrastructural changes to YAML file tweaks once the initial setup is
done, requiring no code inspection or debugging for most common changes. The
:py:class:`tb_pulumi.ThunderbirdPulumiProject` class brings those configs, information about the cloud environment, and
Pulumi project and stack data into a single context. That context is then made available to any
:py:class:`tb_pulumi.ThunderbirdComponentResource` created within that project.

Given that you have...

- created a Pulumi stack with a ``$STACK_NAME``,
- properly written a ``config.$STACK_NAME.yaml`` file alongside your tb_pulumi code, and
- configured your AWS client,

...the following code will produce a ThunderbirdPulumiProject with all context availablle for the currently selected
stack:

.. code-block:: python

  import tb_pulumi
  project = tb_pulumi.ThunderbirdPulumiProject()

For example, you can now get the ``resources`` mapping from your configuration like so:

.. code-block:: python

  resources = project.config.get('resources')

At this point, if you have not defined a ``resources`` section in your config file, ``resources`` will be ``None``. But
if you have a good config, it will be a dict where the top-level keys are Pulumi type strings.

You could, of course, do this as well:

.. code-block:: python

  resources = project.config['resources']

But in the case where the config file is not set up right, this results in a ``KeyError``. This is fine, and you should
raise an exception in this case anyway. We find the ``.get()`` method is more elegant.

Consider this approach instead:

.. code-block:: python

  resources = project.config.get('resources')
  if not resources:
      raise ValueError(f'tb_pulumi is not configured for stack {project.stack}.')

Also consider the case where you need access to a nested option. The 

.. code-block:: python

  # This prints a big stack trace ending in a KeyError
  child_config = resources['parent_config']['child_config']

  # If you want to emit a custom error
  try:
    child_config = resources['parent_config']['child_config']
  except KeyError as ex:
    pulumi.error('No child config')
    
    # You can either hard sys.exit
    import sys
    sys.exit(1)

    # Or re-raise the exception
    raise ex

  # But in this form, child_config gets None, allowing us to gracefully handle the failure
  # with little code and extra output.
  child_config = resources.get('parent_config', {}).get('child_config')
  if not child_config:
    raise ValueError('No child config')
  

Resource Patterns
-----------------


Define a resource with no dependencies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The simplest resources stand alone, depending on no other resources, only a valid configuration. Even simpler is when
you must create only one. Consider this YAML config and Python definition of a ``MultiCidrVpc``:

.. code-block:: yaml

  ---
  resources:
    tb:network:MultiCidrVpc:
      vpc:
        cidr_block: 10.0.0.0/16
        subnets:
          eu-central-1a:
            - 10.0.0.0/17
          eu-central-1b:
            - 10.0.128.0/17

.. code-block:: python

  vpc_opts = resources.get('tb:network:MultiCidrVpc', {}).get('vpc')
  vpc = tb_pulumi.network.MultiCidrVpc(
    name=f'{project.name_prefix}-vpc',
    project=project,
    **vpc_opts,
  )

This provides only the bare minimum of code-based information:

  - The ``name`` of the resource, making use of the project's ``name_prefix`` to create a unique identifier.
  - The project we have defined, so this resource and the other resources it contains can be traversed.

After that, it simply expands the ``vpc_opts`` (which has been ripped straight from the config file) into function
parameters. In this way, any changes you make to your YAML will be read into the VPC resource.


Access a resource from within a ThunderbirdComponentResource
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A ``ThunderbirdPulumiProject`` and a ``ThunderbirdComponentResource`` each have a ``resources`` member which is a
dict of all components defined within it. At both levels, these can be Pulumi Outputs, Resources, ComponentResources,
ThunderbirdComponentResources, or a collection of any of these things. Documentation for each
ThunderbirdComponentResource describes what resources it contains. In a project, the keys in this dict are named after
whatever names you provide for the ThunderbirdComponentResources. In a ThunderbirdComponentResource, they're named
according to what that resource is labeled in its :py:meth:`tb_pulumi.ThunderbirdPulumiProject.finish` call. All of the
various resources created by our classes are fully documented in the :ref:`modules` page.

One common need is to define a ``MultiCidrVpc`` and then feed one of the subnet IDs to an EC2 instance. If we have
defined the ``vpc`` resource as in the sample in the previous section, we can access the subnet IDs from the variable
itself. :py:class:`tb_pulumi.network.MultiCidrVpc` documentation shows that the ``aws.ec2.Subnet`` resources are
available through the ``subnets`` resource. Here are some things you can do with that:

.. code-block:: python

  # Get a list of all subnet resources
  subnets = vpc.resources.get('subnets')
  
  # Get a list of all subnet IDs
  subnet_ids = [subnet.id for subnet in vpc.resources.get('subnets')]

  # Get the first subnet ID
  subnet_id = vpc.resources.get('subnets')[0]

Remember that this value will be a ``pulumi.Output`` , not a real subnet ID, not until Pulumi has applied the resource.
For the most part, this is okay. You could pass that value into some other resource as an Output, and Pulumi would wait
for a real value before proceeding.

.. code-block:: python

  subnet_id = vpc.resources.get('subnets')[0]
  instance_opts = resources.get('tb:ec2:SshableInstance', {}).get('my-instance')
  if not instance_opts:
    raise ValueError('my-instance not configured')

  instance = tb_pulumi.ec2.SshableInstance(
    name='my-instance',
    project=project,
    subnet_id=subnet_id,
    **instance_opts,
    opts=pulumi.ResourceOptions(depends_on=[vpc]),
  )

Note that in this pattern, we only hardcode parameters whose values are generated elsewhere in the code. As many options
as possible are passed in directly from the YAML file.

Also note the addition of the ``opts`` parameter, which specifies that the instance is dependent on the VPC resources.
This helps Pulumi set up its dependency tree and prevent problems where you try to build resources that need access to
IDs that don't exist yet.

.. important::

  This also showcases an important concept. Pulumi's internal dependency tree is built around ``Resource`` objects. You
  are defining a ``Resource`` which depends on another ``Resource``. This relationship in Pulumi causes it to wait for
  the first ``Resource`` to be fully applied before trying to apply the dependent one.

  A Pulumi ``ComponentResource`` is a collection of ``Resource`` s, but it is actually an extension of the ``Resource``
  class. So Pulumi understands this as a type of resource upon which some other resource can be dependent.

  A ``ThunderbirdComponentResource`` is an extension of the ``ComponentResource`` class, meaning that **even our custom
  resource collection type can be used as a collective dependency.** In the above example, the entire ``MultiCidrVpc``
  and every resource it contains will be applied before the ``SshableInstance`` ever gets underway.

If you need to wait on that value so you can form it as text, you must write an ``apply`` lambda:

.. code-block:: python

  import json
  
  # ... project setup, etc ...

  subnet_id = vpc.resources.get('subnets')[0]
  json_text = subnet_id.apply(
      lambda subnet_id:
          json.dumps({'subnet_id': subnet_id}))


Defining multiple resources of the same type
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

So far, we have defined singular resources based on singular definitions in the YAML config. Suppose we have a case
where we might want to build more resources of the same type without adjusting code. In this case, we might want some
YAML that looks like this:

.. code-block:: yaml

  ---
  resources:
    tb:network:SecurityGroupWithRules:
      backend-database:
        rules:
          ingress:
            - description: Let traffic into the DB from our IP range
              cidr_blocks:
                - 10.0.0.0/8
              protocol: tcp
              from_port: 5432
              to_port: 5432
          egress:
            - description: Let the DB talk out
              protocol: tcp
              from_port: 0
              to_port: 65535
              cidr_blocks:
                - 0.0.0.0/0
      backend-api-lb:
        rules:
          ingress:
            - description: Let traffic into the API service from anywhere
              cidr_blocks:
                - 0.0.0.0/0
              protocol: tcp
              from_port: 443
              to_port: 443
          egress:
            - description: Let the LB talk out
              protocol: tcp
              from_port: 0
              to_port: 65535
              cidr_blocks:

We do not have to explicitly define both of these security groups. We can feed the data in via dict comprehension:

.. code-block:: python

   sgs = {
       sg_name: tb_pulumi.network.SecurityGroupWithRules(
           name=f'{project.name_prefix}-sg-{sg_name}',
           project=project,
           vpc_id=vpc.resources.get('vpc').id,
           opts=pulumi.ResourceOptions(depends_on=[vpc]),
           **sg_config,
       )
       for sg_name, sg_config in resources['tb:network:SecurityGroupWithRules'].items()
   }


Handling Secrets
----------------

Applications often need to operate on values such as database passwords that are considered secrets. You never want to
store these values in plaintext, since that is a security risk, and they should always be protected by policies
preventing unauthorized access.

To some extent, this problem is partially solved by Pulumi itself, which allows you to store secret values directly in
its configuration using hashes only decryptable with a secret passphrase.

To set a Pulumi secret value, make sure you have the right encryption passphrase exported and run a ``pulumi config``
statement like so:

.. code-block:: bash

    export PULUMI_CONFIG_PASSPHRASE='a-super-secret-passphrase'
    pulumi config set --secret my-password 'P@$sw0rd'

This will add an item to your ``Pulumi.$STACK_NAME.yaml`` file in which this secret is listed in encrypted form. This is
considered secure because the data cannot be decrypted without the secret passphrase, which you should always keep
secret and secure.

But many AWS configurations will require that secret values come out of their Secrets Manager product. ECS Task
Definitions, for example, take in Secrets Manager ARNs to feed secret data into environment variables. To help bridge
the gap between Pulumi and AWS, we have the :py:class:`tb_pulumi.secrets.PulumiSecretsManager` class. Feed this a list
of ``secret_names`` which match Pulumi secret names. This module will create AWS secrets matching those Pulumi secrets.

For example, if we've run the above ``pulumi config`` command, we could add a section to our YAML config that looks like
this:

.. code-block:: yaml

  ---
  resources:
  # ...
    tb:secrets:PulumiSecretsManager:
      secrets:
        secret_names:
          - my-password

And later, we could add the following code to our tb_pulumi program:

.. code-block:: python

  psm_opts = resources.get('tb:secrets:PulumiSecretsManager', {}).get('secrets')
  psm = tb_pulumi.secrets.PulumiSecretsManager(
    name='my-secrets',
    project=project,
    **psm_opts,
  )

This would ultimately create a series of Secrets Manager entries named after the listed secrets. Using this pattern
makes sure that your secret data stays secret the whole way through to the cloud provider.


.. _autoscaling_fargate_cluster_patterns:

Designing Autoscaling Fargate Clusters
--------------------------------------

The :py:class:`tb_pulumi.fargate.AutoscalingFargateCluster` class provides a one-stop pattern for deploying Fargate
services. It improves upon the :py:class:`tb_pulumi.fargate.FargateClusterWithLogging` class in a variety of ways:

- Supports multiple services per cluster
- Allows full control over load balancing
- Internally builds security groups connecting load balancers and containers

.. note::

    The ``FargateClusterWithLogging`` will become deprecated in a future version and eventually removed in favor of the
    ``AutoscalingFargateCluster`` class.

The class documentation is thorough, but does little to guide you through the design of your cluster and the
configuration that leads to that design working. Therefore, we have this bit of documentation, which helps step you
through the process of setting up a cluster.

Before writing out any configuration, consider what services you will need to expose. Come up with a YAML-friendly name
for each of them. You will eventually name some configurations after these terms, and you will need to reference them
elsewhere before you define those services, so it is best to have a clear idea of this before diving in. In our example,
we will define one exposed API service (``svc_exposed_api``) and one unexposed background worker service
(``svc_background_worker``).

.. note::
  
  You probably want your cluster running on private network space. At any rate, you will need to provide a list of valid
  subnets on which to run your tasks. We recommend setting up a :py:class:`tb_pulumi.network.MultiCidrVpc` or a
  :py:class:`tb_pulumi.network.MultiTierVpc` and using the subnet resources it creates as inputs to your autoscaling
  Fargate cluster.

That accomplished, begin with some YAML, following our conventions:

.. code-block:: yaml

  ---
  resources:
  # ...
    tb:fargate:AutoscalingFargateCluster:
      my_cluster:
        # ...

The cluster itself is little more than an organizational unit for services. Typically, you can let it run with defaults,
specifying only a name:

.. code-block:: yaml

  # ...
      my_cluster:
        cluster: {} # You can specify other cluster settings here if necessary
        cluster_name: my-cluster # How this appears in the ECS clusters console

Now work out your task definitions. For each service you intend to run (whether it will be exposed through a load
balancer or not), add an entry to your config:

.. code-block:: yaml

  # ...
        cluster_name: my-cluster
        task_definitions:
          svc_background_worker:
            container_definitions:
              - name: ctr_background_worker
            # ... other container/task definition options
          svc_exposed_api:
            # ... task definition

What you put in the various service entries is `documented by AWS
<https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_TaskDefinition.html>`_.

.. note::

  Task definitions can contain multiple container definitions. Each of those has a name. You can name them anything you
  like, but they must be unique in the cluster. You will need to reference these names later in the service
  configurations.

Now define your targets. A target is a service exposed through a network port on one of your containers. Each target's
name will be referred to later by load balancer configurations. The values for each target are the inputs to a
`TargetGroup Pulumi resource <https://www.pulumi.com/registry/packages/aws/api-docs/lb/targetgroup/>`_.

.. code-block:: yaml

  # ...
        targets:
          tgt_exposed_api:
            name: exposed-api-stage
            port: 1234
            protocol: HTTP
            target_type: ip
            ip_address_type: ipv4
            health_check:
              port: 1234
              path: /health
              protocol: HTTP

.. note::

  Not every task in a service necessarily exposes a port. The background worker in our example only ever pulls jobs from
  another source, never even opening a network port. For these services, you should write task definitions and so on,
  but not targets, nor load balancers, nor load balancer security groups.

Now define your load balancers. You will need a load balancer for any service you wish to expose. Load balancers do not
have to be public facing (set ``internal: yes``). The term you provide as the key for each load balancer config here
will be referenced later in other parts of the config. The configuration options are inputs to `aws.lb.LoadBalancers
<https://www.pulumi.com/registry/packages/aws/api-docs/lb/loadbalancer/>`_. Remember that a load balancer's ``name``
attribute can be no longer than 32 characters, a limit imposed by AWS's API.

.. code-block:: yaml

  # ...
        load_balancers:
          lb_exposed_api:
            enable_cross_zone_load_balancing: yes
            internal: yes
            ip_address_type: ipv4
            load_balancer_type: application
            name: exposed-api-stage # 32 characters max

Next, design the security groups for your containers. In this config, we refer to our own
:py:class:`tb_pulumi.network.SecurityGroupWithRules` pattern, and we organize around the names of services and load
balancers. The reason for including the load balancer names here is that the code can determine the correct set of
security group rules to allow traffic from each service's load balancer to its corresponding targets. If a service does
not expose a port through a load balancer, use the string "none" to define a security group without making this network
association.

.. code-block:: yaml

  # ...
        container_security_groups:
          svc_background_worker:
            none:
              description: SG for background worker
              rules:
                egress:
                  - from_port: 0
                    to_port: 65535
                    protocol: tcp
                    description: Allow all egress
                    cidr_blocks:
                      - 0.0.0.0/0
                    ingress: []  # The worker doesn't allow inbound traffic
          svc_exposed_api:
            lb_exposed_api:
              description: SG for API worker
              rules:
                egress:
                  - from_port: 0
                    to_port: 65535
                    protocol: tcp
                    description: Allow all egress
                    cidr_blocks:
                      - 0.0.0.0/0
                ingress:
                  - from_port: 1234
                    to_port: 1234
                    protocol: tcp
                    description: Allow API traffic from internal network only
                    # The source for this rule will be added programmatically, referring to the load balalncer's SG

Now we do the same thing for our load balancer security groups. These are listed by the name of the load balancer they
apply to.

.. code-block:: yaml

  # ...
        load_balancer_security_groups:
          lb_exposed_api:
            rules:
              egress:
                # ... Rule to allow egress
              ingress:
                - from_port: 443
                  to_port: 443
                  protocol: tcp
                  description: Allow TLS traffic from local network only
                  cidr_blocks:
                    - 10.0.0.0/8

With our load balancers set up, we can now describe each one's listeners. A listener is a port the load balancer holds
open. It is associated with some rules defining which of its targets to route traffic to. This class automatically sets
up port-based forwarding rules between the load balancer and target you set. Use those terms when setting up listeners.

.. code-block:: yaml

  # ...
        listeners:
          lb_exposed_api: # The load balancer to attach the listener to
            tgt_exposed_api: # The target to route this traffic to
              certificate_arn: arn:aws:acm:etc:etc:etc # Certificate to terminate SSL with
              port: 443
              protocol: HTTPS


Finally, we can define services. These are scalable workloads which tie together all of the elements we've just set up.
If your service doesn't expose a port, you can leave off the various routing options.

.. code-block:: yaml

  # ...
        services:
          svc_background_worker:
            assign_public_ip: yes # This is usually required, if only to access a container image repository
            service: # Inputs to an ECS Service resource go in here
              desired_count: 1
            target: null # There is no target
          svc_exposed_api:
            assign_public_ip: yes
            container_name: ctr_background_worker
            container_port: 1234
            load_balancer: lb_exposed_api
            service:
              desired_count: 1 # The autoscaler will take over managing this value later
            target: tgt_exposed_api

We also have to define any special resources that these services need access to in order to launch and run. This
typically involves access to ECR registries (for pulling container images), secret values stored in AWS Secrets Manager,
and runtime parameters stored in AWS Systems Manager (SSM). For these, provide lists of ARNs or ARN patterns under the
names of the services that need access to them, or provide empty objects where no access is needed.

.. code-block:: yaml

  # ...
        registries:
          svc_background_worker:
            - arn:aws:ecr:eu-central-1:123456789098:repository/bgworker/*
          svc_exposed_api:
            - arn:aws:ecr:eu-central-1:123456789098:repository/api/*
        
        secrets:
          svc_background_worker:
            - arn:aws:secretsmanager:eu-central-1:123456789098:secret:bgworker/stage/*
          svc_exposed_api:
            - arn:aws:secretsmanager:eu-central-1:123456789098:secret:bgworker/stage/*
        
        ssm_params: {}

The last thing to write up is our autoscaling demand. Each service gets a configuration for a
:py:class:`tb_pulumi.autoscale.EcsServiceAutoscaler`.

.. code-block:: yaml

  # ...
        autoscalers:
          svc_background_worker:
            min_capacity: 1
            max_capacity: 2
          svc_exposed_api:
            min_capacity: 2
            max_capacity: 4

And that's it! A ``pulumi up`` should bring up this cluster.


.. _full_stack_patterns:

Acting on Fully Applied Pulumi Stacks
-------------------------------------

One limitation of raw Pulumi code is that the programmatic visibility into resources you have defined stops at the
individual resource level. ComponentResources give you no ability to inspect those components. As shown in previous
examples, the ThunderbirdComponentResource restores that ability.

As we have also shown, the outputs generated by these Resources and ComponentResources must be applied before you can
access their actual values. This can create some complexity where, for example, you may define a
ThunderbirdComponentResource that contains other ThunderbirdComponentResources. To access the resources of the inner
nested ThunderbirdComponentResource, you have to do a nested apply lambda. Your code gets very confusing at this point,
and hard to follow and debug.

Furthermore, if you need to create something like CloudWatch alarms for your resources, this leaves you defining those
alarms individually. If you add a new resource you want to monitor, you would have to write that code, or develop some
other module to set the monitors up.

Wouldn't it be great if you could develop Pulumi code that simply acts on all resources in a project with full context
about those resources? Then you could write any kind of stack-aware meta-tool you like and act on the entire stack at
once.

Fortunately, tb_pulumi solves this problem as well. There is an abstract class called
:py:class:`tb_pulumi.ProjectResourceGroup` which can be extended, its :py:meth:`tb_pulumi.ProjectResourceGroup.ready`
function implemented to act in just such a fully resolved state. This function (with a little help from
:py:meth:`tb_pulumi.ThunderbirdPulumiProject.flatten`) recursively detects all outputs in a stack and resolves them,
calling that ``ready`` function only when everything is completely resolved and available.

For more information on developing ProjectResourceGroups, see :ref:`development`. Currently, we have two specific
implementations.

This first pertains to monitoring. That is described fully on the :ref:`monitoring_resources` page. The other is related
to granting access to your AWS resources with :py:class:`tb_pulumi.iam.StackAccessPolicies`.