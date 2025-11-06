"""Patterns related to continuous integration."""

# import json
import pulumi
import pulumi_aws as aws
import tb_pulumi


class SecurityHubAccount(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:securityhub:SecurityHubAccount``

    Enable and configure AWS Security Hub for an account/region.

    Produces the following ``resources``:

    - *securityhub_account* - `aws.securityhub.Account
    <https://www.pulumi.com/registry/packages/aws/api-docs/securityhub/account/>`_
    The Security Hub account resource for the account/region.
    - *member* - `aws.securityhub.Member
    <https://www.pulumi.com/registry/packages/aws/api-docs/securityhub/member/>`_
    The Security Hub member resource (if organization is enabled).
    - *invite_accepter* - `aws.securityhub.InviteAccepter
    <https://www.pulumi.com/registry/packages/aws/api-docs/securityhub/inviteaccepter/>`_
    The Security Hub invite accepter (if organization is enabled).

    :param name: A string identifying this set of resources.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param organization: Whether this account is part of a Security Hub organization.
    :type organization: bool

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param tags: Tags to apply to the resources.
    :type tags: dict
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
