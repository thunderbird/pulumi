"""Infrastructural patterns related to networking."""

import pulumi
import pulumi_aws as aws
import tb_pulumi


class MultiCidrVpc(tb_pulumi.ThunderbirdComponentResource):
    """Builds a VPC with configurable network space.

    :param name: A string identifying this set of resources.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param cidr_block: A CIDR describing the IP space of this VPC. Defaults to '10.0.0.0/16'.
    :type cidr_block: str, optional

    :param egress_via_internet_gateway: When True, establish an outbound route to the Internet via the Internet
        Gateway. Requires ``enable_internet_gateway=True``. Defaults to False.
    :type egress_via_internet_gateway: bool, optional

    :param egress_via_nat_gateway: When True, establish an outbound route to the Internet via the NAT Gateway.
        Requires ``enable_nat_gateway=True``. Defaults to False.
    :type egress_via_nat_gateway: bool, optional

    :param enable_dns_hostnames: When True, internal DNS mappings get built for IPs assigned within the VPC. This is
        required for the use of certain other services like load-balanced Fargate clusters. Defaults to None.
    :type enable_dns_hostnames: bool, optional

    :param enable_internet_gateway: Build an IGW will to allow traffic outbond to the Internet. Defaults to False.
    :type enable_internet_gateway: bool, optional

    :param enable_nat_gateway: Build a NAT Gateway to route inbound traffic. Defaults to False.
    :type enable_nat_gateway: bool, optional

    :param endpoint_gateways: List of public-facing AWS services (such as S3) to create VPC gateways to. Defaults to
        [].
    :type endpoint_gateways: list[str], optional

    :param endpoint_interfaces: List of AWS services to create VPC Interface endpoints for. These must match service
        names listed `here
        <https://docs.aws.amazon.com/vpc/latest/privatelink/aws-services-privatelink-support.html>`_ **Do not** list
        the full qualifying name, only the service name portion. f/ex, do not use
        ``com.amazonaws.us-east-1.secretsmanager``, only use ``secretsmanager``. Defaults to [].
    :type endpoint_interfaces: list[str], optional

    :param public_subnets: A dict where the keys are the names of AWS Availability Zones in which to build public subnets and the
        values are lists of CIDRs describing valid subsets of IPs in the VPC ``cidr_block`` to build in that AZ.
        f/ex:
        ::

            { 'us-east-1': ['10.0.100.0/24'],
              'us-east-2': ['10.0.101.0/24', '10.0.102.0/24'] }

        Defaults to {}.
    :type subnets: dict, optional

    :param private_subnets: A dict where the keys are the names of AWS Availability Zones in which to build private subnets and the
        values are lists of CIDRs describing valid subsets of IPs in the VPC ``cidr_block`` to build in that AZ.
        f/ex:
        ::

            { 'us-east-1': ['10.0.200.0/24'],
              'us-east-2': ['10.0.201.0/24', '10.0.202.0/24'] }

        Defaults to {}.

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param kwargs: Any other keyword arguments which will be passed as inputs to the ThunderbirdComponentResource
        superconstructor.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        cidr_block: str = '10.0.0.0/16',
        egress_via_internet_gateway: bool = False,
        egress_via_nat_gateway: bool = False,
        enable_dns_hostnames: bool = None,
        enable_internet_gateway: bool = False,
        enable_nat_gateway: bool = False,
        endpoint_gateways: list[str] = [],
        endpoint_interfaces: list[str] = [],
        public_subnets: dict = {},
        private_subnets: dict = {},
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        """ """

        super().__init__('tb:network:MultiCidrVpc', name, project, opts=opts, **kwargs)

        # Build a VPC
        vpc_tags = {'Name': name}
        vpc_tags.update(self.tags)
        vpc = aws.ec2.Vpc(
            name,
            opts=pulumi.ResourceOptions(parent=self),
            cidr_block=cidr_block,
            enable_dns_hostnames=enable_dns_hostnames,
            tags=vpc_tags,
        )

        # Build public subnets in that VPC
        public_subnet_rs = []
        for idx, subnet in enumerate(public_subnets.items()):
            az, cidrs = subnet
            for cidr in cidrs:
                subnet_resname = f'{name}-public-subnet-{idx}'
                subnet_tags = {'Name': subnet_resname}
                subnet_tags.update(self.tags)
                public_subnet_rs.append(
                    aws.ec2.Subnet(
                        subnet_resname,
                        availability_zone=az,
                        cidr_block=cidr,
                        tags=subnet_tags,
                        vpc_id=vpc.id,
                        opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc]),
                    )
                )

        # Build private subnets in that VPC
        private_subnet_rs = []
        for idx, subnet in enumerate(private_subnets.items()):
            az, cidrs = subnet
            for cidr in cidrs:
                subnet_resname = f'{name}-private-subnet-{idx}'
                subnet_tags = {'Name': subnet_resname}
                subnet_tags.update(self.tags)
                private_subnet_rs.append(
                    aws.ec2.Subnet(
                        subnet_resname,
                        availability_zone=az,
                        cidr_block=cidr,
                        tags=subnet_tags,
                        vpc_id=vpc.id,
                        opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc]),
                    )
                )
        # Associate the VPC's default route table to all of the public subnets
        public_route_table_subnet_associations = []
        for idx, subnet in enumerate(public_subnet_rs):
            public_route_table_subnet_associations.append(
                aws.ec2.RouteTableAssociation(
                    f'{name}-public-subnetassoc-{idx}',
                    route_table_id=vpc.default_route_table_id,
                    subnet_id=subnet.id,
                )
            )

        # Create private route table and associate with to all of the private subnets
        private_route_table_tags = {'Name': name}
        private_route_table_tags.update(self.tags)
        private_route_table = aws.ec2.RouteTable("private",
            vpc_id = vpc.id,
            routes = [],
            tags = private_route_table_tags,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc]),
            )
        
        private_route_table_subnet_associations = []
        for idx, subnet in enumerate(private_subnet_rs):
            private_route_table_subnet_associations.append(
                aws.ec2.RouteTableAssociation(
                    f'{name}-private-subnetassoc-{idx}',
                    route_table_id=private_route_table.id,
                    subnet_id=subnet.id,
                )
            )


        # Allow traffic in from the internet
        if public_subnets and enable_internet_gateway:
            ig_tags = {'Name': name}
            ig_tags.update(self.tags)
            internet_gateway = aws.ec2.InternetGateway(
                f'{name}-ig',
                vpc_id=vpc.id,
                tags=ig_tags,
                opts=pulumi.ResourceOptions(parent=self, depends_on=vpc),
            )
            if egress_via_internet_gateway:
                subnet_ig_route = aws.ec2.Route(
                    f'{name}-igroute',
                    route_table_id=vpc.default_route_table_id,
                    destination_cidr_block='0.0.0.0/0',
                    gateway_id=internet_gateway.id,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc, internet_gateway]),
                )

        if private_subnets and enable_nat_gateway:
            nat_eip = aws.ec2.Eip(
                f'{name}-eip',
                domain='vpc',
                public_ipv4_pool='amazon',
                network_border_group=self.project.aws_region,
                opts=pulumi.ResourceOptions(parent=self, depends_on=vpc),
            )
            ng_tags = {'Name': name}
            ng_tags.update(self.tags)
            nat_gateway = aws.ec2.NatGateway(
                f'{name}-nat',
                allocation_id=nat_eip.allocation_id,
                subnet_id=private_subnets[0].id,
                tags=ng_tags,
                opts=pulumi.ResourceOptions(parent=self, depends_on=nat_eip),
            )
            if egress_via_nat_gateway:
                subnet_ng_route = aws.ec2.Route(
                    f'{name}-ngroute',
                    route_table_id=private_route_table.id,
                    destination_cidr_block='0.0.0.0/0',
                    gateway_id=nat_gateway.id,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc, nat_gateway]),
                )

        # If we have to build endpoints, we have to have a security group to let local traffic in
        if len(endpoint_interfaces + endpoint_gateways) > 0:
            endpoint_sg = tb_pulumi.network.SecurityGroupWithRules(
                f'{name}-endpoint-sg',
                project,
                vpc_id=vpc.id,
                rules={
                    'ingress': [
                        {
                            'cidr_blocks': [cidr_block],
                            'description': 'Allow VPC access to endpoint-fronted AWS services',
                            'protocol': 'TCP',
                            'from_port': 443,
                            'to_port': 443,
                        }
                    ],
                    'egress': [
                        {
                            'cidr_blocks': ['0.0.0.0/0'],
                            'description': 'Allow all TCP egress',
                            'protocol': 'TCP',
                            'from_port': 0,
                            'to_port': 65535,
                        }
                    ],
                },
                opts=pulumi.ResourceOptions(parent=self),
                tags=self.tags,
            )

        interfaces = []
        for svc in endpoint_interfaces:
            interfaces.append(
                aws.ec2.VpcEndpoint(
                    f'{name}-interface-{svc}',
                    private_dns_enabled=True,
                    service_name=f'com.amazonaws.{self.project.aws_region}.{svc}',
                    security_group_ids=[endpoint_sg.resources['sg'].id],
                    subnet_ids=[subnet.id for subnet in public_subnet_rs],
                    vpc_endpoint_type='Interface',
                    vpc_id=vpc.id,
                    tags=self.tags,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[*public_subnet_rs, *private_subnet_rs, endpoint_sg.resources['sg']]),
                )
            )

        gateways = []
        for svc in endpoint_gateways:
            gateways.append(
                aws.ec2.VpcEndpoint(
                    f'{name}-gateway-{svc}',
                    route_table_ids=[vpc.default_route_table_id, private_route_table.id],
                    service_name=f'com.amazonaws.{self.project.aws_region}.{svc}',
                    vpc_endpoint_type='Gateway',
                    vpc_id=vpc.id,
                    tags=self.tags,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[*public_subnet_rs, *private_subnet_rs, endpoint_sg.resources['sg']]),
                )
            )

        self.finish(
            outputs={
                'public_subnets': [subnet.id for subnet in public_subnet_rs],
                'private_subnets': [subnet.id for subnet in private_subnet_rs],
                'vpc': vpc.id,
            },
            resources={
                'endpoint_sg': endpoint_sg if len(endpoint_interfaces + endpoint_gateways) > 0 else None,
                'gateways': gateways,
                'interfaces': interfaces,
                'internet_gateway': internet_gateway if enable_internet_gateway else None,
                'nat_eip': nat_eip if enable_nat_gateway else None,
                'nat_gateway': nat_gateway if enable_nat_gateway else None,
                'public_route_table_subnet_associations': public_route_table_subnet_associations,
                'public_subnets': public_subnet_rs,
                'private_route_table_subnet_associations': private_route_table_subnet_associations,
                'private_subnets': private_subnet_rs,
                'subnet_ig_route': subnet_ig_route if enable_internet_gateway and egress_via_internet_gateway else None,
                'subnet_ng_route': subnet_ng_route if enable_nat_gateway and egress_via_nat_gateway else None,
                'vpc': vpc,
            },
        )


class SecurityGroupWithRules(tb_pulumi.ThunderbirdComponentResource):
    """Builds a security group and sets rules for it.

    :param name: A string identifying this set of resources.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param rules: A dict describing in/egress rules of the following construction:
        ::

            {
                'ingress': [{
                    # Valid inputs to the SecurityGroupRule resource go here. Ref:
                    # https://www.pulumi.com/registry/packages/aws/api-docs/ec2/securitygrouprule/#inputs
                }],
                'egress': [{
                    # The same inputs are valid here
                }]
            }

        Defaults to {}.
    :type rules: dict, optional

    :param vpc_id: ID of the VPC this security group should belong to. When not set, defaults to the region's default
        VPC. Defaults to None.
    :type vpc_id: str, optional

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param kwargs: Any other keyword arguments which will be passed as inputs to the ThunderbirdComponentResource
        superconstructor.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        rules: dict = {},
        vpc_id: str = None,
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        """ """

        super().__init__('tb:network:SecurityGroupWithRules', name, project, opts=opts, **kwargs)

        # Build a security group in the provided VPC
        sg = aws.ec2.SecurityGroup(
            f'{name}-sg',
            opts=pulumi.ResourceOptions(parent=self),
            name=name,
            description=f'Send Suite backend security group ({self.project.stack})',
            vpc_id=vpc_id,
            tags=self.tags,
        )

        # Set up security group rules for that SG
        ingress_rules = []
        egress_rules = []

        if 'ingress' in rules:
          ingress_ruledefs = rules['ingress']
          for idx, rule in enumerate(ingress_ruledefs):
              rule.update({'type': 'ingress', 'security_group_id': sg.id})
              ingress_rules.append(
                  aws.ec2.SecurityGroupRule(
                      f'{name}-ingress-{rule['to_port']}-{idx}',
                      opts=pulumi.ResourceOptions(parent=self, depends_on=[sg]),
                      **rule,
                  )
              )

        if 'egress' in rules:
          egress_ruledefs = rules['egress']
          for idx, rule in enumerate(egress_ruledefs):
              rule.update({'type': 'egress', 'security_group_id': sg.id})
              egress_rules.append(
                  aws.ec2.SecurityGroupRule(
                      f'{name}-egress-{rule['to_port']}-{idx}',
                      opts=pulumi.ResourceOptions(parent=self, depends_on=[sg]),
                      **rule,
                  )
              )

        self.finish(
            outputs={'sg': sg.id},
            resources={
                'egress_rules': egress_rules,
                'ingress_rules': ingress_rules,
                'sg': sg,
            },
        )

class SecurityGroup(tb_pulumi.ThunderbirdComponentResource):
    """Builds a security group with no attached rules.

    :param name: A string identifying this resource.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param vpc_id: ID of the VPC this security group should belong to. When not set, defaults to the region's default
        VPC. Defaults to None.
    :type vpc_id: str, optional

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param kwargs: Any other keyword arguments which will be passed as inputs to the ThunderbirdComponentResource
        superconstructor.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        vpc_id: str = None,
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        """ """

        super().__init__('tb:network:SecurityGroup', name, project, opts=opts, **kwargs)

        # Build a security group in the provided VPC
        sg = aws.ec2.SecurityGroup(
            f'{name}',
            opts=pulumi.ResourceOptions(parent=self),
            name=name,
            description=f'Send Suite backend security group ({self.project.stack})',
            vpc_id=vpc_id,
            tags=self.tags,
        )

        self.finish(
            outputs={'sg': self.id},
            resources={'sg': sg},
        )

class SecurityGroupRule(tb_pulumi.ThunderbirdComponentResource):
    """Builds a security group rule and attaches it to an existing security group.

    :param name: A string identifying this resource.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param config: A dict describing rule config of the following construction:
        ::

            {
              # Valid inputs to the SecurityGroupRule resource go here. Ref:
              # https://www.pulumi.com/registry/packages/aws/api-docs/ec2/securitygrouprule/#inputs
            }

        Defaults to {}.
    :type config: dict, optional

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param kwargs: Any other keyword arguments which will be passed as inputs to the ThunderbirdComponentResource
        superconstructor.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        config: dict = {},
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        """ """

        super().__init__('tb:network:SecurityGroupRule', name, project, opts=opts, **kwargs)

        rule = aws.ec2.SecurityGroupRule(
            f'{name}-{config['type']}-{config['to_port']}',
            opts=pulumi.ResourceOptions(parent=self),
            **config,
        )

        self.finish(
            outputs={'id': rule.id},
            resources={'rule': self},
        )
