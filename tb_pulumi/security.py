"""Patterns related to continuous integration."""

import json
import pulumi
import pulumi_aws as aws
import tb_pulumi

class SecurityHub(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:security:SecurityHub``
    Enable and Configure AWS SecurityHub for an account/region.

    Produces the following ``resources``:

    """

    def __init(
        self,
        project: tb_pulumi.ThunderbirdPulumiProject,
        region: str,
        name: str = 'securityhub',
        enable_default_standards: bool = True,
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
        **kwargs,
    ):
        if 'exclude_from_project' in kwargs:
            exclude_from_project = kwargs['exclude_from_project'] or False
            del kwargs['exclude_from_project']

        super().__init__(
            'tb:security:SecurityHub',
            name=name,
            project=project,
            exclude_from_project=exclude_from_project,
            opts=opts,
            tags=tags,
        )
    
        security_hub = aws.security_hub.SecurityHub(
            f'{name}',
            enable_default_standards=enable_default_standards,
            opts=pulumi.ResourceOptions(region)
        )