"""Infrastructural patterns related to `AWS EC2 <https://docs.aws.amazon.com/ec2/>`_."""

import pulumi
import pulumi_aws as aws
import tb_pulumi
import tb_pulumi.network
import tb_pulumi.secrets

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


AMAZON_LINUX_AMI = 'ami-02ccbe126fe6afe82'  #: AMI for Amazon Linux


class NetworkLoadBalancer(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:ec2:NetworkLoadBalancer``

    Construct a NetworkLoadBalancer to route TCP traffic to a collection of backends. This targets backend services
    by IP address, connecting a frontend listening port to a backend port on the round-robin load balanced targets.

    Produces the following ``resources``:

        - *security_group_with_rules* - :py:class:`tb_pulumi.network.SecurityGroupWithRules` defining ingress and egress
          rules for the NLB.
        - *nlb* - `aws.lb.LoadBalancer <https://www.pulumi.com/registry/packages/aws/api-docs/lb/loadbalancer/>`_ with a
          ``load_balancer_type`` of ``network``.
        - *target_group* - `aws.lb.TargetGroup <https://www.pulumi.com/registry/packages/aws/api-docs/lb/targetgroup/>`_
          containing the IPs the NLB is balancing.
        - *target_group_attachments* - List of `aws.lb.TargetGroupAttachments
          <https://www.pulumi.com/registry/packages/aws/api-docs/lb/targetgroupattachment/>`_, one for each IP address
          registered with the NLB.
        - *listener* - `aws.lb.Listener <https://www.pulumi.com/registry/packages/aws/api-docs/lb/listener/>`_ for the
          NLB.

    :param name: A string identifying this set of resources.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param listener_port: The port that the load balancer should accept traffic on.
    :type listener_port: int

    :param subnets: List of subnet resource outputs. The NLB will be built in these network spaces, and in the VPC
        of the first subnet listed. All subnets must reside in the same VPC.
    :type subnets: list[str]

    :param target_port: The port to route to on the backends.
    :type target_port: int

    :param ingress_cidrs: List of CIDR blocks to allow ingress to the NLB from. If not provided, traffic to the
        listener_port will be allowed from anywhere. Defaults to None.
    :type ingress_cidrs: list[str], optional

    :param internal: When True (default), ingress is restricted to traffic sourced within the VPC. When False, the
        NLB gets a public IP to listen on. Defaults to True.
    :type internal: bool, optional

    :param ips: List of IP addresses to balance load between. Defaults to [].
    :type ips: list[str], optional

    :param security_group_description: Text to use for the security group's description field. Defaults to None.
    :type security_group_description: str, optional

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param tags: Key/value pairs to merge with the default tags which get applied to all resources in this group.
        Defaults to {}.
    :type tags: dict, optional

    :param kwargs: Any other keyword arguments which will be passed as inputs to the LoadBalancer resource. A full
        listing of options is found `here
        <https://www.pulumi.com/registry/packages/aws/api-docs/alb/loadbalancer/#inputs>`_.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        listener_port: int,
        subnets: list[str],
        target_port: int,
        exclude_from_project: bool = False,
        ingress_cidrs: list[str] = None,
        internal: bool = True,
        ips: list[str] = [],
        security_group_description: str = None,
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
        **kwargs,
    ):
        super().__init__(
            'tb:ec2:NetworkLoadBalancer',
            name=name,
            project=project,
            exclude_from_project=exclude_from_project,
            opts=opts,
            tags=tags,
        )

        # The primary_subnet is just the first subnet listed, used for determining VPC placement
        primary_subnet = subnets[0]

        # Build a security group that allows ingress on our listener port
        security_group_with_rules = tb_pulumi.network.SecurityGroupWithRules(
            f'{name}-sg',
            project=project,
            vpc_id=primary_subnet.vpc_id,
            exclude_from_project=True,
            rules={
                'ingress': [
                    {
                        'cidr_blocks': ingress_cidrs if ingress_cidrs else ['0.0.0.0/0'],
                        'description': 'Allow ingress',
                        'protocol': 'tcp',
                        'from_port': listener_port,
                        'to_port': listener_port,
                    }
                ],
                'egress': [
                    {
                        'cidr_blocks': ['0.0.0.0/0'],
                        'description': 'Allow egress',
                        'protocol': 'tcp',
                        'from_port': target_port,
                        'to_port': target_port,
                    }
                ],
            },
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Build the load balancer first, as other resources must be attached to it later
        nlb = aws.lb.LoadBalancer(
            f'{name}-nlb',
            enable_cross_zone_load_balancing=True,
            internal=internal,
            load_balancer_type='network',
            name=name,
            security_groups=[security_group_with_rules.resources['sg']],
            subnets=[subnet.id for subnet in subnets],
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[security_group_with_rules.resources['sg']]),
            **kwargs,
        )

        # Build and attach a target group
        target_group = aws.lb.TargetGroup(
            f'{name}-targetgroup',
            health_check={
                'enabled': True,
                'healthy_threshold': 3,
                'interval': 20,
                'port': target_port,
                'protocol': 'TCP',
                'timeout': 10,
                'unhealthy_threshold': 3,
            },
            load_balancing_cross_zone_enabled=True,
            name=name,
            port=target_port,
            protocol='TCP',
            target_type='ip',
            vpc_id=primary_subnet.vpc_id,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[nlb, primary_subnet]),
        )

        # Add targets to the target group
        target_group_attachments = []
        for idx, ip in enumerate(ips):
            target_group_attachments.append(
                aws.lb.TargetGroupAttachment(
                    f'{name}-tga-{idx}',
                    target_group_arn=target_group.arn,
                    target_id=ip,
                    port=target_port,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[target_group]),
                )
            )

        # Build the listener, sending traffic to the target group
        listener = aws.lb.Listener(
            f'{name}-listener',
            default_actions=[{'type': 'forward', 'target_group_arn': target_group.arn}],
            load_balancer_arn=nlb.arn,
            port=listener_port,
            protocol='TCP',
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[nlb, target_group]),
        )

        self.finish(
            resources={
                'security_group_with_rules': security_group_with_rules,
                'nlb': nlb,
                'target_group': target_group,
                'target_group_attachments': target_group_attachments,
                'listener': listener,
            },
        )


class SshableInstance(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:ec2:SshableInstance``

    Builds an EC2 instance which can be accessed with SSH from somewhere on the Internet.

    Produces the following ``resources``:

        - *instance* - The `aws.ec2.Instance <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/instance/>`_.
        - *keypair* - :py:class:`tb_pulumi.ec2.SshKeyPair` used for authenticating to the instance.
        - *security_group* - :py:class:`tb_pulumi.network.SecurityGroupWithRules` defining network access to the
          instance.

    :param name: A string identifying this set of resources.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param subnet_id: The ID of the subnet to build the instance in.
    :type subnet_id: str

    :param ami: ID of the AMI to build the instance with. Defaults to {AMAZON_LINUX_AMI}.
    :type ami: str, optional

    :param kms_key_id: ID of the KMS key for encrypting all database storage. Defaults to None.
    :type kms_key_id: str, optional

    :param public_key: The RSA public key used for SSH authentication. Defaults to None.
    :type public_key: str, optional

    :param source_cidrs: List of CIDRs which should be allowed to open SSH connections to the instance. Defaults to
        ['0.0.0.0/0'].
    :type source_cidrs: list[str], optional

    :param user_data: Custom user data to launch the instance with. Defaults to None.
    :type user_data: str, optional

    :param vpc_id: The VPC to build this instance in. Defaults to None.
    :type vpc_id: str, optional

    :param vpc_security_group_ids: If provided, sets the security groups for the instance. Otherwise, a security group
        allowing only port 22 from the `source_cidrs` will be created and used. Defaults to None.
    :type vpc_security_group_ids: list[str], optional

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param kwargs: Any other keyword arguments which will be passed as inputs to the ThunderbirdComponentResource
        superconstructor.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        subnet_id: str,
        ami: str = AMAZON_LINUX_AMI,
        kms_key_id: str = None,
        public_key: str = None,
        source_cidrs: list[str] = ['0.0.0.0/0'],
        user_data: str = None,
        vpc_id: str = None,
        vpc_security_group_ids: list[str] = None,
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        super().__init__('tb:ec2:SshableInstance', name=name, project=project, opts=opts, **kwargs)

        keypair = SshKeyPair(f'{name}-keypair', project, public_key=public_key)

        if not vpc_security_group_ids:
            security_group_with_rules = tb_pulumi.network.SecurityGroupWithRules(
                f'{name}-sg',
                project,
                vpc_id=vpc_id,
                exclude_from_project=True,
                rules={
                    'ingress': [
                        {
                            'cidr_blocks': source_cidrs,
                            'description': 'SSH access',
                            'protocol': 'tcp',
                            'from_port': 22,
                            'to_port': 22,
                        }
                    ],
                    'egress': [
                        {
                            'cidr_blocks': ['0.0.0.0/0'],
                            'description': 'Allow all egress',
                            'protocol': 'tcp',
                            'from_port': 0,
                            'to_port': 65535,
                        }
                    ],
                },
                opts=pulumi.ResourceOptions(parent=self),
                tags=self.tags,
            )
            sg_ids = [security_group_with_rules.resources['sg'].id]
        else:
            sg_ids = vpc_security_group_ids

        instance_tags = {'Name': name}
        instance_tags.update(self.project.common_tags)
        instance = aws.ec2.Instance(
            f'{name}-instance',
            ami=ami,
            associate_public_ip_address=True,
            disable_api_stop=False,  # Jump hosts should never contain live services or
            disable_api_termination=False,  # be the source of data; they don't need protection.
            instance_type='t3.micro',
            key_name=keypair.resources['keypair'].key_name,
            root_block_device={'encrypted': True, 'kms_key_id': kms_key_id, 'volume_size': 10, 'volume_type': 'gp3'},
            subnet_id=subnet_id,
            user_data=user_data,
            volume_tags=self.tags,
            vpc_security_group_ids=sg_ids,
            tags=instance_tags,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[keypair.resources['keypair']]),
        )

        self.finish(
            resources={
                'instance': instance,
                'keypair': keypair,
                'security_group': security_group_with_rules,
            },
        )


class SshKeyPair(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:ec2:SshKeyPair``

    Builds an SSH keypair and stores its values in Secrets Manager.

    You should usually specify the ``public_key`` when using this module. If you do not, Pulumi will generate a new key
    for you. However, at the moment, it appears there's no way to have Pulumi generate a private key ONE TIME and ONLY
    ONE TIME. Each ``pulumi up/preview`` command generates a new keypair, which generates new secret versions (and if
    this is attached to an instance downstream, it triggers the recreation of that instance).

    Produces the following ``resources``:

        - *keypair* - `aws.ec2.KeyPair <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/keypair/>`_ containing
          the keypair content.
        - *private_key_secret* :py:class:`tb_pulumi.secrets.SecretsManagerSecret` containing the private key data.
        - *public_key_secret* :py:class:`tb_pulumi.secrets.SecretsManagerSecret` containing the public key data.

    :param name: A string identifying this set of resources.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param key_size: Byte length of the private key to generate. Only used if public_key is not supplied. Defaults to
        4096.
    :type key_size: int, optional

    :param public_key: RSA public key to stash in the KeyPair. It is highly recommended that you always provide this.
        That is, you should usually generate a keypair on your local machine (``ssh-keygen -t rsa -b 4096``) and provide
        that public key to this resource. Defaults to None.
    :type public_key: str, optional

    :param secret_name: A slash ("/") delimited name to give the Secrets Manager secret. If not supplied, one will be
        generated based on `name`. Only used if public_key is not provided. Defaults to 'keypair'.
    :type secret_name: str, optional

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param kwargs: Any other keyword arguments which will be passed as inputs to the ThunderbirdComponentResource
        superconstructor.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        key_size: int = 4096,
        public_key: str = None,
        secret_name: str = 'keypair',
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        super().__init__('tb:ec2:SshKeyPair', name, project, opts=opts, **kwargs)

        if not public_key:
            private_key, public_key = generate_ssh_keypair(key_size=key_size)
            keypair = aws.ec2.KeyPair(
                f'{name}-keypair',
                key_name=name,
                public_key=self.resources['public_key'],
                tags=self.tags,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[private_key]),
            )

            if secret_name is not None:
                suffix = 'keypair'
            else:
                suffix = secret_name
            prefix = f'{tb_pulumi.PROJECT}/{tb_pulumi.STACK}/{suffix}'
            priv_secret = f'{prefix}/private_key'
            pub_secret = f'{prefix}/public_key'

            private_key_secret = tb_pulumi.secrets.SecretsManagerSecret(
                f'{name}/privatekey',
                project,
                secret_name=priv_secret,
                secret_value=self.resources['private_key'],
                exclude_from_project=True,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[private_key]),
                tags=self.tags,
            )
            public_key_secret = tb_pulumi.secrets.SecretsManagerSecret(
                f'{name}/publickey',
                project,
                secret_name=pub_secret,
                secret_value=self.resources['public_key'],
                exclude_from_project=True,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[public_key]),
                tags=self.tags,
            )
        else:
            keypair = aws.ec2.KeyPair(
                f'{name}-keypair',
                key_name=name,
                public_key=public_key,
                tags=self.tags,
                opts=pulumi.ResourceOptions(parent=self),
            )

        self.finish(
            resources={
                'keypair': keypair,
                'private_key_secret': private_key_secret if not public_key else None,
                'public_key_secret': public_key_secret if not public_key else None,
            },
        )


def generate_ssh_keypair(key_size: int = 4096) -> (str, str):
    """Returns plaintext representations of a private and public RSA key for use in SSH authentication.

    :param key_size: Byte length of the private key. Defaults to 4096.
    :type key_size: int

    :return: Tuple in this form: ``(private_key, public_key)``
    :rtype: tuple[str, str]
    """

    # Ref: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/rsa/#module-cryptography.hazmat.primitives.asymmetric.rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    private_key = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode('utf-8')
    public_key = (
        key.public_key()
        .public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH)
        .decode('utf-8')
    )

    return private_key, public_key
