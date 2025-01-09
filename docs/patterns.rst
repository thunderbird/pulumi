Patterns of Use
===============

The patterns contained in this module support our use cases for services hosted at Thunderbird. At an extremely high
level, this module allows us to standardize certain aspects of the Pulumi resources we're building by using a custom
``ComponentResource`` called a :py:class:`tb_pulumi.ThunderbirdComponentResource`. When building your Pulumi project
using this module, you should organize these resources into a :py:class:`tb_pulumi.ThunderbirdPulumiProject`.

Full documentation on the individual resource patterns can be found in the :py:mod:`tb_pulumi` pages.


Patterns for managing projects
------------------------------

One primary goal of this project is to reduce most infrastructural changes to YAML file tweaks once the initial setup is
done, requiring no code inspection or debugging for most common changes. The
:py:class:`tb_pulumi.ThunderbirdPulumiProject` class brings those configs, information about the cloud environment, and
Pulumi project and stack data into a single context. That context is then made available to any
:py:class:`tb_pulumi.ThunderbirdComponentResource` created within that project.

.. note::
   Some may find it easiest to jump straight to the Quickstart on the Getting Started page, or to review the sample
   `configuration <https://github.com/thunderbird/pulumi/blob/main/config.stack.yaml.example>`_ and `program
   <https://github.com/thunderbird/pulumi/blob/main/__main__.py.example>`_ used by the quickstart to see how these
   patterns fit together.


Resource patterns
-----------------

The various classes in tb_pulumi represent commonly used infrastructural patterns. Some of these will depend on the
pre-existence of some other patterns. For example, most services will require some kind of private network space to
operate within. Thus, your infrastructure stack will usually begin with a :py:class:`tb_pulumi.network.MultiCidrVpc` to
establish the network layout.

The resources built by that class will become available as members of its ``resources`` dict. For example:

.. code-block:: python
   :linenos:

   vpc = tb_pulumi.network.MultiCidrVpc(
      'my-vpc',
      various_options=various_values,
      # ...
   )

   # Print the VPC ID
   pulumi.info(f'VPC ID: {vpc.resources["vpc"].id}')'

.. note::
   The outputs and resources for each class are poorly documented right now. The `need for improvment
   <https://github.com/thunderbird/pulumi/issues/75>`_ is noted.


Handling secrets
----------------

Applications often need to operate on values such as database passwords that are considered secrets. You never want to
store these values in plaintext, and they should always be protected by policies preventing unauthorized access. Pulumi
allows you to store secret values directly in its configuration using hashes only decryptable with a secret passphrase.

To set a secret value, run a command like this:

.. code-block:: bash

    pulumi config set --secret my-password 'P@$sw0rd'

The first time you set a Pulumi secret, you will be asked to generate this passphrase. When you do, be sure to log it in
a safe location. Any other users working with your Pulumi code will need this to manipulate your live resources.

Many AWS configurations will require that secret values come out of their Secrets Manager product. To help bridge the
gap between Pulumi and AWS, we have the :py:class:`tb_pulumi.secrets.PulumiSecretsManager` class. Feed this a list of
``secret_names`` which match Pulumi secret names. This module will create AWS secrets matching those Pulumi secrets.

.. note::
   AWS Secrets Manager applies a randomly generated suffix to each secret ARN. This value is not predictable. References
   to secrets typically require you to use this ARN even though it is not predictable. For this reason, you may have to
   run a ``pulumi up`` to generate these secrets before using them as part of, for example, an ECS task definition.