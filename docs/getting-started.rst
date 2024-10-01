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
* `Configure awscli <https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html>`_ with
  your credentials and default region. (You do not have to install awscli, though you can
  `read how to here <https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html>`_.
  Some of these docs refer to helpful awscli commands.)
* Set up an `S3 bucket`_ to store your Pulumi state in.

The `Troubleshooting`_ section has some details on how to work through some issues related to setup.

Quickstart
----------

After ensuring you meet the above prerequisites, run the ``quickstart.sh`` script, adjusting the following command to
refer to your particular project details:
::

  ./quickstart.sh \
    /path/to/project/root          # The root of your code project where you want to set up a pulumi project
    pulumi-state-s3-bucket-name \  # S3 bucket where you'll store your pulumi state files
    project_name, \                # Name of your project as it will be known to pulumi
    stack_name, \                  # Name of the first stack you want to create
    [code_version]                 # Code version (git branch) that you want to pin. Optional; defaults to "main"

This will...

* run you through some prompts where you can enter further project details,
* install a simple Pulumi program intended to set up a basic networking landscape,
* run a ``pulumi preview`` command to finish setting up the environment and confirm the project is working.

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

S3 bucket
^^^^^^^^^

Create an S3 bucket in which to store state for the project. You must have one bucket devoted to your project, but you
can store multiple stacks' state files in that one bucket. The bucket should not be public (treat these files as
sensitive), and it's a good idea to turn on versioning, as it can save you from some difficult situations down the road.

The name of an S3 bucket is used as part of a global domain, and so your bucket name must be globally unique. A good way
to handle this is to include an organization name in your bucket name. As a template, you may use:
::

  $ORG-$PROJECT_NAME-pulumi

Repo setup
^^^^^^^^^^

You probably already have a code repo with your application code in it. If not, create such a repo.

Create a directory there called ``pulumi`` and create a new project and stack in it. You'll need the name of the S3
bucket from the previous step here. If you are operating in an AWS region other than what is set as your default for
AWSCLI, be sure to ``export AWS_REGION=us-east-1`` or whatever else you may need to do to override that.
::

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

  git+https://github.com/thunderbird/pulumi.git@v0.0.2

Pulumi will need these requirements installed. On your first run of a ``pulumi preview`` command (or some others),
Pulumi will attempt to set up its working environment. If this fails, or you need to make adjustments later, you can
activate Pulumi's virtual environment to perform pip changes. Assuming Pulumi's virtual environment lives at ``venv``,
run:
::

  source ./venv/bin/activate
  pip install -U -r requirements.txt

You can now develop Python Pulumi code in that directory, referring to this module with imports such as these:
::

  import tb_pulumi

  # ...or...

  from tb_pulumi import (ec2, fargate, secrets)


Use this module
^^^^^^^^^^^^^^^

When you issue ``pulumi`` commands (like "up" and "preview" and so on), it looks for a ``__main__.py`` file in your
current directory and executes the code in that file. To use this module, you'll import it into that file and write up
some code and configuration files.


Create a config file
""""""""""""""""""""

It is assumed that a config file will exist at ``config.$STACK.yaml`` where ``$STACK`` is the currently selected Pulumi
stack. This file must contain a mapping of names of config settings to their desired values. Currently, only one such
setting is formally recognized. That is ``resources``.

This is a mostly arbitary mapping that you will have to interpret on your own. This allows for flexibility, but we
recommend some conventions here. Namely:

* ``resources`` should be a mapping where the keys are the Pulumi type-strings for the resources they are configuring.
  For example, if you want to build a VPC with several subnets, you might use the ``tb_pulumi.network.MultiCidrVpc``
  class. Following this convention, that should be accompanied by a ``tb:network:MultiCidrVpc`` key in this mapping.
* The values these keys map to should themselves be mappings. This provides a convention where more than one of each
  pattern are configurable. The keys here should be arbitrary but unique identifiers for the resources being configured.
  F/ex: ``backend`` or ``api``.
* The values these keys map to should be a mapping where the keys are valid configuration options for the resources
  being built. The full listing of these values can be found by browsing the documentation.


Define a ThunderbirdPulumiProject
"""""""""""""""""""""""""""""""""

In your ``__main__.py`` file, start with a simple skeleton (or use ``__main__.py.example`` to start):
::

  import tb_pulumi
  project = tb_pulumi.ThunderbirdPulumiProject()

If you have followed the conventions outlined above, ``project`` is now an object with a key property, ``config``, which
gives you access to the config file's data. You can use this in the next step to feed parameters into resource
declarations.


Declare ThunderbirdComponentResources
"""""""""""""""""""""""""""""""""""""

A ``pulumi.ComponentResource`` is a collection of related resources. In an effort to follow consistent patterns across
infrastructure projects, the resources available in this module all extend a custom class called a
``ThunderbirdComponentResource``. If you have followed the conventions outlined so far, it should be easy to stamp out
common patterns with them by passing config options into the constructors for these classes.

.. note::
   The `Quickstart`_ section provides a working minimal example of code that follows these patterns.

Implementing ThunderbirdComponentResources
""""""""""""""""""""""""""""""""""""""""""

So you want to develop a new pattern to stamp out? Here's what you'll need to do:

* Determine the best place to put the code. Is there an existing module that fits the bill?
* Determine the Pulumi type string for it. This goes: ``org:module:class``. The ``org`` should be unique to your
  organization. For Thunderbird projects, it should be ``tb``. The ``module`` will be the Python submodule you're
  placing the new class in. The ``class`` is whatever you've called the class.
* Design the class following these guidelines:
    * The constructor should always accept, before any other arguments, the following positional options:
        * ``name``: The internal name of the resource as Pulumi tracks it.
        * ``project``: The ThunderbirdPulumiProject these resources belong to.
    * The constructor should always accept the following keyword arguments:
        * ``opts``: A ``pulumi.ResourceOptions`` object which will get merged into the default set of arguments managed
          by the project.
    * The constructor should explicitly define only those arguments that you intend to have default values which differ
      from the default values the provider will set, or which imply larger patterns (such as ``build_jumphost`` implying
      other resources, like a security group and its rules, not just an EC2 instance).
    * The constructor may accept a final ``**kwargs`` argument with arbitrary meaning. Because the nature of a component
      resource is to compile many other resources into one class, it is not implicitly clear what "everything else"
      should apply to. If this is implemented, its function should be clearly documented in the class.
    * The class should extend ``tb_pulumi.ThunderbirdComponentResource``.
    * The class should call its superconstructor in the following way:
        * ``super().__init__(typestring, name, project, opts=opts)``
    * Any resources you create should always be assigned a key in ``self.resources``.
    * Any resources you create must have the ``parent=self`` ``pulumi.ResourceOption`` set.
    * At the end of the ``__init__`` function, you must call ``self.finish()``


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
::

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