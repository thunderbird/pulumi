import pulumi
import pulumi_aws as aws
import tb_pulumi


class MultiCidrVpc(tb_pulumi.ThunderbirdComponentResource):
    '''Builds a VPC with configurable network space.'''

    def __init__(self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        cidr_block: str = '10.0.0.0/16',
        enable_dns_hostnames: bool = None,
        enable_internet_gateway: bool = True,
        enable_nat_gateway: bool = True,
        endpoint_gateways: list[str] = [],
        endpoint_interfaces: list[str] = [],
        subnets: dict = {},
        opts: pulumi.ResourceOptions = None,
        **kwargs
    ):
        '''Construct a MultiCidrVpc resource.

        Positional arguments:
            - name: A string identifying this set of resources.
            - project: The ThunderbirdPulumiProject to add these resources to.

        Keyword arguments:
            - cidr_block: A CIDR describing the IP space of this VPC.
            - enable_dns_hostnames: When True, internal DNS mappings get built for IPs assigned
                within the VPC. This is required for the use of certain other services like
                load-balanced Fargate clusters.
            - enable_internet_gateway: Build an IGW will to allow traffic outbond to the Internet.
            - enable_nat_gateway: Build a NAT Gateway to route inbound traffic.
            - endpoint_gateways: List of public-facing AWS services (such as S3) to create VPC
                gateways to.
            - endpoint_interfaces: List of AWS services to create VPC Interface endpoints for. These
                must match service names listed here:
                https://docs.aws.amazon.com/vpc/latest/privatelink/aws-services-privatelink-support.html)
                **Do not** list the full qualifying name, only the service name portion. f/ex, do
                not use "com.amazonaws.us-east-1.secretsmanager", only use "secretsmanager".
            - subnets: A dict where the keys are the names of AWS Availability Zones in which to
                build subnets and the values are lists of CIDRs describing valid subsets of IPs in
                the VPC `cidr_block` to build in that AZ. f/ex:

                {
                    'us-east-1': ['10.0.100.0/24'],
                    'us-east-2': ['10.0.101.0/24', '10.0.102.0/24']
                }

            - opts: Additional pulumi.ResourceOptions to apply to these resources.
            - kwargs: Any other keyword arguments which will be passed as inputs to the
                ThunderbirdComponentResource superconstructor.
        '''

        super().__init__('tb:network:MultiCidrVpc', name, project, opts=opts, **kwargs)

        # Build a VPC
        vpc_tags = {'Name': name}
        vpc_tags.update(self.tags)
        self.resources['vpc'] = aws.ec2.Vpc(
            name,
            opts=pulumi.ResourceOptions(parent=self),
            cidr_block=cidr_block,
            enable_dns_hostnames=enable_dns_hostnames,
            tags=vpc_tags)

        # Build subnets in that VPC
        self.resources['subnets'] = []
        for idx, subnet in enumerate(subnets.items()):
            az, cidrs = subnet
            for cidr in cidrs:
                subnet_resname = f'{name}-subnet-{idx}'
                subnet_tags = {'Name': subnet_resname}
                subnet_tags.update(self.tags)
                self.resources['subnets'].append(aws.ec2.Subnet(
                    subnet_resname,
                    availability_zone=az,
                    cidr_block=cidr,
                    tags=subnet_tags,
                    vpc_id=self.resources['vpc'].id,
                    opts=pulumi.ResourceOptions(
                        parent=self,
                        depends_on=[self.resources['vpc']])))

        # Associate the VPC's default route table to all of the subnets
        self.resources['route_table_subnet_associations'] = []
        for idx, subnet in enumerate(self.resources['subnets']):
            self.resources['route_table_subnet_associations'].append(
                aws.ec2.RouteTableAssociation(f'{name}-subnetassoc-{idx}',
                    route_table_id=self.resources['vpc'].default_route_table_id,
                    subnet_id=subnet.id))

        # Allow traffic in from the internet
        if enable_internet_gateway:
            ig_tags = {'Name': name}
            ig_tags.update(self.tags)
            self.resources['internet_gateway'] = aws.ec2.InternetGateway(f'{name}-ig',
                vpc_id=self.resources['vpc'].id,
                tags=ig_tags,
                opts=pulumi.ResourceOptions(
                    parent=self,
                    depends_on=self.resources['vpc']))
            self.resources['subnet_ig_route'] = aws.ec2.Route(f'{name}-igroute',
                route_table_id=self.resources['vpc'].default_route_table_id,
                destination_cidr_block='0.0.0.0/0',
                gateway_id=self.resources['internet_gateway'].id,
                opts=pulumi.ResourceOptions(
                    parent=self,
                    depends_on=[
                        self.resources['vpc'],
                        self.resources['internet_gateway']]))

        if enable_nat_gateway:
            self.resources['nat_eip'] = aws.ec2.Eip(f'{name}-eip',
                domain='vpc',
                public_ipv4_pool='amazon',
                network_border_group=self.project.aws_region,
                opts=pulumi.ResourceOptions(
                    parent=self,
                    depends_on=self.resources['vpc']))
            ng_tags = {'Name': name}
            ng_tags.update(self.tags)
            self.resources['nat_gateway'] = aws.ec2.NatGateway(f'{name}-nat',
                allocation_id=self.resources['nat_eip'].allocation_id,
                subnet_id=self.resources['subnets'][0].id,
                tags=ng_tags,
                opts=pulumi.ResourceOptions(
                    parent=self,
                    depends_on=self.resources['nat_eip']))

        # If we have to build endpoints, we have to have a security group to let local traffic in
        if len(endpoint_interfaces + endpoint_gateways) > 0:
            self.resources['endpoint_sg'] = tb_pulumi.network.SecurityGroupWithRules(
                f'{name}-endpoint-sg',
                project,
                vpc_id=self.resources['vpc'].id,
                rules={'ingress': [{
                    'cidr_blocks': [cidr_block],
                    'description': 'Allow VPC access to endpoint-fronted AWS services',
                    'protocol': 'TCP',
                    'from_port': 443,
                    'to_port': 443}],
                'egress': [{
                    'cidr_blocks': ['0.0.0.0/0'],
                    'description': 'Allow all TCP egress',
                    'protocol': 'TCP',
                    'from_port': 0,
                    'to_port': 65535}]},
                opts=pulumi.ResourceOptions(parent=self),
                tags=self.tags).resources

        self.resources['interfaces'] = []
        for svc in endpoint_interfaces:
            self.resources['interfaces'].append(aws.ec2.VpcEndpoint(f'{name}-interface-{svc}',
                private_dns_enabled=True,
                service_name=f'com.amazonaws.{self.project.aws_region}.{svc}',
                security_group_ids=[self.resources['endpoint_sg']['sg'].id],
                subnet_ids=[subnet.id for subnet in self.resources['subnets']],
                vpc_endpoint_type='Interface',
                vpc_id=self.resources['vpc'].id,
                tags=self.tags,
                opts=pulumi.ResourceOptions(
                    parent=self,
                    depends_on=[
                        *self.resources['subnets'],
                        self.resources['endpoint_sg']['sg']])))

        self.resources['gateways'] = []
        for svc in endpoint_gateways:
            self.resources['gateways'].append(aws.ec2.VpcEndpoint(f'{name}-gateway-{svc}',
                route_table_ids=[self.resources['vpc'].default_route_table_id],
                service_name=f'com.amazonaws.{self.project.aws_region}.{svc}',
                vpc_endpoint_type='Gateway',
                vpc_id=self.resources['vpc'].id,
                tags=self.tags,
                opts=pulumi.ResourceOptions(
                    parent=self,
                    depends_on=[
                        *self.resources['subnets'],
                        self.resources['endpoint_sg']['sg']])))


        self.finish()


class SecurityGroupWithRules(tb_pulumi.ThunderbirdComponentResource):
    '''Builds a security group and sets rules for it.'''

    def __init__(self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        rules: dict = {},
        vpc_id: str = None,
        opts: pulumi.ResourceOptions = None,
        **kwargs
    ):
        '''Construct a SecurityGroupWithRules resource.

        Positional arguments:
            - name: A string identifying this set of resources.
            - project: The ThunderbirdPulumiProject to add these resources to.

        Keyword arguments:
            - rules: A dict describing in/egress rules of the following construction:

                {
                    'ingress': [{
                        # Valid inputs to the SecurityGroupRule resource go here. Ref:
                        # https://www.pulumi.com/registry/packages/aws/api-docs/ec2/securitygrouprule/#inputs
                    }],
                    'egress': [{
                        # The same inputs are valid here
                    }]
                }

            - vpc_id: ID of the VPC this security group should belong to. When not set, defaults to
                the region's default VPC.
            - opts: Additional pulumi.ResourceOptions to apply to these resources.
            - kwargs: Any other keyword arguments which will be passed as inputs to the
                ThunderbirdComponentResource superconstructor.
        '''

        super().__init__('tb:network:SecurityGroupWithRules', name, project, opts=opts, **kwargs)

        # Build a security group in the provided VPC
        self.resources['sg'] = aws.ec2.SecurityGroup(
            f'{name}-sg',
            opts=pulumi.ResourceOptions(parent=self),
            name=name,
            description=f'Send Suite backend security group ({self.project.stack})',
            vpc_id=vpc_id,
            tags=self.tags)

        # Set up security group rules for that SG
        self.resources['ingress_rules'] = []
        self.resources['egress_rules'] = []

        ingress_ruledefs = rules['ingress']
        for rule in ingress_ruledefs:
            rule.update({
                'type': 'ingress',
                'security_group_id': self.resources['sg'].id})
            self.resources['ingress_rules'].append(
                aws.ec2.SecurityGroupRule(
                    f'{name}-ingress-{rule['to_port']}',
                    opts=pulumi.ResourceOptions(
                        parent=self,
                        depends_on=[self.resources['sg']]),
                    **rule))

        egress_ruledefs = rules['egress']
        for rule in egress_ruledefs:
            rule.update({
                'type': 'egress',
                'security_group_id': self.resources['sg'].id})
            self.resources['egress_rules'].append(
                aws.ec2.SecurityGroupRule(
                    f'{name}-egress-{rule['to_port']}',
                    opts=pulumi.ResourceOptions(
                        parent=self,
                        depends_on=[self.resources['sg']]),
                    **rule))

        self.finish()