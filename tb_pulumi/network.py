"""Infrastructural patterns related to networking."""

import pulumi
import pulumi_aws as aws
import tb_pulumi

from copy import deepcopy


class MultiCidrVpc(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:network:MultiCidrVpc``

    Builds a VPC with configurable network space.

    Produces the following ``resources``:

        - *endpoint_sg* - If the ``endpoint_interfaces`` or ``endpoint_gateways`` parameters are provided, this is a
          :py:class:`tb_pulumi.network.SecurityGroupWithRules` used to define traffic through these endpoints.
        - *gateways* - If there are any ``endpoint_gateways`` defined, this is a list of `aws.ec2.VpcEndpoints
          <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/vpcendpoint/>`_ with a ``vpc_endpoint_type`` of
          ``Gateway``.
        - *interfaces* - If there are any ``endpoint_interfaces`` defined, this is a list of `aws.ec2.VpcEndpoints
          <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/vpcendpoint/>`_ with a ``vpc_endpoint_type`` of
          ``Interface``.
        - *internet_gateway* - If ``enable_internet_gateway`` is ``True``, this is the `aws.ec2.InternetGateway
          <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/internetgateway/>`_.
        - *nat_eip* - If ``enable_nat_gateway`` is ``True``, this is the `aws.ec2.Eip
          <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/eip/>`_ used for the NAT Gateway.
        - *nat_gateway* - If ``enable_nat_gateway`` is ``True``, this is the `aws.ec2.NatGateway
          <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/natgateway/>`_.
        - *peering_accepters* - Dict of `aws.ec2.VpcPeeringConnectionAcceptors
          <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/vpcpeeringconnectionaccepter/>`_.
        - *peering_connections* - Dict of `aws.ec2.VpcPeeringConnections
          <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/vpcpeeringconnection/>`_.
        - *routes* - List of all `aws.ec2.Routes <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/route/>`_ in
          the route table.
        - *route_table_subnet_associations* - List of `aws.ec2.RouteTableAssociations
          <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/routetableassociation/>`_ associating the subnets
          to the VPC's default route table, enabling traffic among those subnets.
        - *subnets* - List of `aws.ec2.Subnets <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/subnet/>`_ in
          this VPC.
        - *subnet_ig_route* - If ``enable_internet_gateway`` and ``egress_via_internet_gateway`` are both ``True``,
          this is the `aws.ec2.Route <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/route/>`_ that enables
          outbound traffic through the Internet Gateway.
        - *subnet_ng_route* - If ``enable_nat_gateway`` and ``egress_via_nat_gateway`` are both ``True``, this is the
          `aws.ec2.Route <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/route/>`_ that enables outbound
          traffic through the NAT Gateway.
        - *vpc* - The `aws.ec2.Vpc <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/vpc/>`_.

    :param name: A string identifying this set of resources.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param additional_routes: Many of the routes that wind up in the main route table are generated automatically due
        to necessity with endpoints, peered VPCs,e tc. If you need to define any additional routes beyond those, you can
        do so here, using docs for `aws.ec2.Route <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/route/>`_.
        The ``route_table_id`` parameter will be populated for you automatically.
    :type additional_routes: list[dict]

    :param cidr_block: A CIDR describing the IP space of this VPC. Defaults to '10.0.0.0/16'.
    :type cidr_block: str, optional

    :param egress_via_internet_gateway: When True, establish an outbound route to the Internet via the Internet
        Gateway. Requires ``enable_internet_gateway=True``. Conflicts with ``egress_via_nat_gateway=True``.
        Defaults to False.
    :type egress_via_internet_gateway: bool, optional

    :param egress_via_nat_gateway: When True, establish an outbound route to the Internet via the NAT Gateway.
        Requires ``enable_nat_gateway=True``. Conflicts with ``egress_via_internet_gateway=True``. Defaults to
        False.
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


    :param peering_connections: Dict of configurations of `aws.ec2.VpcPeeringConnections
        <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/vpcpeeringconnection/>`_. The keys become the names
        of the resources created. The vpc_id option will be automatically populated.

    :param peering_accepters: Dict of configurations of `aws.ec2.VpcPeeringConnectionAccepters
        <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/vpcpeeringconnectionaccepter/>`_. The keys become the
        names of the resources created. The vpc_id option will be automatically populated.
    :type peering_accepters: list[dict]

    :param subnets: A dict where the keys are the names of AWS Availability Zones in which to build subnets and the
        values are lists of CIDRs describing valid subsets of IPs in the VPC ``cidr_block`` to build in that AZ.
        f/ex:
        ::

            { 'us-east-1': ['10.0.100.0/24'],
              'us-east-2': ['10.0.101.0/24', '10.0.102.0/24'] }

        Defaults to {}.
    :type subnets: dict, optional

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param kwargs: Any other keyword arguments which will be passed as inputs to the ThunderbirdComponentResource
        superconstructor.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        additional_routes: list[dict] = {},
        cidr_block: str = '10.0.0.0/16',
        egress_via_internet_gateway: bool = False,
        egress_via_nat_gateway: bool = False,
        enable_dns_hostnames: bool = None,
        enable_internet_gateway: bool = False,
        enable_nat_gateway: bool = False,
        endpoint_gateways: list[str] = [],
        endpoint_interfaces: list[str] = [],
        peering_connections: dict = {},
        peering_accepters: dict = {},
        subnets: dict = {},
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

        # Build subnets in that VPC
        subnet_rs = []
        for idx, subnet in enumerate(subnets.items()):
            az, cidrs = subnet
            for cidr in cidrs:
                subnet_resname = f'{name}-subnet-{idx}'
                subnet_tags = {'Name': subnet_resname}
                subnet_tags.update(self.tags)
                subnet_rs.append(
                    aws.ec2.Subnet(
                        subnet_resname,
                        availability_zone=az,
                        cidr_block=cidr,
                        tags=subnet_tags,
                        vpc_id=vpc.id,
                        opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc]),
                    )
                )

        # Associate the VPC's default route table to all of the subnets
        route_table_subnet_associations = []
        for idx, subnet in enumerate(subnet_rs):
            route_table_subnet_associations.append(
                aws.ec2.RouteTableAssociation(
                    f'{name}-subnetassoc-{idx}',
                    route_table_id=vpc.default_route_table_id,
                    subnet_id=subnet.id,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[subnet, vpc]),
                )
            )

        # Allow traffic in from the internet
        if enable_internet_gateway:
            ig_tags = {'Name': name}
            ig_tags.update(self.tags)
            internet_gateway = aws.ec2.InternetGateway(
                f'{name}-ig',
                vpc_id=vpc.id,
                tags=ig_tags,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc]),
            )

            subnet_ig_route = (
                aws.ec2.Route(
                    f'{name}-igroute',
                    route_table_id=vpc.default_route_table_id,
                    destination_cidr_block='0.0.0.0/0',
                    gateway_id=internet_gateway.id,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc, internet_gateway]),
                )
                if egress_via_internet_gateway
                else None
            )

        if enable_nat_gateway:
            nat_eip = aws.ec2.Eip(
                f'{name}-eip',
                domain='vpc',
                public_ipv4_pool='amazon',
                network_border_group=self.project.aws_region,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc]),
                tags=self.tags,
            )
            ng_tags = {'Name': name}
            ng_tags.update(self.tags)
            nat_gateway = aws.ec2.NatGateway(
                f'{name}-nat',
                allocation_id=nat_eip.allocation_id,
                subnet_id=subnets[0].id,
                tags=ng_tags,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[nat_eip, subnets[0]]),
            )
            subnet_ng_route = (
                aws.ec2.Route(
                    f'{name}-ngroute',
                    route_table_id=vpc.default_route_table_id,
                    destination_cidr_block='0.0.0.0/0',
                    gateway_id=nat_gateway.id,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc, nat_gateway]),
                )
                if egress_via_nat_gateway
                else None
            )

        # If we have to build endpoints, we have to have a security group to let local traffic in
        if len(endpoint_interfaces + endpoint_gateways) > 0:
            endpoint_sg = tb_pulumi.network.SecurityGroupWithRules(
                f'{name}-endpoint-sg',
                project,
                vpc_id=vpc.id,
                exclude_from_project=True,
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
                opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc]),
                tags=self.tags,
            )

        interfaces = []
        for svc in endpoint_interfaces:
            tags = deepcopy(self.tags)
            tags['Name'] = f'{project.name_prefix}-{svc}'
            interfaces.append(
                aws.ec2.VpcEndpoint(
                    f'{name}-interface-{svc}',
                    private_dns_enabled=True,
                    service_name=f'com.amazonaws.{self.project.aws_region}.{svc}',
                    security_group_ids=[endpoint_sg.resources['sg'].id],
                    subnet_ids=[subnet.id for subnet in subnet_rs],
                    vpc_endpoint_type='Interface',
                    vpc_id=vpc.id,
                    tags=tags,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc, *subnet_rs, endpoint_sg.resources['sg']]),
                )
            )

        gateways = []
        for svc in endpoint_gateways:
            tags = deepcopy(self.tags)
            tags['Name'] = f'{project.name_prefix}-{svc}'
            gateways.append(
                aws.ec2.VpcEndpoint(
                    f'{name}-gateway-{svc}',
                    route_table_ids=[vpc.default_route_table_id],
                    service_name=f'com.amazonaws.{self.project.aws_region}.{svc}',
                    vpc_endpoint_type='Gateway',
                    vpc_id=vpc.id,
                    tags=tags,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc, *subnet_rs, endpoint_sg.resources['sg']]),
                )
            )

        # Set up VPC peering. Peering the VPCs is not enough to enable network traffic. You must also create a route.
        peer_conns = {}
        peer_conn_routes = {}
        for peer_name, connection in peering_connections.items():
            peered_cidrs = connection.pop('peered_cidrs', {})
            tags = self.tags.copy()
            tags.update({'Name': f'{project.name_prefix}-to-{peer_name}'})
            peer_conns[peer_name] = aws.ec2.VpcPeeringConnection(
                f'{name}-peerconn-{peer_name}',
                vpc_id=vpc.id,
                tags=tags,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc]),
                **connection,
            )
            peer_conn_routes[peer_name] = [
                aws.ec2.Route(
                    f'{name}-pcxroute-{peer_name}-{idx}',
                    destination_cidr_block=cidr,
                    route_table_id=vpc.default_route_table_id,
                    vpc_peering_connection_id=peer_conns[peer_name].id,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc, peer_conns[peer_name]]),
                )
                for idx, cidr in enumerate(peered_cidrs)
            ]

        peer_accs = {}
        peer_acc_routes = {}
        for peer_name, accepter in peering_accepters.items():
            peered_cidrs = accepter.pop('peered_cidrs', {})
            peer_accs[peer_name] = aws.ec2.VpcPeeringConnectionAccepter(
                f'{name}-peeracc-{peer_name}',
                tags=self.tags,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc]),
                **accepter,
            )
            peer_acc_routes[peer_name] = [
                aws.ec2.Route(
                    f'{name}-pacroute-{idx}',
                    destination_cidr_block=cidr,
                    route_table_id=vpc.default_route_table_id,
                    vpc_peering_connection_id=peer_accs[peer_name].id,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc, peer_accs[peer_name]]),
                )
                for idx, cidr in enumerate(peered_cidrs)
            ]

        additional_routes = [
            aws.ec2.Route(
                f'{name}-route-{idx}',
                route_table_id=vpc.default_route_table_id,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc]),
                **route,
            )
            for idx, route in enumerate(additional_routes)
        ]

        # Combine all routes we've created into one list; remove any optional routes which are disabled/None
        routes = [
            route
            for route in [
                subnet_ig_route if enable_internet_gateway else None,
                subnet_ng_route if enable_nat_gateway else None,
                *peer_conn_routes.values(),
                *peer_acc_routes.values(),
                *additional_routes,
            ]
            if route is not None
        ]

        self.finish(
            resources={
                'endpoint_sg': endpoint_sg if len(endpoint_interfaces + endpoint_gateways) > 0 else None,
                'gateways': gateways,
                'interfaces': interfaces,
                'internet_gateway': internet_gateway if enable_internet_gateway else None,
                'nat_eip': nat_eip if enable_nat_gateway else None,
                'nat_gateway': nat_gateway if enable_nat_gateway else None,
                'peering_acceptors': peer_accs,
                'peering_connections': peer_conns,
                'routes': routes,
                'route_table_subnet_associations': route_table_subnet_associations,
                'subnets': subnet_rs,
                'subnet_ig_route': subnet_ig_route if enable_internet_gateway and egress_via_internet_gateway else None,
                'subnet_ng_route': subnet_ng_route if enable_nat_gateway and egress_via_nat_gateway else None,
                'vpc': vpc,
            },
        )


class MultiTierVpc(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:network:MultiTierVpc``

    Builds a VPC with configurable network space broken across multiple private and public subnets.

    Produces the following ``resources``:

        - *endpoint_sg* - If the ``endpoint_interfaces`` or ``endpoint_gateways`` parameters are provided, this is a
          :py:class:`tb_pulumi.network.SecurityGroupWithRules` used to define traffic through these endpoints.
        - *gateways* - If there are any ``endpoint_gateways`` defined, this is a list of `aws.ec2.VpcEndpoints
          <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/vpcendpoint/>`_ with a ``vpc_endpoint_type`` of
          ``Gateway``.
        - *interfaces* - If there are any ``endpoint_interfaces`` defined, this is a list of `aws.ec2.VpcEndpoints
          <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/vpcendpoint/>`_ with a ``vpc_endpoint_type`` of
          ``Interface``.
        - *internet_gateway* - If ``enable_internet_gateway`` is ``True``, this is the `aws.ec2.InternetGateway
          <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/internetgateway/>`_.
        - *nat_eip* - If ``enable_nat_gateway`` is ``True``, this is the `aws.ec2.Eip
          <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/eip/>`_ used for the NAT Gateway.
        - *nat_gateway* - If ``enable_nat_gateway`` is ``True``, this is the `aws.ec2.NatGateway
          <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/natgateway/>`_.
        - *peering_accepters* - Dict of `aws.ec2.VpcPeeringConnectionAcceptors
          <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/vpcpeeringconnectionaccepter/>`_.
        - *peering_connections* - Dict of `aws.ec2.VpcPeeringConnections
          <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/vpcpeeringconnection/>`_.
        - *routes* - List of all `aws.ec2.Routes <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/route/>`_ in
          the route table.
        - *route_table_subnet_associations* - List of `aws.ec2.RouteTableAssociations
          <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/routetableassociation/>`_ associating the subnets
          to the VPC's default route table, enabling traffic among those subnets.
        - *private_subnets* - List of private `aws.ec2.Subnets <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/subnet/>`_ in
          this VPC.
        - *public_subnets* - List of public `aws.ec2.Subnets <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/subnet/>`_ in
          this VPC.
        - *subnet_ig_route* - If ``enable_internet_gateway`` and ``egress_via_internet_gateway`` are both ``True``,
          this is the `aws.ec2.Route <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/route/>`_ that enables
          outbound traffic through the Internet Gateway.
        - *subnet_ng_route* - If ``enable_nat_gateway`` and ``egress_via_nat_gateway`` are both ``True``, this is the
          `aws.ec2.Route <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/route/>`_ that enables outbound
          traffic through the NAT Gateway.
        - *vpc* - The `aws.ec2.Vpc <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/vpc/>`_.

    :param name: A string identifying this set of resources.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param additional_routes: Many of the routes that wind up in the main route table are generated automatically due
        to necessity with endpoints, peered VPCs,e tc. If you need to define any additional routes beyond those, you can
        do so here, using docs for `aws.ec2.Route <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/route/>`_.
        The ``route_table_id`` parameter will be populated for you automatically.
    :type additional_routes: list[dict]

    :param cidr_block: A CIDR describing the IP space of this VPC. Defaults to '10.0.0.0/16'.
    :type cidr_block: str, optional

    :param egress_via_internet_gateway: When True, establish an outbound route to the Internet via the Internet
        Gateway. Requires ``enable_internet_gateway=True``. Conflicts with ``egress_via_nat_gateway=True``.
        Defaults to False.
    :type egress_via_internet_gateway: bool, optional

    :param egress_via_nat_gateway: When True, establish an outbound route to the Internet via the NAT Gateway.
        Requires ``enable_nat_gateway=True``. Conflicts with ``egress_via_internet_gateway=True``. Defaults to
        False.
    :type egress_via_nat_gateway: bool, optional

    :param enable_dns_hostnames: When True, internal DNS mappings get built for IPs assigned within the VPC. This is
        required for the use of certain other services like load-balanced Fargate clusters. Defaults to None.
    :type enable_dns_hostnames: bool, optional

    :param enable_internet_gateway: Build an IGW will to allow traffic outbond to the Internet. Defaults to False.
    :type enable_internet_gateway: bool, optional

    :param enable_nat_gateway: Build a NAT Gateway to route inbound traffic. Defaults to False.
    :type enable_nat_gateway: bool, optional

    :param nat_gateway_allocation_id: If you want to use an existing EIP for the NAT Gateway, provide its allocation
        ID here. If not provided, a new EIP will be created. Defaults to None.
    :type nat_gateway_allocation_id: str, optional

    :param nat_gateway_secondary_allocation_ids: A list of allocation IDs of existing EIPs to associate as secondary
        IPs for the NAT Gateway. A maximum of 7 secondary EIPs can be associated with a NAT Gateway. Defaults to None.
    :type nat_gateway_secondary_allocation_ids: list[str], optional

    :param endpoint_gateways: List of public-facing AWS services (such as S3) to create VPC gateways to. Defaults to
        [].
    :type endpoint_gateways: list[str], optional

    :param endpoint_interfaces: List of AWS services to create VPC Interface endpoints for. These must match service
        names listed `here
        <https://docs.aws.amazon.com/vpc/latest/privatelink/aws-services-privatelink-support.html>`_ **Do not** list
        the full qualifying name, only the service name portion. f/ex, do not use
        ``com.amazonaws.us-east-1.secretsmanager``, only use ``secretsmanager``. Defaults to [].
    :type endpoint_interfaces: list[str], optional


    :param peering_connections: Dict of configurations of `aws.ec2.VpcPeeringConnections
        <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/vpcpeeringconnection/>`_. The keys become the names
        of the resources created. The vpc_id option will be automatically populated.

    :param peering_accepters: Dict of configurations of `aws.ec2.VpcPeeringConnectionAccepters
        <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/vpcpeeringconnectionaccepter/>`_. The keys become the
        names of the resources created. The vpc_id option will be automatically populated.
    :type peering_accepters: list[dict]

    :param subnets: A dict where the keys are the names of AWS Availability Zones in which to build subnets and the
        values are lists of CIDRs describing valid subsets of IPs in the VPC ``cidr_block`` to build in that AZ.
        f/ex:
        ::

            { 'us-east-1': ['10.0.100.0/24'],
              'us-east-2': ['10.0.101.0/24', '10.0.102.0/24'] }

        Defaults to {}.
    :type subnets: dict, optional

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param kwargs: Any other keyword arguments which will be passed as inputs to the ThunderbirdComponentResource
        superconstructor.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        additional_routes: list[dict] = {},
        cidr_block: str = '10.0.0.0/16',
        egress_via_internet_gateway: bool = False,
        egress_via_nat_gateway: bool = False,
        enable_dns_hostnames: bool = None,
        enable_internet_gateway: bool = False,
        enable_nat_gateway: bool = False,
        nat_gateway_allocation_id: str = None,
        nat_gateway_secondary_allocation_ids: list[str] = None,
        endpoint_gateways: list[str] = [],
        endpoint_interfaces: list[str] = [],
        peering_connections: dict = {},
        peering_accepters: dict = {},
        private_subnets: dict = {},
        public_subnets: dict = {},
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

        # build public subnets in that VPC
        public_subnet_rs = []
        for idx, subnet in enumerate(public_subnets.items()):
            az, cidrs = subnet
            for cidr in cidrs:
                public_subnet_resname = f'{name}-subnet-public-{idx}'
                public_subnet_tags = {'Name': public_subnet_resname, 'Tier': 'Public'}
                public_subnet_tags.update(self.tags)
                public_subnet_rs.append(
                    aws.ec2.Subnet(
                        public_subnet_resname,
                        availability_zone=az,
                        cidr_block=cidr,
                        map_public_ip_on_launch=True,
                        tags=public_subnet_tags,
                        vpc_id=vpc.id,
                        opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc]),
                    )
                )

        # Build private subnets in VPC
        private_subnet_rs = []
        for idx, subnet in enumerate(private_subnets.items()):
            az, cidrs = subnet
            for cidr in cidrs:
                private_subnet_resname = f'{name}-private_subnet-{idx}'
                private_subnet_tags = {'Name': private_subnet_resname, 'Tier': 'Private'}
                private_subnet_tags.update(self.tags)
                private_subnet_rs.append(
                    aws.ec2.Subnet(
                        private_subnet_resname,
                        availability_zone=az,
                        cidr_block=cidr,
                        tags=private_subnet_tags,
                        map_public_ip_on_launch=False,
                        vpc_id=vpc.id,
                        opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc]),
                    )
                )

        # Associate the VPC's default route table to all of the public subnets
        # route_table_subnet_associations = []
        # all_subnet_rs = public_subnet_rs
        # for idx, subnet in enumerate(public_subnet_rs):
        #     route_table_subnet_associations.append(
        #         aws.ec2.RouteTableAssociation(
        #             f'{name}-subnetassoc-{idx}',
        #             route_table_id=vpc.default_route_table_id,
        #             subnet_id=subnet.id,
        #             opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc]),
        #         )
        #     )

        # Allow traffic in from the internet
        if enable_internet_gateway:
            ig_tags = {'Name': name}
            ig_tags.update(self.tags)
            internet_gateway = aws.ec2.InternetGateway(
                f'{name}-ig',
                vpc_id=vpc.id,
                tags=ig_tags,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc]),
            )

            # create public_route_table
            public_route_table = (
                aws.ec2.RouteTable(
                    f'{name}-public-rt',
                    vpc_id=vpc.id,
                    routes=[
                        {
                            'cidr_block': '0.0.0.0/0',
                            'gateway_id': internet_gateway.id,
                        }
                    ],
                    tags={'Name': f'{name}-public-rt', **self.tags},
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc, internet_gateway]),
                )
                if egress_via_internet_gateway
                else None
            )

            # subnet_ig_route = (
            #     aws.ec2.Route(
            #         f'{name}-igroute',
            #         route_table_id=public_route_table.id,
            #         destination_cidr_block='0.0.0.0/0',
            #         gateway_id=internet_gateway.id,
            #         opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc, internet_gateway, public_route_table]),
            #     )
            #     if egress_via_internet_gateway
            #     else None
            # )
            # Associate the VPC's default route table to all of the public subnets
            public_route_table_subnet_associations = []
            if egress_via_internet_gateway:
                for idx, subnet in enumerate(public_subnet_rs):
                    public_route_table_subnet_associations.append(
                        aws.ec2.RouteTableAssociation(
                            f'{name}-public-subnetassoc-{idx}',
                            route_table_id=public_route_table.id,
                            subnet_id=subnet.id,
                            opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc, public_route_table]),
                        )
                    )

        if enable_nat_gateway:
            # create EIP for NAT Gateway if not specified
            if not nat_gateway_allocation_id:
                nat_eip = aws.ec2.Eip(
                    f'{name}-eip',
                    domain='vpc',
                    public_ipv4_pool='amazon',
                    network_border_group=self.project.aws_region,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc]),
                    tags=self.tags,
                )
            else:
                # get allocation id of specified EIP instead of creating a new one
                nat_eip = aws.ec2.Eip.get(
                    f'{name}-eip',
                    id=nat_gateway_allocation_id,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc]),
                )
            # if nat_gateway_secondary_allocation_ids is provided, use them as secondary EIPs for the NAT Gateway
            if nat_gateway_secondary_allocation_ids:
                if len(nat_gateway_secondary_allocation_ids) > 7:
                    raise ValueError('A maximum of 7 secondary EIPs can be associated with a NAT Gateway.')
            ng_tags = {'Name': name}
            ng_tags.update(self.tags)
            nat_gateway = aws.ec2.NatGateway(
                f'{name}-nat',
                allocation_id=nat_eip.allocation_id,
                secondary_allocation_ids=nat_gateway_secondary_allocation_ids,
                subnet_id=public_subnet_rs[0].id,
                tags=ng_tags,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[nat_eip, public_subnet_rs[0]]),
            )
            # create private_subnet_route_table
            private_route_table = (
                aws.ec2.RouteTable(
                    f'{name}-private-rt',
                    vpc_id=vpc.id,
                    routes=[
                        {
                            'cidr_block': '0.0.0.0/0',
                            'gateway_id': nat_gateway.id,
                        }
                    ],
                    tags={'Name': f'{name}-private-rt', **self.tags},
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc, nat_gateway]),
                )
                if egress_via_nat_gateway
                else None
            )
            # private_subnet_ng_route = (
            #     aws.ec2.Route(
            #         f'{name}-ngroute',
            #         route_table_id=private_route_table.id,
            #         destination_cidr_block='0.0.0.0/0',
            #         gateway_id=nat_gateway.id,
            #         opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc, nat_gateway, private_route_table]),
            #     )
            #     if egress_via_nat_gateway
            #     else None
            # )

            # associate private subnets with private route table
            private_route_table_subnet_associations = []
            if egress_via_nat_gateway:
                for idx, subnet in enumerate(private_subnet_rs):
                    private_route_table_subnet_associations.append(
                        aws.ec2.RouteTableAssociation(
                            f'{name}-private-subnetassoc-{idx}',
                            route_table_id=private_route_table.id,
                            subnet_id=subnet.id,
                            opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc, private_route_table]),
                        )
                    )

        # If we have to build endpoints, we have to have a security group to let local traffic in
        if len(endpoint_interfaces + endpoint_gateways) > 0:
            endpoint_sg = tb_pulumi.network.SecurityGroupWithRules(
                f'{name}-endpoint-sg',
                project,
                vpc_id=vpc.id,
                exclude_from_project=True,
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
                opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc]),
                tags=self.tags,
            )

        interfaces = []
        for svc in endpoint_interfaces:
            tags = deepcopy(self.tags)
            tags['Name'] = f'{project.name_prefix}-{svc}'
            interfaces.append(
                aws.ec2.VpcEndpoint(
                    f'{name}-interface-{svc}',
                    private_dns_enabled=True,
                    service_name=f'com.amazonaws.{self.project.aws_region}.{svc}',
                    security_group_ids=[endpoint_sg.resources['sg'].id],
                    subnet_ids=[subnet.id for subnet in subnet_rs],
                    vpc_endpoint_type='Interface',
                    vpc_id=vpc.id,
                    tags=tags,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc, *subnet_rs, endpoint_sg.resources['sg']]),
                )
            )

        gateways = []
        for svc in endpoint_gateways:
            tags = deepcopy(self.tags)
            tags['Name'] = f'{project.name_prefix}-{svc}'
            gateways.append(
                aws.ec2.VpcEndpoint(
                    f'{name}-gateway-{svc}',
                    route_table_ids=[vpc.default_route_table_id],
                    service_name=f'com.amazonaws.{self.project.aws_region}.{svc}',
                    vpc_endpoint_type='Gateway',
                    vpc_id=vpc.id,
                    tags=tags,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc, *subnet_rs, endpoint_sg.resources['sg']]),
                )
            )

        # Set up VPC peering. Peering the VPCs is not enough to enable network traffic. You must also create a route.
        peer_conns = {}
        peer_conn_routes = {}
        for peer_name, connection in peering_connections.items():
            peered_cidrs = connection.pop('peered_cidrs', {})
            tags = self.tags.copy()
            tags.update({'Name': f'{project.name_prefix}-to-{peer_name}'})
            peer_conns[peer_name] = aws.ec2.VpcPeeringConnection(
                f'{name}-peerconn-{peer_name}',
                vpc_id=vpc.id,
                tags=tags,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc]),
                **connection,
            )
            peer_conn_routes[peer_name] = [
                aws.ec2.Route(
                    f'{name}-pcxroute-{peer_name}-{idx}',
                    destination_cidr_block=cidr,
                    route_table_id=vpc.default_route_table_id,
                    vpc_peering_connection_id=peer_conns[peer_name].id,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc, peer_conns[peer_name]]),
                )
                for idx, cidr in enumerate(peered_cidrs)
            ]

        peer_accs = {}
        peer_acc_routes = {}
        for peer_name, accepter in peering_accepters.items():
            peered_cidrs = accepter.pop('peered_cidrs', {})
            peer_accs[peer_name] = aws.ec2.VpcPeeringConnectionAccepter(
                f'{name}-peeracc-{peer_name}',
                tags=self.tags,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc]),
                **accepter,
            )
            peer_acc_routes[peer_name] = [
                aws.ec2.Route(
                    f'{name}-pacroute-{idx}',
                    destination_cidr_block=cidr,
                    route_table_id=vpc.default_route_table_id,
                    vpc_peering_connection_id=peer_accs[peer_name].id,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc, peer_accs[peer_name]]),
                )
                for idx, cidr in enumerate(peered_cidrs)
            ]

        additional_routes = [
            aws.ec2.Route(
                f'{name}-route-{idx}',
                route_table_id=vpc.default_route_table_id,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[vpc]),
                **route,
            )
            for idx, route in enumerate(additional_routes)
        ]

        # Combine all routes we've created into one list; remove any optional routes which are disabled/None
        routes = [
            route
            for route in [
                # subnet_ig_route if enable_internet_gateway else None,
                # private_subnet_ng_route if enable_nat_gateway else None,
                *peer_conn_routes.values(),
                *peer_acc_routes.values(),
                *additional_routes,
            ]
            if route is not None
        ]

        self.finish(
            resources={
                'endpoint_sg': endpoint_sg if len(endpoint_interfaces + endpoint_gateways) > 0 else None,
                'gateways': gateways,
                'interfaces': interfaces,
                'internet_gateway': internet_gateway if enable_internet_gateway else None,
                'nat_eip': nat_eip if enable_nat_gateway else None,
                'nat_gateway': nat_gateway if enable_nat_gateway else None,
                'peering_acceptors': peer_accs,
                'peering_connections': peer_conns,
                'routes': routes,
                'public_route_table_subnet_associations': public_route_table_subnet_associations
                if egress_via_internet_gateway
                else None,
                'private_route_table_subnet_associations': private_route_table_subnet_associations
                if egress_via_nat_gateway
                else None,
                'private_subnets': private_subnet_rs,
                'public_subnets': public_subnet_rs,
                # 'subnet_ig_route': subnet_ig_route if enable_internet_gateway and egress_via_internet_gateway else None,
                # 'private_subnet_ng_route': private_subnet_ng_route if enable_nat_gateway and egress_via_nat_gateway else None,
                'vpc': vpc,
            },
        )


class SecurityGroupWithRules(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:network:SecurityGroupWithRules``

    Builds a security group and sets rules for it.

    Produces the following ``resources``:

        - *egress_rules* - List of `aws.ec2.SecurityGroupRules
          <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/securitygrouprule/>`_ describing outbound traffic.
        - *ingress_rules* - List of `aws.ec2.SecurityGroupRules
          <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/securitygrouprule/>`_ describing inbound traffic.
        - *sg* - The `aws.ec2.SecurityGroup <https://www.pulumi.com/registry/packages/aws/api-docs/ec2/securitygroup/>`_
          containing these rules.

    :param name: A string identifying this set of resources.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param description: Description of the security group
    :type description: str

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
        description: str = None,
        rules: dict = {},
        vpc_id: str = None,
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        super().__init__('tb:network:SecurityGroupWithRules', name, project, opts=opts, **kwargs)

        # Build a security group in the provided VPC
        sg_tags = {'Name': name}
        sg_tags.update(self.tags)
        sg = aws.ec2.SecurityGroup(
            f'{name}-sg',
            name=name,
            description=description,
            vpc_id=vpc_id,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Set up security group rules for that SG
        ingress_rules = []
        egress_rules = []

        ingress_ruledefs = rules['ingress']
        for idx, rule in enumerate(ingress_ruledefs):
            rule.update({'type': 'ingress', 'security_group_id': sg.id})
            ingress_rules.append(
                aws.ec2.SecurityGroupRule(
                    f'{name}-ingress-{idx}',
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[sg], delete_before_replace=True),
                    **rule,
                )
            )

        egress_ruledefs = rules['egress']
        for idx, rule in enumerate(egress_ruledefs):
            rule.update({'type': 'egress', 'security_group_id': sg.id})
            egress_rules.append(
                aws.ec2.SecurityGroupRule(
                    f'{name}-egress-{idx}',
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[sg], delete_before_replace=True),
                    **rule,
                )
            )

        self.finish(
            resources={
                'egress_rules': egress_rules,
                'ingress_rules': ingress_rules,
                'sg': sg,
            },
        )
