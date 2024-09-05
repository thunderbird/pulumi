import pulumi
import pulumi_aws as aws
import tb_pulumi
import tb_pulumi.network
import tb_pulumi.secrets

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


AMAZON_LINUX_AMI='ami-0427090fd1714168b'


class NetworkLoadBalancer(tb_pulumi.ThunderbirdComponentResource):
    '''Create a Network Load Balancer.'''

    def __init__(self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        listener_port: int,
        subnets: list[str],
        target_port: int,
        ingress_cidrs: list[str] = None,
        internal: bool = True,
        ips: list[str] = [],
        security_group_description: str = None,
        opts: pulumi.ResourceOptions = None,
        **kwargs
    ):
        '''Construct a NetworkLoadBalancer to route TCP traffic to a collection of backends. This
            targets backend services by IP address, connecting a frontend listening port to a
            backend port on the round-robin load balanced targets.

        Positional arguments:
            - name: A string identifying this set of resources.
            - project: The ThunderbirdPulumiProject to add these resources to.
            - listener_port: The port that the load balancer should accept traffic on.
            - subnets: List of subnet resource outputs. The NLB will be built in these network
                spaces, and in the VPC of the first subnet listed (they must all be in the same
                VPC).
            - target_port: The port to route to on the backends.

        Keyword arguments:
            - ingress_cidrs: List of CIDR blocks to allow ingress to the NLB from. If not provided,
                traffic to the listener_port will be allowed from anywhere.
            - internal: When True (default), ingress is restricted to traffic sourced within the
                VPC. When False, the NLB gets a public IP to listen on.
            - ips: List of IP addresses to balance load between.
            - security_group_description: Text to use for the security group's description field.
            - opts: Additional pulumi.ResourceOptions to apply to these resources.
            - kwargs: Any other keyword arguments which will be passed as inputs to the LoadBalancer
                resource. A full listing of options is found here:
                https://www.pulumi.com/registry/packages/aws/api-docs/alb/loadbalancer/#inputs
        '''

        super().__init__('tb:ec2:NetworkLoadBalancer', name, project, opts=opts)

        # Build a security group that allows ingress on our listener port
        self.resources['security_group_with_rules'] = tb_pulumi.network.SecurityGroupWithRules(f'{name}-sg',
            project,
            vpc_id=subnets[0].vpc_id,
            rules={
                'ingress': [{
                    'cidr_blocks': ingress_cidrs if ingress_cidrs else ['0.0.0.0/0'],
                    'description': 'Allow ingress',
                    'protocol': 'tcp',
                    'from_port': listener_port,
                    'to_port': listener_port}],
                'egress': [{
                    'cidr_blocks': ['0.0.0.0/0'],
                    'description': 'Allow egress',
                    'protocol': 'tcp',
                    'from_port': target_port,
                    'to_port': target_port}]},
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self)).resources

        # Build the load balancer first, as other resources must be attached to it later
        self.resources['nlb'] = aws.alb.LoadBalancer(f'{name}-nlb',
            enable_cross_zone_load_balancing=True,
            internal=internal,
            load_balancer_type='network',
            name=name,
            security_groups=[self.resources['security_group_with_rules']['sg']],
            subnets=[subnet.id for subnet in subnets],
            tags=self.tags,
            opts=pulumi.ResourceOptions(
                parent=self,
                depends_on=[self.resources['security_group_with_rules']['sg']]),
            **kwargs)

        # Build and attach a target group
        self.resources['target_group'] = aws.lb.TargetGroup(f'{name}-targetgroup',
            health_check={
                'enabled': True,
                'healthy_threshold': 3,
                'interval': 20,
                'port': target_port,
                'protocol': 'TCP',
                'timeout': 10,
                'unhealthy_threshold': 3},
            load_balancing_cross_zone_enabled=True,
            name=name,
            port=target_port,
            protocol='TCP',
            target_type='ip',
            vpc_id=subnets[0].vpc_id,
            tags=self.tags,
            opts=pulumi.ResourceOptions(
                parent=self,
                depends_on=[self.resources['nlb']]))

        # Add targets to the target group
        self.resources['target_group_attachments'] = []
        for idx, ip in enumerate(ips):
            self.resources['target_group_attachments'].append(
                aws.lb.TargetGroupAttachment(f'{name}-tga-{idx}',
                    target_group_arn=self.resources['target_group'].arn,
                    target_id=ip,
                    port=target_port,
                    opts=pulumi.ResourceOptions(
                        parent=self,
                        depends_on=[self.resources['target_group']])))

        # Build the listener, sending traffic to the target group
        self.resources['listener'] = aws.lb.Listener(f'{name}-listener',
            default_actions=[{
                'type': 'forward',
                'target_group_arn': self.resources['target_group'].arn}],
            load_balancer_arn=self.resources['nlb'].arn,
            port=listener_port,
            protocol='TCP',
            tags=self.tags,
            opts=pulumi.ResourceOptions(
                parent=self,
                depends_on=[
                    self.resources['nlb'],
                    self.resources['target_group']]))

        self.finish()


class SshableInstance(tb_pulumi.ThunderbirdComponentResource):
    '''Builds an EC2 instance which can be accessed with SSH from somewhere on the Internet.'''

    def __init__(self,
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
        **kwargs
    ):
        '''Construct an SshableInstance.

        Positional arguments:
            - name: A string identifying this set of resources.
            - project: The ThunderbirdPulumiProject to add these resources to.
            - subnet_id: The ID of the subnet to build the instance in.

        Keyword arguments:
            - ami: ID of the AMI to build the instance with. Defaults to Amazon Linux 2023.
            - kms_key_id: ID of the KMS key for encrypting all database storage.
            - public_key: The RSA public key used for SSH authentication.
            - source_cidrs: List of CIDRs which should be allowed to open SSH connections to the
                instance.
            - user_data: Custom user data to launch the instance with.
            - vpc_id: The VPC to build this instance in.
            - vpc_security_group_ids: If provided, sets the security groups for the instance.
                Otherwise, a security group allowing only port 22 from the `source_cidrs` will be
                created and used.
            - opts: Additional pulumi.ResourceOptions to apply to these resources.
            - kwargs: Any other keyword arguments which will be passed as inputs to the
                ThunderbirdComponentResource superconstructor.
        '''

        super().__init__('tb:ec2:SshableInstance', name, project, opts=opts, **kwargs)

        self.resources['keypair'] = SshKeyPair(f'{name}-keypair',
            project,
            public_key=public_key).resources

        if not vpc_security_group_ids:
            self.resources['security_group_with_rules'] = tb_pulumi.network.SecurityGroupWithRules(f'{name}-sg',
                project,
                vpc_id=vpc_id,
                rules={
                    'ingress': [{
                        'cidr_blocks': source_cidrs,
                        'description': 'SSH access',
                        'protocol': 'tcp',
                        'from_port': 22,
                        'to_port': 22}],
                    'egress': [{
                        'cidr_blocks': ['0.0.0.0/0'],
                        'description': 'Allow all egress',
                        'protocol': 'tcp',
                        'from_port': 0,
                        'to_port': 65535}]},
                opts=pulumi.ResourceOptions(parent=self)).resources
            sg_ids = [self.resources['security_group_with_rules']['sg'].id]
        else:
            sg_ids = vpc_security_group_ids

        instance_tags = {'Name': name}
        instance_tags.update(self.project.common_tags)
        self.resources['instance'] = aws.ec2.Instance(f'{name}-instance',
            ami=ami,
            associate_public_ip_address=True,
            disable_api_stop=False,         # Jump hosts should never contain live services or
            disable_api_termination=False,  # be the source of data; they don't need protection.
            instance_type='t3.micro',
            key_name=self.resources['keypair']['keypair'].key_name,
            root_block_device={
                'encrypted': True,
                'kms_key_id': kms_key_id,
                'volume_size': 10,
                'volume_type': 'gp3'},
            subnet_id=subnet_id,
            user_data=user_data,
            volume_tags=self.tags,
            vpc_security_group_ids=sg_ids,
            tags=instance_tags,
            opts=pulumi.ResourceOptions(parent=self))

        self.finish()


class SshKeyPair(tb_pulumi.ThunderbirdComponentResource):
    '''Builds an SSH keypair and stores its values in Secrets Manager.

    NOTE: This should typically be used by specifying the public_key. If you do not, Pulumi will
    generate a new key for you. However, at the moment, it appears there's no way to have Pulumi
    generate a private key ONE TIME and ONLY ONE TIME. Each `pulumi up/preview` command generates a
    new keypair, which generates new secret versions (and if this is attached to an instance
    downstream, it triggers the recreation of that instance). This is otherwise good code that will
    correctly build these resources.
    '''

    def __init__(self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        key_size: int = 4096,
        public_key: str = None,
        secret_name: str = 'keypair',
        opts: pulumi.ResourceOptions = None,
        **kwargs
    ):
        '''Construct an SshKeyPair.

        Positional arguments:
            - name: A string identifying this set of resources.
            - project: The ThunderbirdPulumiProject to add these resources to.

        Keyword arguments:
            - key_size: Byte length of the private key to generate. Only used if public_key is not
                supplied.
            - public_key: RSA public key to stash in the KeyPair. It is highly recommended that you
                always provide this. That is, you should usually generate a keypair on your local
                machine (ssh-keygen -t rsa -b 4096) and provide that public key to this resource.
            - secret_name: A slash ("/") delimited name to give the Secrets Manager secret. If not
                supplied, one will be generated based on `name`. Only used if public_key is not
                provided.
            - opts: Additional pulumi.ResourceOptions to apply to these resources.
            - kwargs: Any other keyword arguments which will be passed as inputs to the
                ThunderbirdComponentResource superconstructor.
        '''

        super().__init__('tb:ec2:SshKeyPair', name, project, opts=opts, **kwargs)

        if not public_key:
            self.resources['private_key'], self.resources['public_key'] = \
                generate_ssh_keypair(key_size=key_size)
            self.resources['keypair'] = aws.ec2.KeyPair(f'{name}-keypair',
                key_name=name,
                public_key=self.resources['public_key'],
                tags=self.tags,
                opts=pulumi.ResourceOptions(
                    parent=self,
                    depends_on=[self.resources['private_key']]))

            if secret_name is not None:
                suffix = 'keypair'
            else:
                suffix = secret_name
            prefix = f'{tb_pulumi.PROJECT}/{tb_pulumi.STACK}/{suffix}'
            priv_secret = f'{prefix}/private_key'
            pub_secret = f'{prefix}/public_key'

            self.resources['private_key_secret'] = tb_pulumi.secrets.SecretsManagerSecret(f'{name}/privatekey',
                project,
                secret_name=priv_secret,
                secret_value=self.resources['private_key'],
                opts=pulumi.ResourceOptions(
                    parent=self,
                    depends_on=[self.resources['private_key']]))
            self.resources['public_key_secret'] = tb_pulumi.secrets.SecretsManagerSecret(f'{name}/publickey',
                project,
                secret_name=pub_secret,
                secret_value=self.resources['public_key'],
                opts=pulumi.ResourceOptions(
                    parent=self,
                    depends_on=[self.resources['public_key']]))
        else:
            self.resources['keypair'] = aws.ec2.KeyPair(f'{name}-keypair',
                key_name=name,
                public_key=public_key,
                tags=self.tags,
                opts=pulumi.ResourceOptions(parent=self))

        self.finish()


def generate_ssh_keypair(key_size=4096) -> (str, str):
    '''Returns plaintext representations of a private and public RSA key for use in SSH
    authentication.

        - key_size: Byte length of the private key.
    '''

    # Ref: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/rsa/#module-cryptography.hazmat.primitives.asymmetric.rsa
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size)
    private_key = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()).decode('utf-8')
    public_key = key.public_key().public_bytes(
        serialization.Encoding.OpenSSH,
        serialization.PublicFormat.OpenSSH).decode('utf-8')

    return private_key, public_key