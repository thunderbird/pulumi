"""Standardization library for the usage of Pulumi in Python at Thunderbird. For an overview of how
to use this library, read the README: https://github.com/thunderbird/pulumi/blob/main/README.md
"""

import boto3
import pulumi
import yaml

from functools import cached_property
from os import environ, getlogin
from socket import gethostname
from tb_pulumi.constants import DEFAULT_PROTECTED_STACKS


class ThunderbirdPulumiProject:
    """Manages Pulumi resources at Thunderbird. This class enforces some usage conventions that help
    keep us organized and consistent.
    """

    def __init__(self, protected_stacks: list[str] = DEFAULT_PROTECTED_STACKS):
        """Construct a ThunderbirdPulumiProject.

        - protected_stacks: List of stack names which should require explicit instruction to
        modify.
        """

        # General runtime data
        self.project = pulumi.get_project()
        self.stack = pulumi.get_stack()
        self.name_prefix = f'{self.project}-{self.stack}'
        self.protected_stacks = protected_stacks
        self.pulumi_config = pulumi.Config()
        self.resources = {}
        self.common_tags = {
            'project': self.project,
            'pulumi_last_run_by': f'{getlogin()}@{gethostname()}',
            'pulumi_project': self.project,
            'pulumi_stack': self.stack,
        }

        # AWS client setup
        self.__aws_clients = {}
        self.__aws_session = boto3.session.Session()
        sts = self.get_aws_client('sts')
        self.aws_account_id = sts.get_caller_identity()['Account']
        self.aws_region = self.__aws_session.region_name

    def get_aws_client(self, service: str):
        """Retrieves an AWS client for the requested service, preferably from the cache.

        - service: Name of the service as described in boto3 docs: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/index.html
        """
        if service not in self.__aws_clients.keys():
            self.__aws_clients[service] = self.__aws_session.client(service)

        return self.__aws_clients[service]

    @cached_property
    def config(self) -> dict:
        """Provides read-only access to the project configuration"""

        config_file = f'config.{self.stack}.yaml'
        with open(config_file, 'r') as fh:
            return yaml.load(fh.read(), Loader=yaml.SafeLoader)


class ThunderbirdComponentResource(pulumi.ComponentResource):
    """A special kind of pulumi.ComponentResource which handles common aspects of our resources such
    as naming, tagging, and internal resource organization in code.
    """

    def __init__(
        self,
        pulumi_type: str,
        name: str,
        project: ThunderbirdPulumiProject,
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
    ):
        """Construct a ThunderbirdComponentResource.

        - pulumi_type: The "type" string (commonly referred to in docs as just "t") of the component
            as described by Pulumi's docs here:
            https://www.pulumi.com/docs/concepts/resources/names/#types
        - name: A string identifying this set of resources.
        - project: The ThunderbirdPulumiProject this resource belongs to.
        - opts: Additional pulumi.ResourceOptions to apply to this resource.
        - tags: Key/value pairs to merge with the default tags which get applied to all resources in
            this group.
        """
        self.name = name
        self.project = project

        if self.protect_resources:
            pulumi.info(
                f'Resource protection has been enabled on {name}. '
                'To disable, export TBPULUMI_DISABLE_PROTECTION=True'
            )

        # Merge provided opts with defaults before calling superconstructor
        default_opts = pulumi.ResourceOptions(protect=self.protect_resources)
        final_opts = default_opts.merge(opts)
        super().__init__(t=pulumi_type, name=name, opts=final_opts)

        self.tags = self.project.common_tags.copy()
        self.tags.update(tags)

        self.resources = {}

    def finish(self):
        """Registers outputs based on the contents of `self.resources` and adds those resources to
        the project's internal tracking. All implementations of this class should call this function
        at the end of their __init__ functions.
        """

        # Register outputs both with the ThunderbirdPulumiProject and Pulumi itself
        self.project.resources[self.name] = self.resources
        self.register_outputs({k: self.resources[k] for k in self.resources.keys()})

    @property
    def protect_resources(self) -> bool:
        """Sets or unsets resource protection on the stack based on operating conditions."""

        if self.project.stack not in self.project.protected_stacks:
            protect = False
        else:
            protect = not env_var_is_true('TBPULUMI_DISABLE_PROTECTION')

        return protect


def env_var_matches(name: str, matches: list[str], default: bool = False) -> bool:
    """Determines if the value of the given environment variable is in the given list. Returns True
    if it does, otherwise the `default` value. This is a case-insensitive check. Returns None if the
    variable is unset.

        - name: The environment variable to check
        - matches: A list of strings to match against
        - default: Default value if the variable doesn't match
    """

    # Convert to lowercase for case-insensitive matching
    matches = [match.lower() for match in matches]
    value = environ.get(name, None)
    if value is None:
        return None
    if value.lower() in matches:
        return True
    return default


def env_var_is_true(name: str) -> bool:
    """Determines if the value of the given environment variable represents "True" in some way.

    - name: The environment variable to check
    """

    return env_var_matches(name, ['t', 'true', 'yes'], False)
