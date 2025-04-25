"""Infrastructural patterns related to AWS's RDS product."""

import pulumi
import pulumi_aws as aws
import pulumi_random
import socket
import tb_pulumi
import tb_pulumi.ec2
import tb_pulumi.network
import tb_pulumi.secrets

from tb_pulumi.constants import SERVICE_PORTS


class RdsDatabaseGroup(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:rds:RdsDatabaseGroup``

    Using RDS, construct a primary database and zero or more read replicas. A Network Load Balancer (NLB) is
    created to spread load across the read replicas.

    Produces the following ``resources``:

        - *instances* - A list of `aws.rds.Instances
          <https://www.pulumi.com/registry/packages/aws/api-docs/rds/instance/>`_ in the group. The zeroth index will
          always be the primary/writer instance. If there are any replica/reader instances, those will follow.
        - *key* - `aws.kms.Key <https://www.pulumi.com/registry/packages/aws/api-docs/kms/key/>`_ used to encrypt
          database storage.
        - *load_balancer* - :py:class:`tb_pulumi.ec2.NetworkLoadBalancer` routing traffic to the read databases.
        - *parameter_group* - `aws.rds.ParameterGroup
          <https://www.pulumi.com/registry/packages/aws/api-docs/rds/parametergroup/>`_ defining how these databases
          operate.
        - *password* - `pulumi_random.RandomPassword
          <https://www.pulumi.com/registry/packages/random/api-docs/randompassword/>`_ for the database.
        - *secret* - :py:class:`tb_pulumi.secrets.SecretsManagerSecret` storing the password within AWS.
        - *security_group* - :py:class:`tb_pulumi.network.SecurityGroupWithRules` defining access to the database.
        - *ssm_param_db_name* - `aws.ssm.Parameter
          <https://www.pulumi.com/registry/packages/aws/api-docs/ssm/parameter/>`_ containing the database name.
        - *ssm_param_db_write_host* - `aws.ssm.Parameter
          <https://www.pulumi.com/registry/packages/aws/api-docs/ssm/parameter/>`_ containing the write instance's
          hostname.
        - *ssm_param_port* - `aws.ssm.Parameter
          <https://www.pulumi.com/registry/packages/aws/api-docs/ssm/parameter/>`_ containing the database port.
        - *ssm_param_read_host* - `aws.ssm.Parameter
          <https://www.pulumi.com/registry/packages/aws/api-docs/ssm/parameter/>`_ containing the hostname of the read
          traffic load balancer.
        - *subnet_group* - `aws.rds.SubnetGroup
          <https://www.pulumi.com/registry/packages/aws/api-docs/rds/subnetgroup/>`_, a logical grouping of subnets in
          which to build database instances.

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
        this option depending on other storage options. Details are found in
        `AWS RDS documentation <https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Storage.html>`_. Defaults to
        20.
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
        `in these docs <https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.DBInstanceClass.html>`_.
        Defaults to 'db.t3.micro'.
    :type instance_class: str, optional

    :param internal: When True, if no sg_cidrs are set, allows ingress only from what `vpc_cidr` is set to. If False
        and no sg_cidrs are set, allows ingress from anywhere. Defaults to True.
    :type internal: bool, optional

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

    :param secret_recovery_window_in_days: Number of days to retain the database_url secret after it has been deleted.
        Set this to zero in testing environments to avoid issues during stack rebuilds. Defaults to None (which causes
        AWS to default to 7 days).
    :type secret_recovery_window_in_days: int, optional

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

    :param tags: Key/value pairs to merge with the default tags which get applied to all resources in this group.
        Defaults to {}.
    :type tags: dict, optional

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
        db_username: str = 'root',
        enabled_cluster_cloudwatch_logs_exports: list[str] = [],
        enabled_instance_cloudwatch_logs_exports: list[str] = [],
        engine: str = 'postgres',
        engine_version: str = '15.7',
        instance_class: str = 'db.t3.micro',
        internal: bool = True,
        max_allocated_storage: int = 0,
        num_instances: int = 1,
        override_special='!#$%&*()-_=+[]{}<>:?',
        parameters: list[dict] = None,
        parameter_group_family: str = 'postgres15',
        performance_insights_enabled: bool = False,
        port: int = None,
        secret_recovery_window_in_days: int = None,
        sg_cidrs: list[str] = None,
        skip_final_snapshot: bool = False,
        storage_type: str = 'gp3',
        tags: dict = {},
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        if 'exclude_from_project' in kwargs:
            exclude_from_project = kwargs.pop('exclude_from_project', False)
        else:
            exclude_from_project = False

        super().__init__(
            'tb:rds:RdsDatabaseGroup', name, project, exclude_from_project=exclude_from_project, opts=opts, tags=tags
        )

        unsupported_opts = ['build_jumphost', 'jumphost_public_key', 'jumphost_source_cidrs', 'jumphost_user_data']
        invalid_opts = [opt for opt in unsupported_opts if opt in kwargs]
        if len(invalid_opts) > 0:
            pulumi.warn(
                'The tb_pulumi.rds.RdsDatabaseGroup class no longer support the following arguments:',
                f'{", ".join(unsupported_opts)}. ',
                'Instead, build a `tb_pulumi.ec2.SshableInstance`.',
            )
            for opt in invalid_opts:
                del kwargs[opt]

        # Generate a random password
        password = pulumi_random.RandomPassword(
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
        secret = tb_pulumi.secrets.SecretsManagerSecret(
            f'{name}-secret',
            project=project,
            exclude_from_project=True,
            secret_name=secret_fullname,
            secret_value=password.result,
            recovery_window_in_days=secret_recovery_window_in_days,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[password]),
            tags=self.tags,
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
        security_group_with_rules = tb_pulumi.network.SecurityGroupWithRules(
            f'{name}-sg',
            project,
            vpc_id=vpc_id,
            exclude_from_project=True,
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
            tags=self.tags,
        )

        # Build a subnet group to launch instances in
        subnet_group = aws.rds.SubnetGroup(
            f'{name}-subnetgroup',
            name=name,
            subnet_ids=[subnet.id for subnet in subnets],
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[*subnets]),
        )

        # Build a parameter group
        parameter_group = aws.rds.ParameterGroup(
            f'{name}-parametergroup',
            name=name,
            family=parameter_group_family,
            parameters=parameters,
            opts=pulumi.ResourceOptions(parent=self),
            tags=self.tags,
        )

        # Build a KMS Key
        key = aws.kms.Key(
            f'{name}-storage',
            description=f'Key to encrypt database storage for {name}',
            deletion_window_in_days=7,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
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
            db_subnet_group_name=subnet_group.name,
            enabled_cloudwatch_logs_exports=enabled_instance_cloudwatch_logs_exports,
            engine=engine,
            engine_version=engine_version,
            identifier=instance_id,
            instance_class=instance_class,
            kms_key_id=key.arn,
            max_allocated_storage=max_allocated_storage,
            password=password.result,
            parameter_group_name=parameter_group.name,
            performance_insights_enabled=performance_insights_enabled,
            performance_insights_kms_key_id=key.arn if performance_insights_enabled else None,
            port=port,
            publicly_accessible=False,
            skip_final_snapshot=skip_final_snapshot,
            storage_encrypted=True,
            storage_type=storage_type,
            username=db_username,
            vpc_security_group_ids=[security_group_with_rules.resources['sg'].id],
            tags=instance_tags,
            opts=pulumi.ResourceOptions(
                parent=self,
                depends_on=[
                    key,
                    parameter_group,
                    password,
                    security_group_with_rules,
                    subnet_group,
                ],
            ),
            **kwargs,
        )

        # Build replica instances in the cluster
        instances = [primary]
        for idx in range(1, num_instances):  # Start at 1, taking the primary into account
            # Pad the index with zeroes to produce a 3-char string ID; set tags
            idx_str = str(idx).rjust(3, '0')
            instance_id = f'{tb_pulumi.PROJECT}-{tb_pulumi.STACK}-{idx_str}'
            instance_tags = {'instanceId': instance_id}
            instance_tags.update(self.tags)

            instances.append(
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
                    kms_key_id=key.arn,
                    max_allocated_storage=max_allocated_storage,
                    parameter_group_name=parameter_group.name,
                    performance_insights_enabled=performance_insights_enabled,
                    performance_insights_kms_key_id=key.id if performance_insights_enabled else None,
                    port=port,
                    publicly_accessible=False,
                    replicate_source_db=primary.identifier,
                    skip_final_snapshot=skip_final_snapshot,
                    storage_encrypted=True,
                    storage_type=storage_type,
                    vpc_security_group_ids=[security_group_with_rules.resources['sg'].id],
                    tags=instance_tags,
                    opts=pulumi.ResourceOptions(
                        parent=self, depends_on=[key, parameter_group, security_group_with_rules, primary]
                    ),
                ),
                **kwargs,
            )

        # Store some data as SSM params for later retrieval
        ssm_param_port = (
            self.__ssm_param(f'{name}-ssm-port', f'/{self.project.project}/{self.project.stack}/db-port', port),
        )
        ssm_param_db_name = (
            self.__ssm_param(f'{name}-ssm-dbname', f'/{self.project.project}/{self.project.stack}/db-name', db_name),
        )
        ssm_param_db_write_host = (
            self.__ssm_param(
                f'{name}-ssm-dbwritehost',
                f'/{self.project.project}/{self.project.stack}/db-write-host',
                primary.address,
                depends_on=[primary],
            ),
        )

        # Figure out the IPs once the instances are ready and build a load balancer targeting them
        port = SERVICE_PORTS.get(engine, 5432)
        inst_addrs = [instance.address for instance in instances]
        load_balancer = pulumi.Output.all(*inst_addrs).apply(
            lambda addresses: tb_pulumi.ec2.NetworkLoadBalancer(
                f'{name}-nlb',
                project=project,
                exclude_from_project=True,
                listener_port=port,
                subnets=subnets,
                target_port=port,
                ingress_cidrs=[vpc_cidr],
                internal=True,
                ips=[socket.gethostbyname(addr) for addr in addresses],
                security_group_description=f'Allow database traffic for {name}',
                opts=pulumi.ResourceOptions(parent=self, depends_on=[*instances, *subnets]),
                tags=self.tags,
            )
        )

        ssm_param_db_read_host = load_balancer.apply(
            lambda lb: aws.ssm.Parameter(
                f'{name}-ssm-dbreadhost',
                name=f'/{self.project.project}/{self.project.stack}/db-read-host',
                type=aws.ssm.ParameterType.STRING,
                value=lb.resources['nlb'].dns_name,
                opts=pulumi.ResourceOptions(depends_on=[load_balancer]),
                tags=self.tags,
            )
        )

        self.finish(
            resources={
                'instances': instances,
                'key': key,
                'load_balancer': load_balancer,
                'parameter_group': parameter_group,
                'password': password,
                'secret': secret,
                'security_group': security_group_with_rules,
                'ssm_param_db_name': ssm_param_db_name,
                'ssm_param_db_write_host': ssm_param_db_write_host,
                'ssm_param_port': ssm_param_port,
                'ssm_param_read_host': ssm_param_db_read_host,
                'subnet_group': subnet_group,
            },
        )

    def __ssm_param(self, name, param_name, value, depends_on: list[pulumi.Output] = None) -> aws.ssm.Parameter:
        """Build an SSM Parameter."""
        return aws.ssm.Parameter(
            name,
            name=param_name,
            type=aws.ssm.ParameterType.STRING,
            value=value,
            opts=pulumi.ResourceOptions(depends_on=depends_on),
            tags=self.tags,
        )
