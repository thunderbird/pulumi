import json
import pulumi
import pulumi_aws as aws
import tb_pulumi

from tb_pulumi.constants import ASSUME_ROLE_POLICY, DEFAULT_AWS_SSL_POLICY


class FargateClusterWithLogging(tb_pulumi.ThunderbirdComponentResource):
    """Builds a Fargate cluster running a variable number of tasks. Logs from these tasks will be
    sent to CloudWatch.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        subnets: list[str],
        assign_public_ip: bool = False,
        desired_count: int = 1,
        ecr_resources: list = ['*'],
        enable_container_insights: bool = False,
        health_check_grace_period_seconds: int = None,
        internal: bool = True,
        key_deletion_window_in_days: int = 7,
        security_groups: list[str] = [],
        services: dict = {},
        task_definition: dict = {},
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        """Construct a FargateClusterWithLogging.

        Positional arguments:
            - name: A string identifying this set of resources.
            - project: The ThunderbirdPulumiProject to add these resources to.
            - subnets: A list of subnet IDs to build Fargate containers on. There must be at least
                one subnet to use.

        Keyword arguments:
            - assign_public_ip: When True, containers will receive Internet-facing network
                interfaces. Must be enabled for Fargate-backed containers to talk out to the net.
            - desired_count: The number of containers the service should target to run.
            - ecr_resources: The containers will be granted permissions to pull images from ECR. If
                you would like to restrict these permissions, supply this argument as a list of ARNs
                as they would appear in an IAM Policy.
            - enable_container_insights: When True, enables advanced CloudWatch metrics collection.
            - health_check_grace_period_seconds: Time to wait for a container to come online before
                attempting health checks. This can be used to prevent accidental health check
                failures.
            - internal: Whether traffic should be accepted from the Internet (False) or not (True)
            - key_deletion_window_in_days: Number of days after the KMS key is deleted that it will
                be recoverable. If you need to forcibly delete a key, set this to 0.
            - security_groups: A list of security group IDs to attach to the load balancer.
            - services: A dict defining the ports to use when routing requests to each service. The keys
                should be the name of the service as described in a container definition. The values
                should be dicts supporting the options shown below. If no listenter_port is specified,
                the container_port will be used. The container_name is the name of a container as
                specified in a container definition which can receive this traffic.

                {'web_portal': {
                    'container_port': 8080,
                    'container_name': 'web_backend',
                    'listener_cert_arn': 'arn:aws:acm:region:account:certificate/id',
                    'listener_port': 80,
                    'listener_proto': 'HTTPS',
                    'name': 'Arbitrary name for the ALB; must be unique and no longer than 32 characters.',
                    'health_check': {
                        # Keys match parameters listed here:
                        # https://www.pulumi.com/registry/packages/aws/api-docs/alb/targetgroup/#targetgrouphealthcheck
                    }
                }}

            - task_definition: A dict representing an ECS task definition.
            - opts: Additional pulumi.ResourceOptions to apply to these resources.
            - kwargs: Any other keyword arguments which will be passed as inputs to the
                ThunderbirdComponentResource superconstructor.
        """

        if len(subnets) < 1:
            raise IndexError('You must provide at least one subnet.')

        super().__init__('tb:fargate:FargateClusterWithLogging', name, project, opts=opts, **kwargs)
        family = name

        # Key to encrypt logs
        log_key_tags = {'Name': f'{name}-fargate-logs'}
        log_key_tags.update(self.tags)
        self.resources['log_key'] = aws.kms.Key(
            f'{name}-logging',
            description=f'Key to encrypt logs for {name}',
            deletion_window_in_days=key_deletion_window_in_days,
            tags=log_key_tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Log group
        self.resources['log_group'] = aws.cloudwatch.LogGroup(
            f'{name}-fargate-logs',
            name=f'{name}-fargate-logs',
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Set up an assume role policy
        arp = ASSUME_ROLE_POLICY.copy()
        arp['Statement'][0]['Principal']['Service'] = 'ecs-tasks.amazonaws.com'
        arp = json.dumps(arp)

        # IAM policy for shipping logs
        doc = self.resources['log_group'].arn.apply(
            lambda arn: json.dumps(
                {
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Sid': 'AllowECSLogSending',
                            'Effect': 'Allow',
                            'Action': 'logs:CreateLogGroup',
                            'Resource': arn,
                        }
                    ],
                }
            )
        )
        self.resources['policy_log_sending'] = aws.iam.Policy(
            f'{name}-policy-logs',
            name=f'{name}-logging',
            description='Allows Fargate tasks to log to their log group',
            policy=doc,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[self.resources['log_group']]),
        )

        # IAM policy for accessing container dependencies
        doc = json.dumps(
            {
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Sid': 'AllowSecretsAccess',
                        'Effect': 'Allow',
                        'Action': 'secretsmanager:GetSecretValue',
                        'Resource': f'arn:aws:secretsmanager:{self.project.aws_region}:'
                        f'{self.project.aws_account_id}:'
                        f'secret:{self.project.project}/{self.project.stack}/*',
                    },
                    {
                        'Sid': 'AllowECRAccess',
                        'Effect': 'Allow',
                        'Action': [
                            'ecr:BatchCheckLayerAvailability',
                            'ecr:BatchGetImage',
                            'ecr:DescribeImages',
                            'ecr:GetDownloadUrlForLayer',
                            'ecr:ListImages',
                            'ecr:ListTagsForResource',
                        ],
                        'Resource': ecr_resources,
                    },
                    {
                        'Sid': 'AllowParametersAccess',
                        'Effect': 'Allow',
                        'Action': 'ssm:GetParameters',
                        'Resource': f'arn:aws:ssm:{self.project.aws_region}:{self.project.aws_account_id}:'
                        f'parameter/{self.project.project}/{self.project.stack}/*',
                    },
                ],
            }
        )
        self.resources['policy_exec'] = aws.iam.Policy(
            f'{name}-policy-exec',
            name=f'{name}-exec',
            description=f'Allows {self.project.project} tasks access to resources they need to run',
            policy=doc,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Create an IAM role for tasks to run as
        self.resources['task_role'] = aws.iam.Role(
            f'{name}-taskrole',
            name=name,
            description=f'Task execution role for {self.project.name_prefix}',
            assume_role_policy=arp,
            managed_policy_arns=[
                'arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy',
                self.resources['policy_log_sending'],
                self.resources['policy_exec'],
            ],
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Fargate Cluster
        self.resources['cluster'] = aws.ecs.Cluster(
            f'{name}-cluster',
            opts=pulumi.ResourceOptions(
                parent=self, depends_on=[self.resources['log_key'], self.resources['log_group']]
            ),
            name=name,
            configuration={
                'executeCommandConfiguration': {
                    'kmsKeyId': self.resources['log_key'].arn,
                    'logging': 'OVERRIDE',
                    'logConfiguration': {
                        'cloudWatchEncryptionEnabled': True,
                        'cloudWatchLogGroupName': self.resources['log_group'].name,
                    },
                }
            },
            settings=[{'name': 'containerInsights', 'value': 'enabled' if enable_container_insights else 'disabled'}],
            tags=self.tags,
        )

        # Prep the task definition
        self.resources['task_definition'] = pulumi.Output.all(
            self.resources['log_group'].name, self.project.aws_region, self.resources['task_role'].arn
        ).apply(lambda outputs: self.task_definition(task_definition, family, outputs[0], outputs[1]))

        # Build ALBs and related resources to route traffic to our services
        fsalb_name = f'{name}-fargateservicealb'
        self.resources['fargate_service_alb'] = FargateServiceAlb(
            fsalb_name,
            project,
            subnets=subnets,
            internal=internal,
            security_groups=security_groups,
            services=services,
            opts=pulumi.ResourceOptions(parent=self),
        ).resources

        # We only need one Fargate Service config, but that might have multiple load balancer
        # configs. Build those now.
        lb_configs = [
            {
                'targetGroupArn': self.resources['fargate_service_alb']['target_groups'][svc_name].arn,
                'containerName': svc['container_name'],
                'containerPort': svc['container_port'],
            }
            for svc_name, svc in services.items()
        ]

        # Fargate Service
        self.resources['service'] = aws.ecs.Service(
            f'{name}-service',
            name=name,
            cluster=self.resources['cluster'].id,
            desired_count=desired_count,
            health_check_grace_period_seconds=health_check_grace_period_seconds,
            launch_type='FARGATE',
            load_balancers=lb_configs,
            network_configuration={
                'subnets': subnets,
                'assign_public_ip': assign_public_ip,
                'security_groups': security_groups,
            },
            task_definition=self.resources['task_definition'],
            tags=self.tags,
            opts=pulumi.ResourceOptions(
                parent=self, depends_on=[self.resources['cluster'], self.resources['task_definition']]
            ),
        )

        self.finish()

    def task_definition(
        self,
        task_def: dict,
        family: str,
        log_group_name: str,
        aws_region: str,
    ) -> aws.ecs.TaskDefinition:
        """Returns an ECS task definition resource.

        - task_def: A dict defining the task definition template which needs modification.
        - family: A unique name for the task definition.
        - log_group_name: Name of the log group to ship logs to.
        - aws_region: AWS region to build in.
        """

        for cont_name, cont_def in task_def['container_definitions'].items():
            # If not overridden, inject a default log configuration
            if 'logConfiguration' not in cont_def:
                cont_def['logConfiguration'] = {
                    'logDriver': 'awslogs',
                    'options': {
                        'awslogs-group': log_group_name,
                        'awslogs-create-group': 'true',
                        'awslogs-region': aws_region,
                        'awslogs-stream-prefix': 'ecs',
                    },
                }
            cont_def['name'] = cont_name

        # Convert container defs into list
        cont_defs = [v for k, v in task_def['container_definitions'].items()]

        task_def.update(
            {
                'execution_role_arn': self.resources['task_role'].arn,
                'family': family,
                'container_definitions': json.dumps(cont_defs),
            }
        )

        return aws.ecs.TaskDefinition(
            f'{family}-taskdef',
            opts=pulumi.ResourceOptions(parent=self, depends_on=[self.resources['log_group']]),
            **task_def,
        )


class FargateServiceAlb(tb_pulumi.ThunderbirdComponentResource):
    """Builds an ALB with all of its constituent components to serve traffic for a set of ECS
    services. ECS does not allow reuse of a single ALB with multiple listeners, so if there are
    multiple services, multiple ALBs will be constructed.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        subnets: list[pulumi.Output],
        internal: bool = True,
        security_groups: list[str] = [],
        services: dict = {},
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        """Construct an ApplicationLoadBalancer.

        Positional arguments:
            - name: A string identifying this set of resources.
            - project: The ThunderbirdPulumiProject to add these resources to.
            - subnets: A list of subnet resources (pulumi outputs) to attach the ALB to.

        Keyword arguments:
            - internal: Whether traffic should be accepted from the Internet (False) or not (True).
            - security_groups: A list of security group IDs to attach to the load balancer.
            - services: A dict defining the ports to use when routing requests to each service. The
                keys should be the name of the service as described in a container definition. The
                values should be dicts supporting the options shown below. If no listenter_port is
                specified, the container_port will be used. The name field is mandatory because we
                have to get around a 32-character limit for naming things, and the generated names
                are far too long and result in namespace collisions when automatically shortened.

                {'web_portal': {
                    'container_port': 8080,
                    'container_name': 'web_backend',
                    'listener_cert_arn': 'arn:aws:acm:region:account:certificate/id',
                    'listener_port': 80,
                    'listener_proto': 'HTTPS',
                    'name': 'Arbitrary name for the ALB; must be unique and no longer than 32 characters.',
                    'health_check': {
                        # Keys match parameters listed here:
                        # https://www.pulumi.com/registry/packages/aws/api-docs/alb/targetgroup/#targetgrouphealthcheck
                    }
                }}

            - opts: Additional pulumi.ResourceOptions to apply to these resources.
            - kwargs: Any other keyword arguments which will be passed as inputs to the
                ThunderbirdComponentResource superconstructor.
        """

        super().__init__('tb:fargate:FargateServiceAlb', name, project, opts=opts, **kwargs)

        # We'll track these per-service
        self.resources['albs'] = {}
        self.resources['listeners'] = {}
        self.resources['target_groups'] = {}

        # For each service...
        for svc_name, svc in services.items():
            # Determine SSL settings based on other values
            listener_proto = svc['listener_proto'] if 'listener_proto' in svc else 'HTTP'
            ssl_policy = None
            if 'ssl_policy' in svc:
                ssl_policy = svc['ssl_policy']
            else:
                if listener_proto == 'HTTPS':
                    ssl_policy = DEFAULT_AWS_SSL_POLICY

            # Add special tagging to these resources to identify the service they're built for
            svc_tags = {'service': svc_name}
            svc_tags.update(self.tags)

            # Build the load balancer first; we'll need it for everything else
            # TODO: Support access logging; AWS only supports S3 buckets, not apparently CloudWatch
            self.resources['albs'][svc_name] = aws.lb.LoadBalancer(
                f'{name}-alb-{svc_name}',
                # AWS imposes a 32-character limit on service names. Simply cropping the name length
                # down is insufficient because it creates name conflicts. So these are explicitly
                # named in our configs.
                name=svc['name'],
                internal=internal,
                load_balancer_type='application',
                security_groups=security_groups,
                subnets=[subnet.id for subnet in subnets],
                tags=self.tags,
                opts=pulumi.ResourceOptions(parent=self),
            )

            # Build a target group
            tg_name = f'{name}-targetgroup-{svc_name}'
            self.resources['target_groups'][svc_name] = aws.alb.TargetGroup(
                tg_name,
                # AWS imposes a 32-character limit on service names. Simply cropping the name length
                # down is insufficient because it creates name conflicts. So these are explicitly
                # named in our configs.
                health_check=svc['health_check'] if 'health_check' in svc else None,
                name=svc['name'],
                port=svc['container_port'],
                protocol='HTTP',
                vpc_id=subnets[0].vpc_id,
                # Next two options are required for ECS services; ref:
                # https://docs.aws.amazon.com/AmazonECS/latest/developerguide/alb.html
                target_type='ip',
                ip_address_type='ipv4',
                tags=svc_tags,
                opts=pulumi.ResourceOptions(parent=self),
            )

            # Build a listener for the target group
            self.resources['listeners'][svc_name] = aws.lb.Listener(
                f'{name}-listener-{svc_name}',
                certificate_arn=svc['listener_cert_arn'] if 'listener_cert_arn' in svc else None,
                default_actions=[{'type': 'forward', 'targetGroupArn': self.resources['target_groups'][svc_name].arn}],
                load_balancer_arn=self.resources['albs'][svc_name].arn,
                port=svc['listener_port'] if 'listener_port' in svc else svc['container_port'],
                protocol=listener_proto,
                ssl_policy=ssl_policy,
                tags=svc_tags,
                opts=pulumi.ResourceOptions(parent=self),
            )

        self.finish()
