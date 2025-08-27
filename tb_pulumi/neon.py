"""Infrastructural patterns related to N seon PrivateLink."""

import pulumi
import pulumi_aws as aws
import tb_pulumi
import pulumi_neon as neon


class NeonVpcAssignment(tb_pulumi.ThunderbirdComponentResource):
    """Assigns a VPC to a Neon PrivateLink endpoint service.

    Args:
        name: The name of the resource.
        vpc_id: The ID of the VPC to assign.
        service_id: The ID of the Neon PrivateLink endpoint service.
        opts: Optional resource options.
    """

    def __init__(
            self,
            name: str,
            project: tb_pulumi.ThunderbirdPulumiProject,
            org_id: pulumi.Input[str],
            region_id: pulumi.Input[str],
            vpc_endpoint_id: pulumi.Input[str],
            opts: pulumi.ResourceOptions = None,
            **kwargs,
            ):
        super().__init__('tb_pulumi:NeonVpcAssignment', name, project, opts=opts, **kwargs)

        assignment = neon.VpcEndpointAssignment(
            f'{name}',
            org_id = org_id,
            region_id = region_id,
            vpc_endpoint_id = vpc_endpoint_id,
            label = f'{name}',
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.finish(
            resources={
                'assignment': assignment,
            },
        )

class NeonVpcEndpointRestriction(tb_pulumi.ThunderbirdComponentResource):
    """Restricts a Neon PrivateLink endpoint to a specific VPC.

    Args:
        name: The name of the resource.
        vpc_id: The ID of the VPC to restrict.
        service_id: The ID of the Neon PrivateLink endpoint service.
        opts: Optional resource options.
    """

    def __init__(
            self,
            name: str,
            project: tb_pulumi.ThunderbirdPulumiProject,
            neon_project_id: pulumi.Input[str],
            vpc_endpoint_id: pulumi.Input[str],
            opts: pulumi.ResourceOptions = None,
            **kwargs,
            ):
        super().__init__('tb_pulumi:NeonVpcEndpointRestriction', name, project, opts=opts, **kwargs)

        restriction = neon.VpcEndpointRestriction(
            f'{name}',
            project_id = neon_project_id,
            vpc_endpoint_id = vpc_endpoint_id,
            label = f'{name}',
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.finish(
            resources={
                'label': restriction.label.apply(lambda label: f'{label}'),
            },
        )

