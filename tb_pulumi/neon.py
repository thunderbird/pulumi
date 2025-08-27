import pulumi
import pulumi_aws as aws
import pulumi_neon as neon
import tb_pulumi

#: Mapping of all AWS service endpoints for all supported regions. Ref: https://neon.com/docs/guides/neon-private-networking
NEON_AWS_SERVICE_ENDPOINTS = {
    'us-east-1': [
        'com.amazonaws.vpce.us-east-1.vpce-svc-0de57c578b0e614a9',
        'com.amazonaws.vpce.us-east-1.vpce-svc-02a0abd91f32f1ed7',
    ],
    'us-east-2': [
        'com.amazonaws.vpce.us-east-2.vpce-svc-010736480bcef5824',
        'com.amazonaws.vpce.us-east-2.vpce-svc-0465c21ce8ba95fb2',
    ],
    'eu-central-1': [
        'com.amazonaws.vpce.eu-central-1.vpce-svc-05554c35009a5eccb',
    ],
    'aws-eu-west-2': [
        'com.amazonaws.vpce.eu-west-2.vpce-svc-0c6fedbe99fced2cd',
    ],
    'us-west-2': [
        'com.amazonaws.vpce.us-west-2.vpce-svc-060e0d5f582365b8e',
        'com.amazonaws.vpce.us-west-2.vpce-svc-07b750990c172f22f',
    ],
    'ap-southeast-1': [
        'com.amazonaws.vpce.ap-southeast-1.vpce-svc-07c68d307f9f05687',
    ],
    'ap-southeast-2': [
        'com.amazonaws.vpce.ap-southeast-2.vpce-svc-031161490f5647f32',
    ],
    'aws-sa-east-1': [
        'com.amazonaws.vpce.sa-east-1.vpce-svc-061204a851dbd1a47',
    ],
}


class NeonDatabaseEndpoint(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:neon:NeonDatabaseEndpoint``

    Construct a VPC Endpoint in the specific way required by NeonDB to establish private database communication.

    First, we must create a VpcEndpoint with DNS disabled on the AWS/VPC side. Then we must create the VPC Endpoint
    Assignment on the NeonDB side. Then we must wait for that Assignment to be complete. Then we can enable DNS on the
    endpoint.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        subnet_ids: list[str],
        vpc_id: str,
        # Technically, we could also offer egress_security_group_ids, but it doesn't make any sense in this context
        egress_cidrs: list[str] = ['0.0.0.0/0'],
        ingress_cidrs: list[str] = [],
        ingress_security_group_ids: list[str] = [],
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
    ):
        super().__init__(
            'tb:neon:NeonDatabaseEndpoint',
            name=name,
            project=project,
            opts=opts,
            tags=tags,
        )

        sg_rules = {
            'egress': [
                {
                    'description': 'Allow postgres',
                    'protocol': 'tcp',
                    'from_port': 5432,
                    'to_port': 5432,
                    'cidr_blocks': egress_cidrs,
                }
            ],
            'ingress': [],
        }
        if ingress_cidrs:
            sg_rules['ingress'].append(
                {
                    'description': 'Allow postgres',
                    'protocol': 'tcp',
                    'from_port': 5432,
                    'to_port': 5432,
                    'cidr_blocks': ingress_cidrs,
                }
            )
        if ingress_security_group_ids:
            sg_rules['ingress'].extend(
                [
                    {
                        'description': 'Allow postgres',
                        'protocol': 'tcp',
                        'from_port': 5432,
                        'to_port': 5432,
                        'security_group_id': sgid,
                    }
                    for sgid in ingress_security_group_ids
                ]
            )

        # Create a security group allowing Postgres's TCP traffic through the endpoints to come
        vpc_endpoint_sg = tb_pulumi.network.SecurityGroupWithRules(
            f'{self.name}-neonsg',
            project=project,
            vpc_id=vpc_id,
            rules=sg_rules,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Build a VPC endpoint for each of the service endpoints on Neon's side
        vpc_endpoints = []
        for idx, service_name in enumerate(NEON_AWS_SERVICE_ENDPOINTS.get(project.aws_region, [])):
            endpoint_name = f'{self.name}-neonvpce-{idx}'
            tags = self.tags.copy()
            tags.update({'Name': endpoint_name})
            vpc_endpoints.append(
                aws.ec2.VpcEndpoint(
                    endpoint_name,
                    private_dns_enabled=False,
                    security_group_ids=[vpc_endpoint_sg.id],
                    service_name=service_name,
                    subnet_ids=subnet_ids,
                    vpc_endpoint_type='Interface',
                    vpc_id=vpc_id,
                    opts=pulumi.ResourceOptions(parent=self, ignore_changes=['private_dns_enabled']),
                    tags=tags,
                )
            )

        # Establish the VPC assignment on Neon's side
        # neon_assignment =

        self.finish(resources={'vpc_endpoints': vpc_endpoints})
