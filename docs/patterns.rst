Patterns of Use
===============

The patterns contained in this module support our use cases for services hosted at Thunderbird. At an extremely high
level, this module allows us to standardize certain aspects of the Pulumi resources we're building by using a custom
``ComponentResource`` called a :py:class:`tb_pulumi.ThunderbirdComponentResource`. When building your Pulumi project
using this module, you should organize these resources into a :py:class:`tb_pulumi.ThunderbirdPulumiProject`.

The following patterns are available:

* :py:class:`tb_pulumi.cloudfront.CloudFrontS3Service`: Store static content in an S3 bucket and serve it up over the
  CloudFront Content Delivery Network.
* :py:class:`tb_pulumi.ec2.NetworkLoadBalancer`: Build a load balancer routing TCP traffic to multiple backends.
* :py:class:`tb_pulumi.ec2.SshKeyPair`: Build an SSH keypair (or supply your own).
* :py:class:`tb_pulumi.ec2.SshableInstance`: Build an EC2 instance allowing SSH access.
* :py:class:`tb_pulumi.fargate.FargateClusterWithLogging`: Run load balanced Docker containers on AWS Fargate.
* :py:class:`tb_pulumi.fargate.FargateServiceAlb`: Balance load between Fargate tasks.
* :py:class:`tb_pulumi.network.MultiCidrVpc`: Build a VPC with configurable network space and routing.
* :py:class:`tb_pulumi.network.SecurityGroupWithRules`: Build a security group with configurable traffic rules.
* :py:class:`tb_pulumi.rds.RdsDatabaseGroup`: Build a database, optionally with replication to multiple downstreams.
* :py:class:`tb_pulumi.secrets.PulumiSecretsManager`: Manage secrets in AWS Secrets Manager based on Pulumi secrets.
* :py:class:`tb_pulumi.secrets.SecretsManagerSecret`: Store a secret value in AWS Secrets Manager.


Project patterns
----------------

The idea is to reduce most infrastructural changes to YAML file tweaks, requiring no code inspection or debugging for
most changes. Python gives us the ``**kwargs`` method of using ``dict`` types to supply arguments to function calls. The
:py:class:`tb_pulumi.ThunderbirdPulumiProject` class gives us access to these YAML files' contents as a ``dict``.
This enables a simple pattern of reading the config and arbitrarily passing its contents into these modules.

.. note::
   It may be best to review the sample `configuration
   <https://github.com/thunderbird/pulumi/blob/main/config.stack.yaml.example>`_ and `program
   <https://github.com/thunderbird/pulumi/blob/main/__main__.py.example>`_ used by the quickstart to see an easy way to
   achieve this.


Setting up a network
--------------------

Your infrastructure stack should usually begin with a :py:class:`tb_pulumi.network.MultiCidrVpc` to establish some
private network space. This will build you a VPC, some subnets, and some network routes. These things will get used by
any resources that present a service to the network, so this will typically be one of the first things to build.


Handling secrets
----------------

Applications often need to operate on values such as database passwords that are considered secrets. You never want to
store these values in plaintext, and they should always be protected by policies preventing unauthorized access. Pulumi
allows you to store secret values directly in its configuration using hashes only decryptable with a secret passphrase.

To set a secret value, run a command like this:
::

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