.. _patterns_of_use:

Patterns of Use
===============

The patterns contained in this module support our use cases for services hosted at Thunderbird. At an extremely high
level, this module allows us to standardize certain aspects of the Pulumi resources we're building by using a custom
``ComponentResource`` called a :py:class:`tb_pulumi.ThunderbirdComponentResource`. When building your Pulumi project
using this module, you should organize these resources into a :py:class:`tb_pulumi.ThunderbirdPulumiProject`.

.. seealso::

   Full documentation on the individual resource patterns can be found in the :py:mod:`tb_pulumi` pages.


Patterns for managing projects
------------------------------

One primary goal of this project is to reduce most infrastructural changes to YAML file tweaks once the initial setup is
done, requiring no code inspection or debugging for most common changes. The
:py:class:`tb_pulumi.ThunderbirdPulumiProject` class brings those configs, information about the cloud environment, and
Pulumi project and stack data into a single context. That context is then made available to any
:py:class:`tb_pulumi.ThunderbirdComponentResource` created within that project.

.. note::
   Some may find it easiest to jump straight to the :ref:`quickstart` on the :ref:`getting_started` page, or to review the sample
   `configuration <https://github.com/thunderbird/pulumi/blob/main/config.stack.yaml.example>`_ and `program
   <https://github.com/thunderbird/pulumi/blob/main/__main__.py.example>`_ used by the quickstart to see how these
   patterns fit together.


Resource patterns
-----------------

The various classes in tb_pulumi represent commonly used infrastructural patterns. Some of these will depend on the
pre-existence of some other patterns. For example, most services will require some kind of private network space to
operate within. Thus, your infrastructure stack will usually begin with a :py:class:`tb_pulumi.network.MultiCidrVpc` to
establish the network layout.

The resources built by that class will become available as members of its ``resources`` dict. The values in these dicts
are all Pulumi Resource objects, but you'll have to wait until the component resource is applied to access them. The
simplest way to do this is to create a Pulumi output out of all the resources in the ThunderbirdComponentResource.

In this example, we build a SecretsManagerSecret, which contains both a Secret and a SecretVersion resource. We wait on
all resources in the secret to be applied, then return the ARN of the secret.

.. code-block:: python
   :linenos:

   secret = tb_pulumi.secrets.SecretsManagerSecret(
      name='mysecretname',
      secret_name='app/env/mysecret',
      secret_value='super duper secret',
   )

   secret_arn = pulumi.Output.all(**secret.resources).apply(
      lambda resources: resources['secret'].arn
   )

The resources produced by each pattern are documented alongside those classes. For example, the
:py:class:`tb_pulumi.secrets.SecretsManagerSecret` documentation lists the ``'secret'`` resource and links to the
Pulumi documentation for that resource type so you can learn about their properties.

In the above example, we build a single component resource by pulling its config out by name. But in some cases, you may
wish to build multiple instances of one pattern based upon the YAML config. Consider a very frequently appearing
resource such as the AWS EC2 Security Group. We provide the :py:class:`tb_pulumi.network.SecurityGroupWithRules` pattern
for building these resources.

Suppose we must govern traffic for both a backend API service and a separate authentication service. We could define the
security groups in YAML:

.. code-block:: yaml

  ---
  resources:
    # ... other resources ...
    tb:network:SecurityGroupWithRules:
      api:
        description: API backend
        rules:
          egress:
            - from_port: 0
              to_port: 0
              protocol: tcp
              description: Allow local egress
              cidr_blocks:
                - 10.0.0.0/16
          ingress:
            - from_port: 8080
              to_port: 8080
              protocol: tcp
              description: Allow local ingress
              cidr_blocks:
                - 10.0.0.0/16
      auth_service:
        description: Auth service backend
        rules:
          egress:
            - from_port: 0
              to_port: 0
              protocol: tcp
              description: Allow all egress
              cidr_blocks:
                - 0.0.0.0/0
          ingress:
            - from_port: 8080
              to_port: 8080
              protocol: tcp
              description: Allow ingress from API
              source_security_group_id: sg-abcdefg0123456789

In the ``__main__.py`` code, we need not explicitly extract each member of the ``tb:network:SecurityGroupWithRules``
config because we can iterate over the items quite easily:

.. code-block:: python

  security_groups = {
      tb_pulumi.network.SecurityGroupWithRules(
          name=f'{project.name_prefix}-sg-{sg_name}',
          project=project,
          **sg_config
      )
      for sg_name, sg_config in resources['tb:network:SecurityGroupWithRules'].items()
  }


Accessing Resources
-------------------

In Pulumi, a Resource can have a number of Outputs, which are pieces of data about a resource that aren't known until
after the resources are "applied" (that is, the real live resources have been altered to match the desired state
defined in your code). Pulumi provides the ComponentResource model to aggregate many Resources into a single code
object.

`Pulumi's documentation <https://www.pulumi.com/docs/iac/concepts/resources/components/#registering-component-outputs>`_
says you should call the ``register_outputs`` function at the end of a ComponentResource's constructor. Crucially,
though, unlike plain Pulumi Resources, these outputs do not become accessible after the ComponentResource is fully
applied. The documentation is unclear on the purpose of this, and the `Pulumi developers also don't know
<https://github.com/pulumi/pulumi/issues/2653#issuecomment-484956028>`_ why you should call it. Its only purpose is
within the CLI tool, as simple output at the end of the run. As such, we will stop allowing this in a future version,
opting to make the ``register_outputs`` call with an empty dict, as is convention among Pulumi developers.                                                                                                                             

The good news is that tb_pulumi restores this missing feature through the :py:class:`tb_pulumi.ThunderbirdPulumiProject`
object. When you pass your project into a ``ThunderbirdComponentResource`` that subsequently makes a ``finish`` call,
the project adds the ``resources`` dict passed into ``finish`` to its own
:py:data:`tb_pulumi.ThunderbirdPulumiProject.resources` dict, organized by the ThunderbirdComponentResource's name. It
also stores these resources internally in the :py:data:`tb_pulumi.ThunderbirdComponentResource.resources` dict. This
structure allows us to inspect not only all of the resources in a project after they've been applied, but all of the
nested resources in the other component resources.

The contents of the ``resources`` dict in a ``ThunderbirdComponentResource`` are all Pulumi Resources with Outputs that
can be applied. The ``resources`` dict of a ``ThunderbirdPulumiProject`` are either Pulumi Resources or some collection
of them. The full set of allowable entries is defined in the :py:type:`tb_pulumi.Flattenable` type alias.

As an example, the following code (which builds a series of security groups and then tries to print their IDs) will fail
with ``Calling __str__ on an Output[T] is not supported`` because the underlying Pulumi logger wants to print a string
but it's getting an unresolved Pulumi Output instead.

.. code-block:: python

   sgs = {
       sg_name: tb_pulumi.network.SecurityGroupWithRules(
           name=f'{project.name_prefix}-sg-{sg_name}',
           project=project,
           vpc_id=vpc.resources['vpc'].id,
           opts=pulumi.ResourceOptions(depends_on=[vpc]),
           **sg_config,
       )
       for sg_name, sg_config in resources['tb:network:SecurityGroupWithRules'].items()
   }

   pulumi.info(f'DEBUG -- {sgs['foo'].resources['sg'].id}')


Instead, wait on the output and then log the ID:

.. code-block:: python

   sgs['foo'].resources['sg'].id.apply(
       lambda sgid: pulumi.info(f'DEBUG -- {sgid}')
   )

This will generate output if you run a ``pulumi up`` to create the resource and generate the ID. It also produces output
on a ``pulumi preview`` if the resource was created on a previous run and the ID has already been generated. It will not
produce output on a preview if the resource does not already exist because the resource has never been applied, but it
will also not throw any errors.

Now suppose you have a component resource which contains other component resources and you need to wait on all of those
sub-resources to be applied before acting on their outputs. For example, a PulumiSecretsManager (PSM) creates a list of
SecretsManagerSecrets (SMS). If we want to produce a list of the resulting secrets' ARNs, we could wait on all of the PSMs'
resources to be applied and then try to get at them:

.. code-block:: python

    pulumi.Output.all(**psm.resources).apply(lambda resources: 
        pulumi.info(f'DEBUG -- {[secret.resources['secret'].arn
            for secret in resources['secrets']]}'))

This waits on all of the SecretsManagerSecrets' resources to be applied before accessing the downstream secrets' ARNs.
It doesn't produce any errors, but it also doesn't produce ARNs:

.. code-block:: text

   DEBUG -- [<pulumi.output.Output object at 0x748bbcfe7a10>, <pulumi.output.Output object at 0x748bbcaa2970>]

That's because those ``arn`` s are also Outputs, and we still have to wait for those to be applied. Luckily, we can 
compile a list of those outputs and then wait on them all to be applied:

.. code-block:: python

    pulumi.Output.all(*[
        sms.resources['secret'].arn
        for sms in psm.resources['secrets']
    ]).apply(
        lambda arns: pulumi.info(f'DEBUG -- {arns}')
    )

This produces output similar to this (slightly edited for readability):

.. code-block:: text

   DEBUG -- [
      'arn:aws:secretsmanager:region_name:account_number:secret:project/stack/secretname1-id',
      'arn:aws:secretsmanager:region_name:account_number:secret:project/stack/secretname2-id'
   ]

The trick here lies in producing a list of those Outputs (the ``.arn`` s), and then using the single-star (``*list``)
notation to expand that into a Pulumi Output made of all of those ``arn`` Outputs, and then waiting for them to apply.


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
