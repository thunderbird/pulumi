"""Infrastructural patterns related to AWS's RDS product."""

import pulumi
import pulumi_aws as aws
import pulumi_random
import socket
import tb_pulumi
import tb_pulumi.ec2
import tb_pulumi.network

from tb_pulumi.constants import SERVICE_PORTS


class RdsDatabaseGroup(tb_pulumi.ThunderbirdComponentResource):
    """Using RDS, construct a primary database and zero or more read replicas. A Network Load Balancer (NLB) is
    created to spread load across the read replicas.

    :param name: A string identifying this set of resources.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param db_name: What to call the name of the database at the schema level.
    :type db_name: str

    :param subnets: List of subnet Output objects defining the network space to build in.
    :type subnets: list[pulumi.Output]

    :param vpc_cidr: An IP range to allow incoming traffic from, which is a subset of the IP range allowed by the
        VPC in which this cluster is built. If you do not specify `sg_cidrs`, but `internal` is True, then ingress
        traffic will be limited to being sourced in this CIDR.
    :type vpc_cidr: str

    :param vpc_id: The ID of the VPC to build in.
    :type vpc_id: str

    :param allocated_storage: GB of storage to allot to each instance. AWS may impose different minimum values for
        this option depending on other storage options. Details are
        `here <https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Storage.html>`_. Defaults to 20.
    :type allocated_storage: int, optional

    :param auto_minor_version_upgrade: Allow RDS to upgrade the engine as long as it's only a minor version change,
        and therefore backward compatible. Defaults to True.
    :type auto_minor_version_upgrade: bool, optional

    :param apply_immediately: When True, changes to the DB config will be applied right away instead of during the
        next maintenance window. Depending on the change, this could cause downtime. Defaults to False.
    :type apply_immediately: bool, optional

    :param backup_retention_period: Number of days to keep old backups. Defaults to 7.
    :type backup_retention_period: int, optional

    :param blue_green_update: When RDS applies updates, it will deploy a new cluster and fail over to it.
        `AWS Reference <https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/blue-green-deployments.html>`_
        Defaults to False.
    :type blue_green_update: bool, optional

    :param build_jumphost: When True, an EC2 instance in the same network space but with a public IP address will be
        built, allowing access to a database that's only internally accessible. Defaults to False.
    :type build_jumphost: bool, optional

    :param db_username: The username to use for the root-level administrative user in the database. Defaults to
        'root'.
    :type db_username: str, optional

    :param enabled_cluster_cloudwatch_logs_exports: Any combination of valid log types for a DB instance to export.
        These include: audit, error, general, slowquery, postgresql. Defaults to [].
    :type enabled_cluster_cloudwatch_logs_exports: list[str], optional

    :param enabled_instance_cloudwatch_logs_exports: Any combination of valid log types for a DB cluster to export.
        For details, see the "EnableCloudwatchLogsExports" section of
        `these docs <https://docs.aws.amazon.com/AmazonRDS/latest/APIReference/API_CreateDBInstance.html>`_.
        Defaults to [].
    :type enabled_instance_cloudwatch_logs_exports: list[str], optional

    :param engine: The core database engine to use, such as "postgres" or "mysql". Defaults to 'postgres'.
    :type engine: str, optional

    :param engine_version: The version of the engine to use. This is a specific string that AWS recognizes. You can
        see a list of those strings by running this command: ``aws rds describe-db-engine-versions``. Defaults to
        '15.7'
    :type engine_version: str, optional

    :param instance_class: One of the database sizes listed
        `here <https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.DBInstanceClass.html>`_. Defaults to
        'db.t3.micro'.
    :type instance_class: str, optional

    :param internal: When True, if no sg_cidrs are set, allows ingress only from what `vpc_cidr` is set to. If False
        and no sg_cidrs are set, allows ingress from anywhere. Defaults to True.
    :type internal: bool, optional

    :param jumphost_public_key: The public key you want to use when authenticating against the jumphost's SSH
        service. Defaults to None.
    :type jumphost_public_key: str, optional

    :param jumphost_source_cidrs: List of CIDRs to allow SSH ingress to the jump host from. Defaults to
        ['0.0.0.0/0'].
    :type jumphost_source_cidrs: list[str], optional

    :param jumphost_user_data: Plaintext value (not base64-encoded) of the user data to pass the jumphost. Use this
        to launch the server with your database client of choice pre-installed, for example. Defaults to None.
    :type jumphost_user_data: str, optional

    :param max_allocated_storage: Gigabytes of storage which storage autoscaling will refuse to increase beyond. To
        disable autoscaling, set this to zero. Defaults to 0.
    :type max_allocated_storage: int, optional

    :param num_instances: Number of database servers to build. This must be at least 1. This module interprets this
        number to mean that we should build a primary instance and (num_instances - 1) read replicas. All servers
        will be built from the same set of options described here. Defaults to 1.
    :type num_instances: int, optional

    :param override_special: The root password is generated using "special characters". Set this value to a string
        containing only those special characters that you want included in your otherwise random password. Defaults
        to '!#$%&*()-_=+[]{}<>:?'.
    :type override_special: str, optional

    :param parameters: A list of dicts describing parameters to override from the defaults set by the
        parameter_group_family. These dicts should describe one of
        `these <https://www.pulumi.com/registry/packages/aws/api-docs/rds/parametergroup/#parametergroupparameter>`_.
        Defaults to None
    :type parameters: list[dict], optional

    :param parameter_group_family: A special string known to AWS describing the base set of DB parameters to use.
        These parameters can be overridden with the `parameters` option. You can get a list of options by running:
        ``aws rds describe-db-engine-versions --query "DBEngineVersions[].DBParameterGroupFamily"`` Defaults to
        'postgres15'.
    :type parameter_group_family: str, optional

    :param performance_insights_enabled: Record more detailed monitoring metrics to CloudWatch. Incurs additional costs.
        Defaults to False.
    :type performance_insights_enabled: bool, optional

    :param port: Specify a non-default listening port. Defaults to None.
    :type port: int, optional

    :param sg_cidrs: A list of CIDRs from which ingress should be allowed. If this is left to the default value, a
        sensible default will be selected. If `internal` is True, this will allow access from the `vpc_cidr`. Otherwise,
        traffic will be allowed from anywhere. Defaults to None.
    :type sg_cidrs: list[str], optional

    :param skip_final_snapshot: Allow deletion of an RDS instance without performing a final backup. Defaults to False.
    :type skip_final_snapshot: bool, optional

    :param storage_type: Type of storage to provision. Defaults to `gp3` but could be set to other values such as `io2`.
        For details, see `Amazon RDS DB instance storage <https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Storage.html>`_
        Defaults to 'gp3'.
    :type storage_type: str, optional

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param kwargs: Key/value pairs describing additional arguments to be passed into *all* RDS Instance declarations.
        Detail can be found `here <https://www.pulumi.com/registry/packages/aws/api-docs/rds/instance/#inputs>`_.

    :raises ValueError: Raised if no ``port`` is supplied, and if a default cannot be found in the lookup table in the
        constants module.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        db_name: str,
        subnets: list[pulumi.Output],
        vpc_cidr: str,
        vpc_id: str,
        allocated_storage: int = 20,
        auto_minor_version_upgrade: bool = True,
        apply_immediately: bool = False,
        backup_retention_period: int = 7,
        blue_green_update: bool = False,
        build_jumphost: bool = False,
        db_username: str = 'root',
        enabled_cluster_cloudwatch_logs_exports: list[str] = [],
        enabled_instance_cloudwatch_logs_exports: list[str] = [],
        engine: str = 'postgres',
        engine_version: str = '15.7',
        instance_class: str = 'db.t3.micro',
        internal: bool = True,
        jumphost_public_key: str = None,
        jumphost_source_cidrs: list[str] = ['0.0.0.0/0'],
        jumphost_user_data: str = None,
        max_allocated_storage: int = 0,
        num_instances: int = 1,
        override_special='!#$%&*()-_=+[]{}<>:?',
        parameters: list[dict] = None,
        parameter_group_family: str = 'postgres15',
        performance_insights_enabled: bool = False,
        port: int = None,
        sg_cidrs: list[str] = None,
        skip_final_snapshot: bool = False,
        storage_type: str = 'gp3',
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        super().__init__('tb:rds:RdsDatabaseGroup', name, project, opts=opts)

        # Generate a random password
        self.resources['password'] = pulumi_random.RandomPassword(
            f'{name}-password',
            length=29,
            override_special=override_special,
            special=True,
            min_lower=1,
            min_numeric=1,
            min_special=1,
            min_upper=1,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Store the password in Secrets Manager
        secret_fullname = f'{self.project.project}/{self.project.stack}/{name}/root_password'
        self.resources['secret'] = aws.secretsmanager.Secret(
            f'{name}-secret', opts=pulumi.ResourceOptions(parent=self), name=secret_fullname
        )
        self.resources['secret_version'] = aws.secretsmanager.SecretVersion(
            f'{name}-secretversion',
            secret_id=self.resources['secret'].id,
            secret_string=self.resources['password'].result,
            opts=pulumi.ResourceOptions(parent=self, depends_on=self.resources['password']),
        )

        # If no ingress CIDRs have been defined, find a reasonable default
        if sg_cidrs is None:
            cidrs = [vpc_cidr] if internal else ['0.0.0.0/0']
        else:
            cidrs = sg_cidrs

        # If no port has been specified, try to look it up by the engine name
        if port is None:
            port = SERVICE_PORTS.get(engine, None)
            if port is None:
                raise ValueError('Cannot determine the correct port to open')

        # Build a security group allowing the specified access
        self.resources['security_group_with_rules'] = tb_pulumi.network.SecurityGroupWithRules(
            f'{name}-sg',
            project,
            vpc_id=vpc_id,
            rules={
                'ingress': [
                    {
                        'cidr_blocks': cidrs,
                        'description': 'Database access',
                        'protocol': 'tcp',
                        'from_port': port,
                        'to_port': port,
                    }
                ],
                'egress': {},
            },
            opts=pulumi.ResourceOptions(parent=self),
        ).resources

        # Build a subnet group to launch instances in
        self.resources['subnet_group'] = aws.rds.SubnetGroup(
            f'{name}-subnetgroup',
            name=name,
            subnet_ids=[subnet.id for subnet in subnets],
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Build a parameter group
        self.resources['parameter_group'] = aws.rds.ParameterGroup(
            f'{name}-parametergroup',
            name=name,
            opts=pulumi.ResourceOptions(parent=self),
            family=parameter_group_family,
            parameters=parameters,
        )

        # Build a KMS Key
        self.resources['key'] = aws.kms.Key(
            f'{name}-storage',
            opts=pulumi.ResourceOptions(parent=self),
            description=f'Key to encrypt database storage for {name}',
            deletion_window_in_days=7,
            tags=self.tags,
        )

        # Build the primary instance
        instance_id = f'{self.project.name_prefix}-000'
        instance_tags = {'instanceId': instance_id}
        instance_tags.update(self.tags)
        primary = aws.rds.Instance(
            f'{name}-instance-{000}',
            allocated_storage=allocated_storage,
            allow_major_version_upgrade=False,
            auto_minor_version_upgrade=auto_minor_version_upgrade,
            backup_retention_period=backup_retention_period,
            blue_green_update={'enabled': blue_green_update},
            copy_tags_to_snapshot=True,
            db_name=db_name,
            db_subnet_group_name=self.resources['subnet_group'].name,
            enabled_cloudwatch_logs_exports=enabled_instance_cloudwatch_logs_exports,
            engine=engine,
            engine_version=engine_version,
            identifier=instance_id,
            instance_class=instance_class,
            kms_key_id=self.resources['key'].arn,
            max_allocated_storage=max_allocated_storage,
            password=self.resources['password'].result,
            parameter_group_name=self.resources['parameter_group'].name,
            performance_insights_enabled=performance_insights_enabled,
            performance_insights_kms_key_id=self.resources['key'].arn if performance_insights_enabled else None,
            port=port,
            publicly_accessible=False,
            skip_final_snapshot=skip_final_snapshot,
            storage_encrypted=True,
            storage_type=storage_type,
            username=db_username,
            vpc_security_group_ids=[self.resources['security_group_with_rules']['sg'].id],
            tags=instance_tags,
            opts=pulumi.ResourceOptions(
                parent=self,
                depends_on=[
                    self.resources['key'],
                    self.resources['parameter_group'],
                    self.resources['password'],
                    self.resources['subnet_group'],
                ],
            ),
            **kwargs,
        )

        # Build replica instances in the cluster
        self.resources['instances'] = [primary]
        for idx in range(1, num_instances):  # Start at 1, taking the primary into account
            # Pad the index with zeroes to produce a 3-char string ID; set tags
            idx_str = str(idx).rjust(3, '0')
            instance_id = f'{tb_pulumi.PROJECT}-{tb_pulumi.STACK}-{idx_str}'
            instance_tags = {'instanceId': instance_id}
            instance_tags.update(self.tags)

            self.resources['instances'].append(
                aws.rds.Instance(
                    f'{name}-instance-{idx_str}',
                    allow_major_version_upgrade=False,
                    auto_minor_version_upgrade=auto_minor_version_upgrade,
                    backup_retention_period=backup_retention_period,
                    blue_green_update={'enabled': blue_green_update},
                    copy_tags_to_snapshot=True,
                    enabled_cloudwatch_logs_exports=enabled_instance_cloudwatch_logs_exports,
                    engine=engine,
                    engine_version=engine_version,
                    identifier=instance_id,
                    instance_class=instance_class,
                    kms_key_id=self.resources['key'].arn,
                    max_allocated_storage=max_allocated_storage,
                    parameter_group_name=self.resources['parameter_group'].name,
                    performance_insights_enabled=performance_insights_enabled,
                    performance_insights_kms_key_id=self.resources['key'].id if performance_insights_enabled else None,
                    port=port,
                    publicly_accessible=False,
                    replicate_source_db=primary.identifier,
                    skip_final_snapshot=skip_final_snapshot,
                    storage_encrypted=True,
                    storage_type=storage_type,
                    vpc_security_group_ids=[self.resources['security_group_with_rules']['sg'].id],
                    tags=instance_tags,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[primary]),
                ),
                **kwargs,
            )

        # Store some data as SSM params for later retrieval
        self.resources['ssm_param_port'] = (
            self.__ssm_param(f'{name}-ssm-port', f'/{self.project.project}/{self.project.stack}/db-port', port),
        )
        self.resources['ssm_param_db_name'] = (
            self.__ssm_param(f'{name}-ssm-dbname', f'/{self.project.project}/{self.project.stack}/db-name', db_name),
        )
        self.resources['ssm_param_db_write_host'] = (
            self.__ssm_param(
                f'{name}-ssm-dbwritehost',
                f'/{self.project.project}/{self.project.stack}/db-write-host',
                primary.address,
            ),
        )

        # Figure out the IPs once the instances are ready and build a load balancer targeting them
        port = SERVICE_PORTS.get(engine, 5432)
        inst_addrs = [instance.address for instance in self.resources['instances']]
        pulumi.Output.all(*inst_addrs).apply(
            lambda addresses: self.__load_balancer(name, project, port, subnets, vpc_cidr, *addresses)
        )

        if build_jumphost:
            self.resources['jumphost'] = tb_pulumi.ec2.SshableInstance(
                f'{name}-jumphost',
                project,
                subnets[0].id,
                kms_key_id=self.resources['key'].arn,
                public_key=jumphost_public_key,
                source_cidrs=jumphost_source_cidrs,
                user_data=jumphost_user_data,
                vpc_id=vpc_id,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[self.resources['key']]),
            ).resources

        self.finish()

    def __load_balancer(self, name, project, port, subnets, vpc_cidr, *addresses):
        # Build a load balancer
        self.resources['nlb'] = tb_pulumi.ec2.NetworkLoadBalancer(
            f'{name}-nlb',
            project,
            port,
            subnets,
            port,
            ingress_cidrs=[vpc_cidr],
            internal=True,
            ips=[socket.gethostbyname(addr) for addr in addresses],
            security_group_description=f'Allow database traffic for {name}',
            opts=pulumi.ResourceOptions(parent=self, depends_on=[*self.resources['instances']]),
        ).resources
        self.resources['ssm_param_read_host'] = self.__ssm_param(
            f'{name}-ssm-dbreadhost',
            f'/{self.project.project}/{self.project.stack}/db-read-host',
            self.resources['nlb']['nlb'].dns_name.apply(lambda dns_name: dns_name),
        )

    def __ssm_param(self, name, param_name, value):
        """Build an SSM Parameter."""
        return aws.ssm.Parameter(name, name=param_name, type=aws.ssm.ParameterType.STRING, value=value)
