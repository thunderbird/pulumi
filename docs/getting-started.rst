.. _getting_started:

Getting Started
===============

The classes in this module are intended to provide easy access to common infrastructural patterns in use at Thunderbird.
This should...

* help you set up a Pulumi project,
* reduce most infrastructure configuration to values in a YAML file,
* simplify the process of building complete infrastructural patterns.

As such, it is somewhat opinionated, requires certain usage patterns, and strongly suggests some usage conventions.

Prerequisites
-------------

To use this module, you'll need to get through this checklist first:

* Ensure Python 3.12 or greater is installed on your system.
* `Install Pulumi <https://www.pulumi.com/docs/iac/download-install/>`_.
* Understand the `basic concepts of Pulumi <https://www.pulumi.com/docs/iac/concepts/>`_, particularly `Resources
  <https://www.pulumi.com/docs/iac/concepts/resources/>`_ and `Component Resources
  <https://www.pulumi.com/docs/iac/concepts/resources/components/>`_.
* Provide an `awscli configuration <https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html>`_ with
  your credentials and default region. (You do not have to install awscli, though you can
  `read how to here <https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html>`_.
  Some of these docs refer to helpful awscli commands.) The Pulumi AWS provider relies on the same configuration,
  though, so you must create the config file.
* Optionally, set up an `S3 bucket`_ to store your Pulumi state in.

The `Troubleshooting`_ section has some details on how to work through some issues related to setup.


.. _quickstart:

Quickstart
----------

After ensuring you meet the above prerequisites, run the ``quickstart.sh`` script, adjusting the following command to
refer to your particular project details:

.. code-block:: bash

 ./quickstart.sh \
     /path/to/project/root \ # The root of your code project where you want to set up a pulumi project
     pulumi_login_url      \ # URL to use with `pulumi login`; use "https://api.pulumi.com" for Pulumi Cloud
     project_name, \         # Name of your project as it will be known to pulumi
     stack_name, \           # Name of the first stack you want to create
     [code_version]          # Code version (git branch) that you want to pin. Optional; defaults to "main"

This will...

* run you through some prompts where you can enter further project details,
* install a simple Pulumi program intended to set up a basic networking landscape,
* run a ``pulumi preview`` command to finish setting up the environment and confirm the project is working.

If you are using an S3 bucket to privately store your state, you'll need to make sure you have configured your AWSCLI
tool with an account that has permission to manipulate that bucket. Prefix your bucket name with `s3://` to use as your
`pulumi_login_url` value (e.g.,: `s3://acme-awesomeapi-pulumi`). If you will use Pulumi Cloud, use
`https://api.pulumi.com`. If you have a
`self-hosted Pulumi Cloud API <https://www.pulumi.com/docs/pulumi-cloud/admin/self-hosted/components/api/>`_, you may
specify your custom URL here.

The output should look something like this:
::

  Previewing update (mystack):
       Type                              Name                                 Plan
   +   pulumi:pulumi:Stack               myproject-mystack                    create
   +   ├─ tb:network:MultiCidrVpc        myproject-mystack-vpc                create
   +   │  ├─ aws:ec2:Vpc                 myproject-mystack-vpc                create
   +   │  ├─ aws:ec2:Subnet              myproject-mystack-vpc-subnet-0       create
   +   │  ├─ aws:ec2:Subnet              myproject-mystack-vpc-subnet-1       create
   +   │  └─ aws:ec2:Subnet              myproject-mystack-vpc-subnet-2       create
   +   ├─ aws:ec2:RouteTableAssociation  myproject-mystack-vpc-subnetassoc-0  create
   +   ├─ aws:ec2:RouteTableAssociation  myproject-mystack-vpc-subnetassoc-1  create
   +   └─ aws:ec2:RouteTableAssociation  myproject-mystack-vpc-subnetassoc-2  create

  Resources:
      + 9 to create


Manual Setup
------------

If you want to do everything the Quickstart script does manually (or just understand this project framework better),
follow this guide.

S3 bucket
^^^^^^^^^

.. note:: This step is optional. If you do not set up an S3 bucket, you can use Pulumi Cloud instead by specifying
  ``https://api.pulumi.com`` or a custom self-hosted URL when you run ``pulumi login`` in the next step.

Create an S3 bucket in which to store state for the project. You must have one bucket devoted to your project, but you
can store multiple stacks' state files in that one bucket. The bucket should not be public (treat these files as
sensitive), and it's usually a good idea to turn on versioning.

The name of an S3 bucket is used as part of a global domain, and so your bucket name must be globally unique. A good way
to handle this is to include an organization name in your bucket name. As a template, you may use:
::

  $ORG-$PROJECT_NAME-pulumi


Repo setup
^^^^^^^^^^

You probably already have a repository with your application code in it. If not, create one now.

Create a subdirectory called ``pulumi`` and create a new project and stack in it. You'll need the name of the S3
bucket or cloud host from the previous step here. If you are operating in an AWS region other than what is set as your
default for AWSCLI, be sure to ``export AWS_REGION=us-east-1`` or whatever else you may need to do to override that.

.. code-block:: bash

  cd /path/to/pulumi/code
  pulumi login s3://s3-bucket-name
  pulumi new aws-python

Follow the prompts to get everything named.


Set up this module
^^^^^^^^^^^^^^^^^^

Ensure your pulumi code directory contains a ``requirements.txt`` file with at least this repo listed:
::

  git+https://github.com/thunderbird/pulumi.git

You can pin your code to a specific version of this module by appending ``@branch_name`` to that. For example:
::

  git+https://github.com/thunderbird/pulumi.git@v0.0.11

Pulumi will need these requirements installed. On your first run of a ``pulumi preview`` command (or some others),
Pulumi will attempt to set up its working environment. If this fails, or you need to make adjustments later, you can
activate Pulumi's virtual environment to perform pip changes. Assuming Pulumi's virtual environment lives at ``venv``,
run:

.. code-block:: bash

  source ./venv/bin/activate
  pip install -U -r requirements.txt

You can now develop Python Pulumi code in that directory, as shown in the following section.

Use this module
^^^^^^^^^^^^^^^

When you issue ``pulumi`` commands (like "up" and "preview" and so on), it looks for a ``__main__.py`` file in your
current directory and executes the code in that file.

``__main__.py` imports and uses the ``tb_pulumi`` module:

.. code-block:: python

  import tb_pulumi

  # ...or...

  from tb_pulumi import (ec2, fargate, secrets)

Create a config file
""""""""""""""""""""

Create a config file for each stack, i.e., ``config.$STACK.yaml`` (where ``$STACK`` maps to a Pulumi stack/application
environment). This file maps parameters for tb_pulumi resources to their desired values. Currently, only the
``resources`` setting is formally recognized.

.. note::

   When you run ``pulumi stack select $STACK``, these two files become active:
   ``Pulumi.$STACK.yaml`` and ``config.$STACK.yaml``.
   If you're already familiar with Pulumi, you might recognize that this
   patterns follows Pulumi's conventions.


Let's look at an example tb_pulumi configuration file.

.. code-block:: yaml

    resources:
      tb:network:MultiCidrVpc:
        vpc:
          cidr_block: 10.0.0.0/16
          egress_via_internet_gateway: True
          enable_dns_hostnames: True
          enable_internet_gateway: True
          endpoint_interfaces:
            - ecr.api
            - ecr.dkr
            - logs
            - secretsmanager
          subnets:
            us-east-2a:
              - 10.0.101.0/24
            us-east-2b:
              - 10.0.102.0/24
            us-east-2c:
              - 10.0.103.0/24

At the top-level is the ``resources`` key. Nested inside are configurations for kinds of resources. This resource uses
the ``tb_pulumi.network.MultiCidrVpc`` class.

.. note::
    We recommend using resource key names that are named after the Pulumi Types for each resource. These are documented
    alongside each class in the :py:mod:`tb_pulumi` module.

The Pulumi Type for a ``MultiCidrVpc`` is ``tb:network:MultiCidrVpc``, so we have chosen that as a name under which we
define our MultiCidrVpc configs. We call this one particular config ``vpc`` (you normally need only one, though this
convention allows for as many as you like).

Next, we see a resource named ``tb:fargate:FargateClusterWithLogging``:

.. code-block:: yaml

    tb:fargate:FargateClusterWithLogging:
      backend:
        assign_public_ip: True
        ecr_resources:
          - arn:aws:ecr:us-east-2:1234567890123:repository/rockroll*
        health_check_grace_period_seconds: 60
        internal: False
      api:
        assign_public_ip: True
        ecr_resources:
          - arn:aws:ecr:us-east-2:1234567890124:repository/rockrollapi*
        health_check_grace_period_seconds: 60
        internal: False

It configures two Fargate clusters named ``backend`` and an ``api``.

Note that the specific names ``backend`` and ``api`` are reusable for other resources, such as these security groups:

.. code-block:: yaml

    tb:network:SecurityGroupWithRules:
      backend:
        rules:
          ingress:
            - cidr_blocks: ["0.0.0.0/0"]
              description: TLS port for the load balancer
              protocol: tcp
              from_port: 443
              to_port: 443
          egress:
            - cidr_blocks: ["0.0.0.0/0"]
              description: Outbound traffic
              protocol: tcp
              from_port: 0
              to_port: 65535
      api:
        rules:
          ingress:
            - description: Private backend port
              protocol: tcp
              from_port: 8080
              to_port: 8080
          egress:
            - cidr_blocks: ["0.0.0.0/0"]
              description: Outbound traffic
              protocol: tcp
              from_port: 0
              to_port: 65535

The only other requirement is that you provide valid options and values in your configuration. The full listing of these
values can be found by browsing the :py:mod:`tb_pulumi` documentation.

A barebones example can be found in our `sample config
<https://github.com/thunderbird/pulumi/blob/main/config.stack.yaml.example>`_.


Define a ThunderbirdPulumiProject
"""""""""""""""""""""""""""""""""

In your ``__main__.py`` file, start with a simple skeleton (or use ``__main__.py.example`` to start):

.. code-block:: python

  import tb_pulumi
  project = tb_pulumi.ThunderbirdPulumiProject()

If you have followed the conventions outlined above, ``project.config`` is now a dict representation of the YAML file.
You can use this in the next step to feed parameters into resource declarations.

Moreover, as you create resources with this library, the ``project`` will track them, making them available to you later
to act on as a group. This is explained in more detail on the :ref:`monitoring_resources` page.


Declare ThunderbirdComponentResources
"""""""""""""""""""""""""""""""""""""

A `Pulumi ComponentResource <https://www.pulumi.com/docs/reference/pkg/python/pulumi/#pulumi.ComponentResource>`_ is a
collection of related resources. In an effort to follow consistent patterns across infrastructure projects, the
patterns available in this module all extend a custom class called a :py:class:`tb_pulumi.ThunderbirdComponentResource`.
If you have followed the conventions outlined so far, it should be easy to stamp out infrastructure with them by passing
``project.config`` config options into the constructors for these classes.


Implementing ThunderbirdComponentResources
""""""""""""""""""""""""""""""""""""""""""

So you want to develop a new pattern to stamp out? Here's what you'll need to do:

* Determine the best place to put the code. Is there an existing module that fits the bill?
* Determine the Pulumi type string for it. This goes: ``org:module:class``. The ``org`` should be unique to your
  organization. For Thunderbird projects, it should be ``tb``. The ``module`` will be the Python submodule you're
  placing the new class in (e.g., classes in ``network.py`` should use ``network`` here). The ``class`` is whatever
  you've called the class.
* Design the class following these guidelines:
    * The constructor should always accept, before any other arguments, the following positional options:
        * ``name``: The internal name of the resource as Pulumi tracks it.
        * ``project``: The ThunderbirdPulumiProject these resources belong to.
    * The constructor should always accept the following keyword arguments:
        * ``opts``: A ``pulumi.ResourceOptions`` object which will get merged into the default set of arguments managed
          by the project.
    * The constructor should explicitly define only those arguments that you intend to have default values which differ
      from the default values the provider will set, or which imply larger patterns.
    * The constructor may accept a final ``**kwargs`` argument with arbitrary meaning. Because the nature of a component
      resource is to compile many other resources into one class, it is not implicitly clear what "everything else"
      should apply to. If this is implemented, its function should be clearly documented in the class. If this isn't
      passed into the superconstructor, you will need to implement all superconstructor arguments into your constructor.
    * The class should extend :py:class:`tb_pulumi.ThunderbirdComponentResource`.
    * The class should make an appropriate call to its superconstructor, which ensures the resources can be properly
      tracked in the project (and other things).
    * Any resources you create must have the ``parent=self`` ``pulumi.ResourceOption`` set. Set an appropriate
      ``depends_on`` value.
    * At the end of the ``__init__`` function, you must call ``self.finish()``, passing in a dictionary of ``resources``
      (see :py:meth:`tb_pulumi.ThunderbirdComponentResource.finish`). For
      :py:class:`tb_pulumi.monitoring.MonitoringGroup` derivatives, call this at the end of the
      :py:meth:`tb_pulumi.monitoring.MonitoringGroup.monitor` function instead.

The ``finish`` function also supports an ``outputs`` option, a dict containing outputs to register with Pulumi using
their ``register_outputs`` function. However,
`Pulumi's documentation <https://www.pulumi.com/docs/iac/concepts/resources/components/#registering-component-outputs>`_`
is unclear on the purpose of this, you cannot access these outputs programmatically, and the
`Pulumi developers also don't know <https://github.com/pulumi/pulumi/issues/2653#issuecomment-484956028>`_ why you
should call it. Its only purpose is within the CLI tool, as simple output at the end of the run. As such, we will stop
allowing this in a future version, opting to make the ``register_outputs`` call with an empty dict, as is common among
Pulumi developers.


Troubleshooting
---------------


Pythonic problems
^^^^^^^^^^^^^^^^^

This Pulumi code is developed against Python 3.12 or later. If this is not your default version, you'll need to manage
your own virtual environment.

Check your default version:
::

  $ python -V
  Python 3.12.6

If you need a newer Python, `download and install it <https://www.python.org/downloads/>`_. Then you'll have to set up
the virtual environment yourself with something like this:

.. code-block:: bash

  virtualenv -p /path/to/python3.12 venv
  ./venv/bin/pip install -r requirements.txt

After this, ``pulumi`` commands should work. If 3.12 is your default version of Python, Pulumi should set up its own
virtualenv, and you should not have to do this.


Shells other than Bash
^^^^^^^^^^^^^^^^^^^^^^

Setup instructions in these docs are designed for use with the Bourne Again SHell (Bash). Pulumi also seems to make some
assumptions like this when it installs itself. Pulumi will install itself into a hidden folder in your home directory:
``~/.pulumi/bin``. You may need to add this to your ``$PATH`` to avoid having to make the explicit reference with every
``pulumi`` command.
