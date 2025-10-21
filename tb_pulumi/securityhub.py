"""Patterns related to continuous integration."""

# import json
import pulumi
import pulumi_aws as aws
import tb_pulumi


class SecurityHubAccount(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:securityhub:SecurityHubAccount``
    Enable and Configure AWS SecurityHub for an account/region.

    Produces the following ``resources``:

    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
        **kwargs,
    ):
        exclude_from_project = kwargs.pop('exclude_from_project', False)
        if 'exclude_from_project' in kwargs:
            exclude_from_project = kwargs['exclude_from_project'] or False
            del kwargs['exclude_from_project']

        super().__init__(
            'tb:securityhub:SecurityHubAccount',
            name=f'{name}-sechubacc',
            project=project,
            exclude_from_project=exclude_from_project,
            opts=opts,
            tags=tags,
        )

        security_hub_account = aws.securityhub.Account(f'{name}', opts=pulumi.ResourceOptions())

        self.finish(resources={'security_hub_account': security_hub_account})
