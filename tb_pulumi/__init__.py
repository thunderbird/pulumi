"""Standardization library for the usage of Pulumi in Python at Thunderbird. For an overview of how
to use this library, `read the README <https://github.com/thunderbird/pulumi/blob/main/README.md>`_.
"""

import boto3
import pulumi
import yaml

from functools import cached_property
from os import environ, getlogin, path
from socket import gethostname
from tb_pulumi.constants import DEFAULT_PROTECTED_STACKS
from typing import Any


class ThunderbirdPulumiProject:
    """A collection of related Pulumi resources upon which we can take bulk/collective actions. This class enforces some
    usage conventions that help keep us organized and consistent.

    :param protected_stacks: List of stack names which should require explicit instruction to modify. Defaults to
        :py:data:`tb_pulumi.constants.DEFAULT_PROTECTED_STACKS`.
    :type protected_stacks: list[str], optional
    """

    def __init__(self, protected_stacks: list[str] = DEFAULT_PROTECTED_STACKS):
        # General runtime data
        self.project: str = pulumi.get_project()  #: Name of the Pulumi project
        self.stack: str = pulumi.get_stack()  #: Name of the Pulumi stack
        self.name_prefix: str = f'{self.project}-{self.stack}'  #: Convenience prefix for naming resources consistently
        self.protected_stacks: list[str] = protected_stacks
        #: Pulumi configuration data referencing Pulumi.stack.yaml
        self.pulumi_config: pulumi.config.Config = pulumi.Config()
        self.resources: dict = {}  #: Pulumi Resource objects managed by this project

        # Some machines can't run a getlogin(), which is the preferred method, but we support some others
        try:
            username = getlogin()
        except OSError:
            homepath = path.expanduser('~')
            unix_style = homepath.split('/')
            win_style = homepath.split('\\')
            if len(unix_style) > 1:
                username = unix_style[-1]
            elif len(win_style) > 1:
                username = win_style[-1]
            else:
                username = 'unknown'

        self.common_tags: dict = {  #: Tags to apply to all taggable resources
            'environment': self.stack,
            'project': self.project,
            'pulumi_last_run_by': f'{username}@{gethostname()}',
            'pulumi_project': self.project,
            'pulumi_stack': self.stack,
        }

        # AWS client setup
        self.__aws_clients = {}
        self.__aws_session = boto3.session.Session()
        sts = self.get_aws_client('sts')

        #: Account number that the currently configured AWS user/role is a member of, in which Pulumi will act.
        self.aws_account_id: str = sts.get_caller_identity()['Account']
        #: Currently configured AWS region
        self.aws_region: str = self.__aws_session.region_name

    def get_aws_client(self, service: str):
        """Retrieves an AWS client for the requested service, preferably from a cache. Caches any clients it creates.

        :param service: Name of the service as described in
            `boto3 docs <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/index.html>`_
        :type service: str
        """
        if service not in self.__aws_clients.keys():
            self.__aws_clients[service] = self.__aws_session.client(service)

        return self.__aws_clients[service]

    @cached_property
    def config(self) -> dict:
        """Provides read-only access to the project configuration, which is expected to be in the root of your Pulumi
        project directory, and should match the current stack. For example, ``config.preprod.yaml`` would be a
        configuration for an environment called "preprod"."""

        config_file = f'config.{self.stack}.yaml'
        with open(config_file, 'r') as fh:
            return yaml.load(fh.read(), Loader=yaml.SafeLoader)

    def flatten(self) -> set[pulumi.Resource]:
        """Returns a flat set of all resources existing within this project."""

        return flatten(self.resources)


class ThunderbirdComponentResource(pulumi.ComponentResource):
    """A special kind of pulumi.ComponentResource which handles common elements of resources such as naming and tagging.
    All such resources must belong to a :py:class:`tb_pulumi.ThunderbirdPulumiProject`.

    :param pulumi_type: The "type" string (commonly referred to in docs as just ``t``) of the component as described
        by `Pulumi's docs <https://www.pulumi.com/docs/concepts/resources/names/#types>`_.
    :type pulumi_type: str

    :param name: An identifier for this set of resources. Generally, this gets used as part of all resources defined
        by the ComponentResource.
    :type name: str

    :param project: The project this resource belongs to.
    :type project: :py:class:`tb_pulumi.ThunderbirdPulumiProject`

    :param opts: Additional ``pulumi.ResourceOptions`` to apply to this resource. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param tags: Key/value pairs to merge with the default tags which get applied to all resources in this group.
        Defaults to {}.
    :type tags: dict, optional
    """

    def __init__(
        self,
        pulumi_type: str,
        name: str,
        project: ThunderbirdPulumiProject,
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
    ):
        self.name: str = name  #: Identifier for this set of resources.
        self.project: ThunderbirdPulumiProject = project  #: Project this resource is a member of.

        if self.protect_resources:
            pulumi.info(
                f'Resource protection has been enabled on {name}. '
                'To disable, export TBPULUMI_DISABLE_PROTECTION=True'
            )

        # Merge provided opts with defaults before calling superconstructor
        default_opts = pulumi.ResourceOptions(protect=self.protect_resources)
        final_opts = default_opts.merge(opts)
        super().__init__(t=pulumi_type, name=name, opts=final_opts)

        self.tags: dict = self.project.common_tags.copy()  #: Tags to apply to all taggable resources
        self.tags.update(tags)

        self.resources: dict = {}  #: Resources which are members of this ComponentResource.

    def finish(self, outputs: dict[str, Any], resources: dict[str, pulumi.Resource | list[pulumi.Resource]]):
        """Registers the provided ``outputs`` as Pulumi outputs for the module. Also stores the mapping of ``resources``
        internally as the ``resources`` member where they it be acted on collectively by a ``ThunderbirdPulumiProject``.
        Any implementation of this class should call this function at the end of its ``__init__`` function to ensure its
        state is properly represented.

        Values in ``resources`` should be either a Resource or derivative (such as a ThunderbirdComponentResource) or a
        list of such.
        """

        # Register outputs both with the ThunderbirdPulumiProject and Pulumi itself
        self.resources = resources
        self.project.resources[self.name] = self.resources
        self.register_outputs(outputs)

    @property
    def protect_resources(self) -> bool:
        """Determines whether resources should have protection against changes enabled based on the project's
        configuration. Unprotected resources are not part of a protected stack, or you have run Pulumi with
        ``TBPULUMI_DISABLE_PROTECTION=True`` set in your environment."""

        if self.project.stack not in self.project.protected_stacks:
            protect = False
        else:
            protect = not env_var_is_true('TBPULUMI_DISABLE_PROTECTION')

        return protect


def env_var_matches(name: str, matches: list[str], default: bool = False) -> bool:
    """Determines if the value of the given environment variable is in the given list. This is a case-insensitive check.

    :param name: The environment variable to check
    :type name: str

    :param matches: A list of strings to match against
    :type matches: list[str]

    :param default: Default value if the variable doesn't match. Defaults to False.
    :type default: bool, optional

    :return: True if the value of the given environment variable is in the given list, the provided `default` value if
        it is not, or `None` if the variable is unset.
    :rtype: bool

        - name:
        - matches:
        - default:
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

    :param name: The environment variable to check
    :type name: str

    :return: `True` if the value of the environment variable looks like it is set to an affirmative value, otherwise
        `False`.
    :rtype: bool
    """

    return env_var_matches(name, ['t', 'true', 'yes'], False)


def flatten(item: dict | list | ThunderbirdComponentResource | pulumi.Resource) -> set[pulumi.Resource]:
    """Recursively traverses a nested collection of Pulumi ``Resource``s, converting them into a flat set which can be
    more easily iterated over.

    :param item: Either a Pulumi ``Resource`` object, or some collection thereof. The following types of collections are
        supported: ``dict``, ``list``, ``ThunderbirdComponentResource``.
    :type item: dict | list | ThunderbirdComponentResource

    :return: A ``set`` of Pulumi ``Resource``s contained within the collection.
    :rtype: set(pulumi.Resource)
    """

    # The item could be of a variety of types. When the item is some kind of collection, we should compress it down into
    # a flat list first, then operate on its items.
    flattened = []
    to_flatten = None
    if type(item) is list:
        to_flatten = item
    elif type(item) is dict:
        to_flatten = [value for _, value in item.items()]
    elif isinstance(item, ThunderbirdComponentResource):
        to_flatten = [value for _, value in item.resources.items()]
    elif isinstance(item, pulumi.Resource):
        return [item]
    else:
        pass

    if to_flatten is not None:
        for item in to_flatten:
            flattened.extend(flatten(item))

    return set(flattened)
