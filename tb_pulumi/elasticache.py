"""Infrastructural patterns related to `AWS ElastiCache <https://docs.aws.amazon.com/elasticache/>`_."""

import pulumi
import pulumi_aws as aws
import tb_pulumi


class ElastiCacheReplicationGroup(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:elasticache:ElastiCacheReplicationGroup``

    Builds an ElastiCache replication group in your VPC. This provides a primary writable node with zero or more
    readable replica nodes. The default configuration is for a single-node Redis 7.1 replication group.

    Produces the following ``resources``:

        - *replication_group* - The `aws.elasticache.ReplicationGroup
          <https://www.pulumi.com/registry/packages/aws/api-docs/elasticache/replicationgroup/>`_.
        - *security_group* - The :py:class:`tb_pulumi.network.SecurityGroupWithRules` describing traffic rules for the
          cluster.
        - *parameter_group* - The `aws.elasticache.ParameterGroup
          <https://www.pulumi.com/registry/packages/aws/api-docs/elasticache/parametergroup/>`_ that configures the
          cache service.
        - *subnet_group* - The `aws.elasticache.SubnetGroup
          <https://www.pulumi.com/registry/packages/aws/api-docs/elasticache/subnetgroup/>`_ the cluster is built on.

    .. note:
        Although this replica group is marked as "single-az" the nodes will be deployed across the range of subnets
        provided as you add nodes. A single-node deployment will be truly single-AZ, while multi-node deployments will
        spread their nodes across the subnets, allowing you to build read replicas in other AZs.

    :param name: A string identifying this set of resources.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param subnets: List of subnet IDs in which to build the replication group.
    :type subnets: list[str]

    :param description: Common description of the replication group. Defaults to None.
    :type description: str, optional

    :param engine: Which cache engine to use. Must be either 'valkey' or 'redis'. Defaults to 'redis'.
    :type engine: str, optional

    :param engine_version: Engine version to use. Defaults to '7.1', which is valid for Redis groups.
    :type engine_version: str, optional

    :param node_type: Instance type to build nodes with. Defaults to 'cache.t3.micro'.
    :type node_type: str, optional

    :param num_cache_nodes: Number of nodes to build. If building only one node, ``automatic_failover_enabled`` must
        be False. Defaults to 1.
    :type num_cache_nodes: int, optional

    :param parameter_group_family: Parameter group family to build this parameter group from. Defaults to 'redis7',
        which comports with the default engine version.
    :type parameter_group_family: str, optional

    :param parameter_group_params: List of dicts defining default parameter value overrides. Should be strucutured
        as a `ParameterGroupParameter
        <https://www.pulumi.com/registry/packages/aws/api-docs/elasticache/parametergroup/#parametergroupparameter>`_.
        Defaults to [].
    :type parameter_group_params: list[dict], optional

    :param port: Port to listen on. Defaults to 6379, the default Redis port.
    :type port: int, optional

    :param source_cidrs: List of CIDRs which should have access to the replication group. Defaults to [].
    :type source_cidrs: list[str], optional

    :param source_sgids: List of security group IDs which should have access to the replication group. Defaults to
        [].
    :type source_sgids: list[str], optional

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param tags: Key/value pairs to merge with the default tags which get applied to all resources in this group.
        Defaults to {}.
    :type tags: dict, optional

    :param kwargs: Any other keyword arguments which will be passed as inputs to the ReplicationGroup resource. A
        full listing of options is found `here
        <https://www.pulumi.com/registry/packages/aws/api-docs/elasticache/replicationgroup/#inputs>`_.

    :raises IndexError: Thrown if an empty list of subnets is supplied.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        subnets: list[str],
        description: str = None,
        engine: str = 'redis',
        engine_version: str = '7.1',
        node_type: str = 'cache.t3.micro',
        num_cache_nodes: int = 1,
        parameter_group_family: str = 'redis7',
        parameter_group_params: list[dict] = [],
        port=6379,
        source_cidrs: list[str] = [],
        source_sgids: list[str] = [],
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
        **kwargs,
    ):
        if len(subnets) < 1:
            raise IndexError('You must provide at least one subnet.')

        if description is None:
            description = f'{name}-{engine}-{engine_version}'

        super().__init__('tb:elasticache:ElastiCacheReplicationGroup', name=name, project=project, opts=opts, tags=tags)

        __sg_rules = {
            'ingress': [],
            'egress': [
                {
                    'cidr_blocks': ['0.0.0.0/0'],
                    'from_port': 0,
                    'to_port': 65535,
                    'protocol': 'tcp',
                    'description': 'Allow all egress',
                }
            ],
        }

        if len(source_cidrs) > 0:
            __sg_rules['ingress'].append(
                {
                    'description': 'Allow traffic from certain CIDR blocks',
                    'from_port': port,
                    'to_port': port,
                    'protocol': 'tcp',
                    'cidr_blocks': source_cidrs,
                }
            )

        __sg_rules['ingress'].extend(
            [
                {
                    'description': 'Allow traffic from certain other security groups',
                    'from_port': port,
                    'to_port': port,
                    'protocol': 'tcp',
                    'source_security_group_id': source_sgid,
                }
                for source_sgid in source_sgids
            ]
        )

        security_group = tb_pulumi.network.SecurityGroupWithRules(
            name=name,
            project=project,
            exclude_from_project=True,
            rules=__sg_rules,
            tags=self.tags,
            vpc_id=subnets[0].vpc_id,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Create a custom parameter group, even if we want to use defaults. This allows us to tweak the settings later
        # where using the AWS-provided default group does not.
        parameter_group = aws.elasticache.ParameterGroup(
            f'{name}-parameter-group',
            name=name,
            family=parameter_group_family,
            parameters=parameter_group_params,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        subnet_group = aws.elasticache.SubnetGroup(
            f'{name}-subnet-group',
            description=f'Subnet group for {name}',
            name=name,
            subnet_ids=subnets,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        replication_group = aws.elasticache.ReplicationGroup(
            f'{name}-replication-group',
            description=description,
            engine=engine,
            engine_version=engine_version,
            node_type=node_type,
            parameter_group_name=parameter_group.name,
            replication_group_id=name,
            security_group_ids=[security_group.resources['sg'].id],
            subnet_group_name=subnet_group.name,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[security_group, parameter_group, subnet_group]),
            **kwargs,
        )

        self.finish(
            resources={
                'replication_group': replication_group,
                'parameter_group': parameter_group,
                'security_group': security_group,
                'subnet_group': subnet_group,
            }
        )
