"""Infrastructural patterns related to `AWS Fargate
<https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html>`_."""

import json
import pulumi
import pulumi_aws as aws
import tb_pulumi

from tb_pulumi.constants import ASSUME_ROLE_POLICY, DEFAULT_AWS_SSL_POLICY


class FargateClusterWithLogging(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:fargate:FargateClusterWithLogging``

    Builds a Fargate cluster running a variable number of tasks. Logs from these tasks will be
    sent to CloudWatch.

    Produces the following ``resources``:

        - *cluster* - The `aws.ecs.Cluster <https://www.pulumi.com/registry/packages/aws/api-docs/ecs/cluster/>`_.
        - *log_group* - `aws.cloudwatch.LogGroup
          <https://www.pulumi.com/registry/packages/aws/api-docs/cloudwatch/loggroup/>`_ where these tasks send their
          logs.
        - *log_key* - `aws.kms.Key <https://www.pulumi.com/registry/packages/aws/api-docs/kms/key/>`_ used to encrypt
          log contents.
        - *fargate_service_alb* - :py:class:`tb_pulumi.fargate.FargateServiceAlb` balancing traffic between these tasks.
        - *policy_exec* - `aws.iam.Policy <https://www.pulumi.com/registry/packages/aws/api-docs/iam/policy/>`_ allowing
          the service access to other resources needed to launch tasks.
        - *policy_log_sending* - `aws.iam.Policy <https://www.pulumi.com/registry/packages/aws/api-docs/iam/policy/>`_
          allowing tasks to send logs to their log group.
        - *service* - `aws.ecs.Service <https://www.pulumi.com/registry/packages/aws/api-docs/ecs/service/>`_ managing
          the tasks.
        - *task_role* - `aws.iam.Role <https://www.pulumi.com/registry/packages/aws/api-docs/iam/role/>`_ used for
          executing tasks in this cluster.
        - *task_definition* - `aws.ecs.TaskDefinition
          <https://www.pulumi.com/registry/packages/aws/api-docs/ecs/taskdefinition/>`_ describing the properties of the
          tasks being managed.

    :param name: A string identifying this set of resources.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param subnets: A list of subnet IDs to build Fargate containers on. There must be at least one subnet to use.
    :type subnets: list[str]

    :param assign_public_ip: When True, containers will receive Internet-facing network interfaces. Must be enabled for
        Fargate-backed containers to talk out to the net. Defaults to False.
    :type assign_public_ip: bool, optional

    :param build_load_balancer: When True, an Application Load Balancer will be created to route traffic to your Fargate
        containers. Defaults to True.
    :type build_load_balancer: bool, optional

    :param container_security_groups: List of security group IDs which will attach to the containers/tasks running in
        this cluster. Defaults to [].
    :type container_security_groups: list[str], optional

    :param desired_count: The number of containers the service should target to run. Defaults to 1.
    :type desired_count: int, optional

    :param ecr_resources: The containers will be granted permissions to pull images from ECR. If you would like to
        restrict these permissions, supply this argument as a list of ARNs as they would appear in an IAM Policy.
        Defaults to ['*'].
    :type ecr_resources: list, optional

    :param enable_container_insights: When True, enables advanced CloudWatch metrics collection. Defaults to False.
    :type enable_container_insights: bool, optional

    :param health_check_grace_period_seconds: Time to wait for a container to come online before attempting health
        checks. This can be used to prevent accidental health check failures. Defaults to None.
    :type health_check_grace_period_seconds: int, optional

    :param internal: Whether traffic should be accepted from the Internet (False) or not (True). Defaults to True.
    :type internal: bool, optional

    :param key_deletion_window_in_days: Number of days after the KMS key is deleted that it will be recoverable. If you
        need to forcibly delete a key, set this to 0. Defaults to 7.
    :type key_deletion_window_in_days: int, optional

    :param load_balancer_security_groups: List of security group IDs which will attach to the load balancers created for
        these services.
    :type load_balancer_security_groups: list[str], optional

    :param services: A dict defining the ports to use when routing requests to each service. The keys should be the name
        of the service as described in a container definition. The values should be dicts supporting the options shown
        below. If no ``listenter_port`` is specified, the ``container_port`` will be used. The ``container_name`` is the
        name of a container as specified in a container definition which can receive this traffic.
        ::

                {'web_portal': {
                    'container_port': 8080,
                    'container_name': 'web_backend',
                    'listener_cert_arn': 'arn:aws:acm:region:account:certificate/id',
                    'listener_port': 443,
                    'listener_proto': 'HTTPS',
                    'name': 'Arbitrary name for the ALB; must be unique and no longer than 32 characters.',
                    'health_check': {
                        # Keys match parameters listed here:
                        # https://www.pulumi.com/registry/packages/aws/api-docs/alb/targetgroup/#targetgrouphealthcheck
                    }
                }}

        Defaults to {}.
    :type services: dict, optional

    :param task_definition: A dict representing an ECS task definition. Defaults to {}.
    :type task_definition: dict, optional

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param kwargs: Any other keyword arguments which will be passed as inputs to the ThunderbirdComponentResource
        superconstructor.

    :raises IndexError: Thrown if the list of `subnets` is empty.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        subnets: list[str],
        assign_public_ip: bool = False,
        build_load_balancer: bool = True,
        container_security_groups: list[str] = [],
        desired_count: int = None,
        ecr_resources: list = ['*'],
        enable_container_insights: bool = False,
        health_check_grace_period_seconds: int = None,
        internal: bool = True,
        key_deletion_window_in_days: int = 7,
        load_balancer_security_groups: list[str] = [],
        services: dict = {},
        task_definition: dict = {},
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        if len(subnets) < 1:
            raise IndexError('You must provide at least one subnet.')

        super().__init__('tb:fargate:FargateClusterWithLogging', name, project, opts=opts, **kwargs)
        family = name

        # Key to encrypt logs
        log_key_tags = {'Name': f'{name}-fargate-logs'}
        log_key_tags.update(self.tags)
        log_key = aws.kms.Key(
            f'{name}-logging',
            description=f'Key to encrypt logs for {name}',
            deletion_window_in_days=key_deletion_window_in_days,
            tags=log_key_tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Log group
        log_group = aws.cloudwatch.LogGroup(
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
        log_doc = log_group.arn.apply(
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
        policy_log_sending = aws.iam.Policy(
            f'{name}-policy-logs',
            name=f'{name}-logging',
            description='Allows Fargate tasks to log to their log group',
            policy=log_doc,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[log_group]),
            tags=self.tags,
        )

        # IAM policy for accessing container dependencies
        container_doc = json.dumps(
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
        policy_exec = aws.iam.Policy(
            f'{name}-policy-exec',
            name=f'{name}-exec',
            description=f'Allows {self.project.project} tasks access to resources they need to run',
            policy=container_doc,
            opts=pulumi.ResourceOptions(parent=self),
            tags=self.tags,
        )

        # Create an IAM role for tasks to run as
        task_role = aws.iam.Role(
            f'{name}-taskrole',
            name=name,
            description=f'Task execution role for {self.project.name_prefix}',
            assume_role_policy=arp,
            managed_policy_arns=[
                'arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy',
                policy_log_sending,
                policy_exec,
            ],
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[policy_exec, policy_log_sending]),
        )

        # Fargate Cluster
        cluster = aws.ecs.Cluster(
            f'{name}-cluster',
            name=name,
            configuration={
                'executeCommandConfiguration': {
                    'kmsKeyId': log_key.arn,
                    'logging': 'OVERRIDE',
                    'logConfiguration': {
                        'cloudWatchEncryptionEnabled': True,
                        'cloudWatchLogGroupName': log_group.name,
                    },
                }
            },
            settings=[{'name': 'containerInsights', 'value': 'enabled' if enable_container_insights else 'disabled'}],
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[log_key, log_group]),
        )

        # Prep the task definition
        task_definition_res = pulumi.Output.all(
            log_group.name,
            self.project.aws_region,
            task_role.arn,
        ).apply(
            lambda outputs: self.task_definition(
                task_def=task_definition,
                family=family,
                log_group_name=outputs[0],
                aws_region=outputs[1],
                task_role_arn=outputs[2],
                tags=self.tags,
                dependencies=[log_group, task_role],
            )
        )

        # Build ALBs and related resources to route traffic to our services. Perhaps unintuitively, the Service is
        # dependent upon load balancers, not the other way around, since it must manipulate their configs to match the
        # IP addresses of the running containers.
        fsalb_name = f'{name}-fargateservicealb'
        fargate_service_alb = (
            FargateServiceAlb(
                fsalb_name,
                project,
                subnets=subnets,
                exclude_from_project=True,
                internal=internal,
                security_groups=load_balancer_security_groups,
                services=services,
                opts=pulumi.ResourceOptions(parent=self),
                tags=self.tags,
            )
            if build_load_balancer
            else None
        )

        # We only need one Fargate Service config, but that might have multiple load balancer
        # configs. Build those now.
        lb_configs = (
            [
                {
                    'targetGroupArn': fargate_service_alb.resources['target_groups'][svc_name].arn,
                    'containerName': svc['container_name'],
                    'containerPort': svc['container_port'],
                }
                for svc_name, svc in services.items()
            ]
            if build_load_balancer
            else None
        )

        # Fargate Service
        service_depends_on = [item for item in [cluster, fargate_service_alb, task_definition_res] if item is not None]
        service_opts = {
            'parent': self,
            'depends_on': service_depends_on,
        }
        if not desired_count:
            service_opts['ignore_changes'] = ['desired_count']
        service = aws.ecs.Service(
            f'{name}-service',
            name=name,
            cluster=cluster.id,
            desired_count=desired_count,
            health_check_grace_period_seconds=health_check_grace_period_seconds,
            launch_type='FARGATE',
            load_balancers=lb_configs,
            network_configuration={
                'subnets': subnets,
                'assign_public_ip': assign_public_ip,
                'security_groups': container_security_groups,
            },
            task_definition=task_definition_res,
            propagate_tags='SERVICE',
            tags=self.tags,
            opts=pulumi.ResourceOptions(**service_opts),
        )

        self.finish(
            resources={
                'cluster': cluster,
                'log_group': log_group,
                'log_key': log_key,
                'fargate_service_alb': fargate_service_alb,
                'policy_exec': policy_exec,
                'policy_log_sending': policy_log_sending,
                'service': service,
                'task_role': task_role,
                'task_definition': task_definition_res,
            },
        )

    def task_definition(
        self,
        task_def: dict,
        family: str,
        log_group_name: str,
        aws_region: str,
        tags: dict,
        task_role_arn: str,
        dependencies: list[pulumi.Resource] = [],
    ) -> aws.ecs.TaskDefinition:
        """Returns an ECS task definition resource.

        :param task_def: A dict defining the task definition template which needs modification.
        :type task_def: dict

        :param family: A unique name for the task definition.
        :type family: str

        :param log_group_name: Name of the log group to ship logs to.
        :type log_group_name: str

        :param aws_region: AWS region to build in.
        :type aws_region: str

        :param tags: Key/value pairs to merge with the default tags which get applied to all resources in this group.
            Defaults to {}.
        :type tags: dict, optional

        :param task_role_arn: ARN of the IAM role the task will run as.
        :type task_role_arn: str

        :param dependencies: List of Resources this task definition is dependent upon.
        :type dependencies: list[pulumi.Resource]

        :return: A TaskDefinition Resource
        :rtype: aws.ecs.TaskDefinition
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
                'execution_role_arn': task_role_arn,
                'family': family,
                'container_definitions': json.dumps(cont_defs),
            }
        )

        task_def_res = aws.ecs.TaskDefinition(
            f'{family}-taskdef',
            opts=pulumi.ResourceOptions(parent=self, depends_on=[*dependencies]),
            tags=tags,
            **task_def,
        )

        return task_def_res


class FargateServiceAlb(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:fargate:FargateServiceAlb``

    Builds an ALB with all of its constituent components to serve traffic for a set of ECS
    services. ECS does not allow reuse of a single ALB with multiple listeners, so if there are
    multiple services, multiple ALBs will be constructed.

    Produces the following ``resources``:

        - *albs* - Dict where the keys match the keys of the ``services`` parameter and the values are the
          `aws.lb.LoadBalancers <https://www.pulumi.com/registry/packages/aws/api-docs/lb/loadbalancer/>`_ created for
          those services.
        - *listeners* - Dict where the keys match the keys of the ``services`` parameter and the values are the
          `aws.lb.Listeners <https://www.pulumi.com/registry/packages/aws/api-docs/lb/listener/>`_ created for the
          load balancers for those services.
        - *target_groups* - Dict where the keys match the keys of the ``services`` parameter and the values are the
          `aws.lb.TargetGroups <https://www.pulumi.com/registry/packages/aws/api-docs/lb/targetgroup/>`_ created for the
          listeners for those services. Importantly, Fargate services manage their own targets, so this module does not
          track any target group attachments.

    :param name: A string identifying this set of resources.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param subnets: A list of subnet resources (pulumi outputs) to attach the ALB to.
    :type subnets: list[pulumi.Output]

    :param internal: Whether traffic should be accepted from the Internet (False) or not (True). Defaults to True.
    :type internal: bool, optional

    :param security_groups: A list of security group IDs to attach to the load balancer. Defaults to [].
    :type security_groups: list[str], optional

    :param services: A dict defining the ports to use when routing requests to each service. The keys should be the name
        of the service as described in a container definition. The values should be dicts supporting the options shown
        below. If no ``listenter_port`` is specified, the ``container_port`` will be used. The ``container_name`` is the
        name of a container as specified in a container definition which can receive this traffic.
        ::

                {'web_portal': {
                    'container_port': 8080,
                    'container_name': 'web_backend',
                    'listener_cert_arn': 'arn:aws:acm:region:account:certificate/id',
                    'listener_port': 443,
                    'listener_proto': 'HTTPS',
                    'name': 'Arbitrary name for the ALB; must be unique and no longer than 32 characters.',
                    'health_check': {
                        # Keys match parameters listed here:
                        # https://www.pulumi.com/registry/packages/aws/api-docs/alb/targetgroup/#targetgrouphealthcheck
                    }
                }}

        Defaults to {}.
    :type services: dict, optional

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param kwargs: Any other keyword arguments which will be passed as inputs to the ThunderbirdComponentResource
        superconstructor.
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
        super().__init__('tb:fargate:FargateServiceAlb', name, project, opts=opts, **kwargs)

        # We'll track these per-service
        albs = {}
        listeners = {}
        target_groups = {}

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
            albs[svc_name] = aws.lb.LoadBalancer(
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
                opts=pulumi.ResourceOptions(parent=self, depends_on=[*subnets]),
            )

            # Build a target group
            tg_name = f'{name}-targetgroup-{svc_name}'
            target_groups[svc_name] = aws.alb.TargetGroup(
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
                opts=pulumi.ResourceOptions(parent=self, depends_on=[subnets[0]]),
            )

            # Build a listener for the target group
            listeners[svc_name] = aws.lb.Listener(
                f'{name}-listener-{svc_name}',
                certificate_arn=svc['listener_cert_arn'] if 'listener_cert_arn' in svc else None,
                default_actions=[{'type': 'forward', 'targetGroupArn': target_groups[svc_name].arn}],
                load_balancer_arn=albs[svc_name].arn,
                port=svc['listener_port'] if 'listener_port' in svc else svc['container_port'],
                protocol=listener_proto,
                ssl_policy=ssl_policy,
                tags=svc_tags,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[albs[svc_name]]),
            )

        self.finish(resources={'albs': albs, 'listeners': listeners, 'target_groups': target_groups})
