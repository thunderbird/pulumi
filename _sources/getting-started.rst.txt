.. _getting_started:

Getting Started
===============

The tb_pulumi module has a few guiding principals and helpful features:

- It should meet the needs of Thunderbird Pro Services while also being otherwise useful to the community.
- It should reduce the overhead of working with a project long-term by front-loading most development work and moving
  most settings that one might adjust over time to a simple configuration file.
- It should make use of Pulumi's extensibility to create a broader model of infrastructure management operations beyond
  the management of singular resources.

In order to accomplish these things, tb_pulumi must be rather opinionated. It requires certain usage patterns and
strongly suggests some additional usage conventions. This Getting Started guide will get you up and running with this
tool and adapt to its particularities, setting you up to make the most use of its advanced features. When you've stepped
through it, you should have a simple project structure with a basic private network configuration. This is a good
starting point for further development.


Prerequisites
-------------

To use tb_pulumi, you'll need to get through this checklist first:


Get an AWS Account
^^^^^^^^^^^^^^^^^^

This module builds infrastructure against Amazon Web Services. You will need to `sign up
<https://signin.aws.amazon.com/signup?request_type=register>`_ for an account there. Our patterns default to using
infrastructure that typicaly qualifies for AWS Free Tier, but you should know that usage of this tool always implies
cost at AWS.

Once you have an account, you will need to `set up an access key
<https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html>`_. You will then need to `configure
AWSCLI <https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html>`_ with those credentials. You do not
need to install the AWSCLI tool itself.


Build a State Backend
^^^^^^^^^^^^^^^^^^^^^

Pulumi keeps an accounting of the state of your infrastructure in online storage, enabling it to track that state for
multiple users across multiple executions of Pulumi commands. There are three ways to store this. You will have to set
up one of the following options:

- Create an S3 bucket in AWS. This should be a completely private bucket with no external access. The user you have
  configured an access key for must have full access to this bucket and its objects. To use this, you will have to run
  ``pulumi login s3://your-bucket-name``.
- Create a `Pulumi Cloud account <https://app.pulumi.com/>`_. To use this, you will have to run ``pulumi login`` without
  specifying a backend, or ``pulumi login https://api.pulumi.com``.
- Set up a custom Pulumi Cloud server and use the URL for that server.  

.. note::

  The name of an S3 bucket is used as part of a global domain, and so your bucket name must be globally unique. A good
  way to handle this is to include an organization name in your bucket name. As a template, you may use:
  ``$ORG-$PROJECT_NAME-pulumi``.

Each time you set up to use your Pulumi code, you will need to run:

.. code-block:: bash

  pulumi login $YOUR_LOGIN_URL


Install Python 3.13 or greater
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There are many ways to install Python. You can begin with the `Python downloads page
<https://www.pulumi.com/docs/iac/download-install/>`_.


Install Pulumi
^^^^^^^^^^^^^^

Pulumi provides `instructions for installation <https://www.pulumi.com/docs/iac/download-install/>`_ on their website.
You should follow those instructions to install the latest version of Pulumi.

You should also come to understand the `basic concepts of Pulumi <https://www.pulumi.com/docs/iac/concepts/>`_,
particularly `Resources <https://www.pulumi.com/docs/iac/concepts/resources/>`_ and `Component Resources
<https://www.pulumi.com/docs/iac/concepts/resources/components/>`_.


.. _quickstart:

Quickstart
----------

After ensuring you meet the above prerequisites, run the ``quickstart.sh`` script, adjusting the following command to
refer to your particular project details:

.. code-block:: bash

 ./quickstart.sh           \
     /path/to/project/root \ # The root of your code project where you want to set up a tb_pulumi project
     pulumi_login_url      \ # URL to use with `pulumi login`; see below for details
     project_name,         \ # Name of your project as it will be known to pulumi
     stack_name,           \ # Name of the first stack you want to create (such as "stage" or "dev")
     [code_version]          # Code version (git branch) that you want to pin. Optional; defaults to "main"

This will...

- run you through some prompts where you can enter further project details,
- install a simple Pulumi program intended to set up a basic networking landscape,
- install the same ``dev-setup.sh`` script into your Pulumi directory, which allows developers to quickly set up a
  working development environment, and
- run a ``pulumi preview`` command to finish setting up the environment and confirm the project is working.

If you are using an S3 bucket to privately store your state, you'll need to make sure you have configured your AWSCLI
tool with an account that has permission to manipulate that bucket and its contents. To specify an S3 state backend, set
the login URL to ``s3://your-bucket-name``. If you will use Pulumi Cloud, use ``https://api.pulumi.com``. If you have a
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

  "What's so quick about the quickstart anyway?" ~ You, probably

If you want to do everything the Quickstart script does manually (or just understand this project framework better),
follow this guide.


Repo setup
^^^^^^^^^^

We strongly recommend the use of a version control system such as git when working with your tb_pulumi project. If you
already have a repository containing the source code for your application, then it is recommended to put your Pulumi
code inside that same repo.

Create a subdirectory called ``pulumi/`` and create a new Pulumi project in it with the command below. If you are
operating in an AWS region other than what is set as your default for awscli, be sure to
``export AWS_REGION=your-region-here`` or whatever else you may need to do to override that.

All tb_pulumi projects are AWS/Python projects.

.. code-block:: bash

  pulumi new aws-python

Follow the prompts to complete the initial Pulumi setup. This builds the ``Pulumi.yaml`` file that describes project-
wide settings.


Stack Setup
^^^^^^^^^^^

In Pulumi, a stack roughly translates to an operating environment. You should identify your needs and determine an
appropriate name for your first stack. As an example, on the Thunderbird Services Team, we have "stage" and "prod"
stacks to describe our testing and live environments. Initialize your first stack:

.. code-block:: bash

  pulumi stack init $STACK_NAME

This will create a ``Pulumi.$STACK_NAME.yaml`` file which defines the operating parameters for this particular stack.


Set up tb_pulumi
^^^^^^^^^^^^^^^^

Ensure your ``pulumi`` code directory contains a ``requirements.txt`` file with at least this repo listed:

.. code-block:: text

  tb_pulumi @ git+https://github.com/thunderbird/pulumi.git

You can pin your code to a specific version of this module by appending ``@branch_name`` to that. For example:

.. code-block:: text

  tb_pulumi @ git+https://github.com/thunderbird/pulumi.git@v0.0.14

If your project relies on any other Python dependencies, also list them in this file. This ensures that Pulumi can
bootstrap itself with tb_pulumi and other dependencies all accounted for.


Configure tb_pulumi
^^^^^^^^^^^^^^^^^^^

Whereas ``Pulumi.$STACK_NAME.yaml`` describes how Pulumi handles that one stack, a ``config.$STACK_NAME.yaml`` file
describes the properties of tb_pulumi patterns you will later define in your Pulumi code. The contents of the
``resources`` entry will become the ``config`` property of your project in code.

Let's look at an example tb_pulumi configuration file.

.. code-block:: yaml
    :linenos:

    ---
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

At the top-level (line 2) is the ``resources`` key. Nested inside are configurations for resource patterns. This project
uses the ``tb_pulumi.network.MultiCidrVpc`` class. In Pulumi, resources have a `"type" string
<https://www.pulumi.com/docs/iac/concepts/resources/names/#types>`_, and by convention, we use the same format to
identify these patterns. In this case, you can see how the class ``tb_pulumi.network.MultiCidrVpc`` maps to the type
string ``tb:network:MultiCidrVpc``.

The Pulumi Type for a ``MultiCidrVpc`` is ``tb:network:MultiCidrVpc``, so we have chosen that as a name under which we
define our MultiCidrVpc configs (line 3).

You can define multiple instances of the same pattern, so the next nested key is the name of this instance. In most of
the use cases described in these docs and in our projects, you don't normally need more than one VPC per environment.
Still, you can see how this pattern and the code patterns described below can be useful in many other cases. Let's just
call this one ``vpc``.


Write a tb_pulumi Program
^^^^^^^^^^^^^^^^^^^^^^^^^

The resources you've described in your YAML file must now be described in your Pulumi code. Under tb_pulumi's
conventions, this is mostly a matter of connecting the YAML config values to resource class constructors.

When you issue ``pulumi`` commands (like "up" and "preview" and so on), Pulumi looks for a ``__main__.py`` file in your
current directory and executes the code in that file. So it is this file in which you will make use of the ``tb_pulumi``
code library.


Import tb_pulumi
""""""""""""""""

The imports are simple enough:

.. code-block:: python

  # You can import the whole library
  import tb_pulumi

  # ...or you can import specific modules...
  from tb_pulumi import (ec2, fargate, secrets)



Set up a ThunderbirdPulumiProject
"""""""""""""""""""""""""""""""""

A Pulumi project describes the infrastructural resources that underlie your application. In a typical Pulumi program,
you describe these resources more or less in the order of dependency, passing outputs of one resource (like a subnet ID)
as inputs to other resources (like an EC2 instance that needs to know what network space to attach to). You can even
describe larger repeatable patterns as ``ComponentResource`` s.

However, a raw ``ComponentResource`` offers us very little visibility into its makeup. Although the class allows us to
register outputs, those outputs only ever appear in text in a console and cannot be acted on programmatically. One way
in which tb_pulumi extends the capabilities of Pulumi is with its :py:class:`tb_pulumi.ThunderbirdComponentResource`
class, which provides us with this visibility. These are the basic building blocks of tb_pulumi programs.

These ``ThunderbirdComponentResource`` s are collected together under another class, the
:py:class:`tb_pulumi.ThunderbirdPulumiProject`. This is a special kind of Pulumi project that is aware of its own
resources. It is able to traverse all resources defined in a project and act on them and their outputs programmatically
due to the added visibility of the ``ThunderbirdComponentResource`` s in use.

These projects are easy to set up:

.. code-block:: python

  project = tb_pulumi.ThunderbirdPulumiProject()

If you have followed the conventions outlined so far, ``project.config`` is now a Python dict representation of the YAML
file (see :py:data:`tb_pulumi.ThunderbirdPulumiProject.config`) for the currently selected Pulumi stack. You can use
this in the next step to feed parameters into resource declarations. When you change a stack (``pulumi stack select``),
this config changes with it.


Declare ThunderbirdComponentResources
"""""""""""""""""""""""""""""""""""""

A tb_pulumi program typically does little more than map the ``project.config`` values into ThunderbirdComponentResource
constructor calls. To start, for convenience, let's pull the ``resources`` dict into a variable:

.. code-block:: python

  # Pull the "resources" config mapping
  resources = project.config.get('resources')
  
Continuing the ``MultiCidrVpc`` example, let's now pull the config for our ``vpc`` resource:

.. code-block:: python

  vpc_opts = resources.get('tb:network:MultiCidrVpc', {}).get('vpc')

And then define the ``MultiCidrVpc``:

.. code-block:: python

  vpc = tb_pulumi.network.MultiCidrVpc(
      name=f'{project.name_prefix}-vpc',
      project=project,
      **vpc_opts)

The :py:data:`tb_pulumi.ThunderbirdPulumiProject.name_prefix` value combines the project and stack name to form a
convenient identifier to give your resources useful names. Here, we add ``-vpc`` to it, giving us something like
``myproject-stage-vpc``.

Passing in the ``project`` created beforehand ensures the resources created by the MultiCidrVpc get tracked and become
accessible at the project level. The ThunderbirdComponentResource cannot be created without a ThunderbirdPulumiProject.

Finally, in Python, the double-star (``**variable``) notation unpacks a dict's top level keys and values into function
parameters (called "keyword arguments" and often referred to as "kwargs"). In this case, all of the key/value pairs in
the YAML configuration for the MultiCidrVpc called "vpc" get passed in as arguments to the function.

As a demonstration of this (and as a demonstration of code you *should not write* when using tb_pulumi), here is the
equivalent function call without the YAML conversion:

.. code-block:: python

  vpc = tb_pulumi.network.MultiCidrVpc(
      name=f'{project.name_prefix}-vpc',
      project=project,
      cidr_block='10.0.0.0/16',
      subnets={
        'us-east-1a': '10.0.101.0/24',
        'us-east-1b': '10.0.102.0/24',
        'us-east-1c': '10.0.103.0/24',
      },
  )

You may note some disadvantages to this:

- Making configuration changes to an environment means editing code as opposed to adjusting YAML. We find the YAML to be
  more legible, and we find that after an environment is initially built, the infrastructural patterns do not often
  change. Rather, we adjust the details; we scale out new servers or use a larger instance type or allow a new IP
  address access to a system. These are easier to adjust when we can just find an entry in a sensibly organized config
  file and tweak it.
- Reusing the same broad infrastructural definitions becomes much harder here. Suppose we want our staging environment
  to use different IP space than our production environment. If code is written this explicitly, we must introduce
  conditionals and break Pulumi's comprehension of stacks to accomodate each environment's distinguishing
  characteristics.

Instead, under the tb_pulumi model, we can apply different YAML configs to the same code to achieve environments that
work the same way, but at different scales, against different sets of resources, etc.

.. seealso::

  Additional detail on our conventions can be found in :ref:`patterns_of_use`.

The full listing of values supported by each pattern can be found by browsing the detailed :py:mod:`tb_pulumi`
documentation. The barebones config example used in the quickstart can be found in our `sample config
<https://github.com/thunderbird/pulumi/blob/main/config.stack.yaml.example>`_.


Troubleshooting
---------------


The Pulumi Virtual Environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

On your first run of a ``pulumi`` command, Pulumi will set up a Python virtual environment for itself to work out of at
``venv/``. If this fails, or you need to make adjustments later, you can activate Pulumi's virtual environment to
perform environment changes.

.. code-block:: bash

  source ./venv/bin/activate
  pip install -Ur requirements.txt

It is also always safe (and often easiest) to completely delete the virtual environment. Pulumi will automatically set
itself up again on its next run.

.. code-block:: bash

  rm -rf venv/

Deactivate the environment before running any more ``pulumi`` commands, though, or else Pulumi will become confused.

.. code-block:: bash

  deactivate
  pulumi preview


Pythonic problems
^^^^^^^^^^^^^^^^^

This Pulumi code is developed against Python 3.13 or later. If this is not your default version, you'll need to manage
your own virtual environment.

Check your default version:
::

  $ python -V
  Python 3.13.5

If you need a newer Python, `download and install it <https://www.python.org/downloads/>`_. Then you'll have to set up
the virtual environment yourself with something like this:

.. code-block:: bash

  virtualenv -p /path/to/python3.13 venv
  ./venv/bin/pip install .

You could also use a tool like `uv <https://docs.astral.sh/uv/guides/install-python/>`_ to manage your Python version.

After this, ``pulumi`` commands should work. If 3.13 is your default version of Python, Pulumi should set up its own
virtual environment, and you should not have to do this.


Shells other than Bash
^^^^^^^^^^^^^^^^^^^^^^

Setup instructions in these docs are designed for use with the Bourne Again SHell (Bash). The Pulumi installer places
the ``pulumi`` executable in a hidden folder in your home directory: ``~/.pulumi/bin``. The installer will add this to
your default ``$PATH`` for you, but only on certain supported shells. If you use an alternative shell, you may need to
do this step manually to avoid having to make an explicit path reference for every ``pulumi`` command.
