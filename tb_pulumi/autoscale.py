"""Infrastructural patterns related to `AWS Application Autoscaling <https://docs.aws.amazon.com/autoscaling/>`_."""

import pulumi
import pulumi_aws as aws
import tb_pulumi


class EcsServiceAutoscaler(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:autoscale:EcsServiceAutoscaler``

    Builds an autoscaler for an ECS Service.

    Produces the following ``resources``:

        - *cpu_policy* - The `aws.appautoscaling.Policy
          <https://www.pulumi.com/registry/packages/aws/api-docs/appautoscaling/policy/>`_ tracking average CPU usage.
        - *ram_policy* - The `aws.appautoscaling.Policy
          <https://www.pulumi.com/registry/packages/aws/api-docs/appautoscaling/policy/>`_ tracking average memory
          usage.
        - *target* - The `aws.appautoscaling.Target
          <https://www.pulumi.com/registry/packages/aws/api-docs/appautoscaling/target/>`_ describing the service and
          scaling settings.

    :param name: A string identifying this set of resources.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param service: The `aws.ecs.Service <https://www.pulumi.com/registry/packages/aws/api-docs/ecs/service/>`_ to build
        this autoscaler for.
    :type service: aws.ecs.Service

    :param cpu_threshold: Point at which we scale based on the average CPU consumption across service containers.
      Defaults to 70.
    :type cpu_threshold: int, optional

    :param cooldown: Number of seconds to wait between scaling events, used to prevent rapid fluctuations in capacity.
      Defaults to 300.
    :type cooldown: int, optional

    :param disable_scale_in: When True, prevents the cluster from scaling in while still allowing scale-outs. Defaults
        to False.
    :type disable_scale_in: bool, optional

    :param max_capacity: Maximum number of containers to run in the cluster. Defaults to 2.
    :type max_capacity: int, optional

    :param min_capacity: Minimum number of containers to run in the cluster. Defaults to 1.
    :type min_capacity: int, optional

    :param ram_threshold: Point at which we scale based on the average memory usage across service containers. Defaults
        to 70.
    :type ram_threshold: int, optional

    :param suspend: When True, suspends all scaling operations. Defaults to False.
    :type suspend: bool, optional

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param kwargs: Any other keyword arguments which will be passed as inputs to the ThunderbirdComponentResource
        superconstructor.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        service: aws.ecs.Service,
        cpu_threshold: int = 70,
        cooldown: int = 300,
        disable_scale_in: bool = False,
        max_capacity: int = 2,
        min_capacity: int = 1,
        ram_threshold: int = 70,
        suspend: bool = False,
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        super().__init__(
            pulumi_type='tb:autoscale:EcsServiceAutoscaler', name=name, project=project, opts=opts, **kwargs
        )

        def __build_autoscaling(cluster_name, service_name):
            # That cluster_name is actually an ARN (bug in AWS provider, maybe?)
            cluster_name = cluster_name.split('/').pop()
            service_resource_id = f'service/{cluster_name}/{service_name}'
            pulumi.info(f'DEBUG -- rjung -- suspend: {type(suspend)}')
            target = aws.appautoscaling.Target(
                f'{self.name}-scltgt-{service_name}',
                resource_id=service_resource_id,
                scalable_dimension='ecs:service:DesiredCount',
                service_namespace='ecs',
                min_capacity=min_capacity,
                max_capacity=max_capacity,
                suspended_state={
                    'dynamic_scaling_in_suspended': suspend or disable_scale_in,
                    'dynamic_scaling_out_suspended': suspend,
                    'scheduled_scaling_suspended': suspend,
                },
                tags=self.tags,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[service]),
            )

            cpu_policy_opts = {
                'resource_id': service_resource_id,
                'scalable_dimension': 'ecs:service:DesiredCount',
                'service_namespace': 'ecs',
                'name': f'{service_name}-cpu',
                'policy_type': 'TargetTrackingScaling',
                'target_tracking_scaling_policy_configuration': {
                    'target_value': cpu_threshold,
                    'disable_scale_in': disable_scale_in,
                    'predefined_metric_specification': {
                        'predefined_metric_type': 'ECSServiceAverageCPUUtilization',
                    },
                    'scale_in_cooldown': cooldown,
                    'scale_out_cooldown': cooldown,
                },
            }

            ram_policy_opts = {
                'resource_id': service_resource_id,
                'scalable_dimension': 'ecs:service:DesiredCount',
                'service_namespace': 'ecs',
                'name': f'{service_name}-ram',
                'policy_type': 'TargetTrackingScaling',
                'target_tracking_scaling_policy_configuration': {
                    'target_value': ram_threshold,
                    'disable_scale_in': disable_scale_in,
                    'predefined_metric_specification': {
                        'predefined_metric_type': 'ECSServiceAverageMemoryUtilization',
                    },
                    'scale_in_cooldown': cooldown,
                    'scale_out_cooldown': cooldown,
                },
            }

            cpu_policy = aws.appautoscaling.Policy(
                f'{self.name}-sclpol-cpu',
                **cpu_policy_opts,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[service, target]),
            )

            ram_policy = aws.appautoscaling.Policy(
                f'{self.name}-sclpol-ram',
                **ram_policy_opts,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[service, target]),
            )

            self.finish(resources={'cpu_policy': cpu_policy, 'ram_policy': ram_policy, 'target': target})

        pulumi.Output.all(service.cluster, service.name).apply(lambda outputs: __build_autoscaling(*outputs))
