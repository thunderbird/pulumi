"""Standardization library for the usage of Pulumi in Python at Thunderbird. For an overview of how
to use this library, read the :ref:`getting_started` page.
"""

# <https://thunderbird.github.io/pulumi/getting-started.html>`_
import boto3
import pulumi
import yaml

from functools import cached_property
from os import environ
from tb_pulumi.constants import DEFAULT_PROTECTED_STACKS
from typing import Any


#: Type alias representing valid types to be found among a ThunderbirdPulumiProject's resources
type Flattenable = dict | list | ThunderbirdComponentResource | pulumi.Output | pulumi.Resource

FINISH_OUTPUTS_DEPRECATION_MESSAGE = """Calling ThunderbirdComponentResource.finish with the "outputs" parameter is
    DEPRECATED. This parameter will be removed in a future version."""


class ThunderbirdPulumiProject:
    """A collection of related Pulumi resources upon which we can take bulk/collective actions. This class enforces some
    usage conventions that help keep us organized and consistent.

    :param protected_stacks: List of stack names which should require explicit instruction to modify. Defaults to
        :py:data:`tb_pulumi.constants.DEFAULT_PROTECTED_STACKS`.
    :type protected_stacks: list[str], optional
    """

    def __init__(self, protected_stacks: list[str] = DEFAULT_PROTECTED_STACKS):
        # General runtime data

        #: Name of the Pulumi project
        self.project: str = pulumi.get_project()
        #: Name of the Pulumi stack
        self.stack: str = pulumi.get_stack()
        #: Convenience prefix for naming resources consistently
        self.name_prefix: str = f'{self.project}-{self.stack}'
        #: List of stacks to apply resource deletion protection to
        self.protected_stacks: list[str] = protected_stacks
        #: Pulumi configuration data referencing Pulumi.stack.yaml
        self.pulumi_config: pulumi.config.Config = pulumi.Config()
        #: Pulumi Resource objects managed by this project
        self.resources: dict = {}

        self.common_tags: dict = {  #: Tags to apply to all taggable resources
            'environment': self.stack,
            'project': self.project,
            'pulumi_project': self.project,
            'pulumi_stack': self.stack,
        }

        # AWS client setup
        self.__aws_clients = {}
        self.__aws_session = boto3.session.Session()
        sts = self.get_aws_client(service='sts', region_name=self.__aws_session.region_name)

        #: Account number that the currently configured AWS user/role is a member of, in which Pulumi will act.
        self.aws_account_id: str = sts.get_caller_identity()['Account']
        #: Currently configured AWS region
        self.aws_region: str = self.__aws_session.region_name

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

    def get_aws_client(self, service: str, region_name: str = None):
        """Retrieves an AWS client for the requested service, preferably from a cache. Caches any clients it creates.

        :param service: Name of the service as described in
            `boto3 docs <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/index.html>`_
        :type service: str

        :param region_name: Name of the AWS region to set the client up for, such as "us-east-1".
        :type region_name: str
        """

        # Don't use "None" as part of the key; use the default for the project instead
        key = f'{service}-{self.aws_region}' if region_name is None else f'{service}-{region_name}'

        # If there isn't a client for this service/region, build one
        if key not in self.__aws_clients.keys():
            self.__aws_clients[key] = self.__aws_session.client(service, region_name=region_name)

        return self.__aws_clients[key]

    def get_latest_amazon_linux_ami(
        self, region_name: str = None, name_alias: str = 'al2023-ami-minimal-kernel-6.1-x86_64'
    ) -> str:
        """Returns the AMI ID of the latest Amazon Linux 2023 image for the given region. AWS provides many such AMIs
        for various purposes. By default, this returns the AMI for the x86-architecture HVM image with GP2 storage. You
        can specify a different image by providing the appropriate ``name_alias``. This is accomplished by checking an
        `SSM parameter that AWS publishes
        <https://aws.amazon.com/blogs/compute/query-for-the-latest-amazon-linux-ami-ids-using-aws-systems-manager-parameter-store/>`_.

        :param region_name: Name of the region to get the localized AMI ID for. Defaults to the project's region.
        :type region_name: str, optional

        :param name_alias: AMI name alias describing the image to look up. To see what values are valid for your region,
            run this AWSCLI command:

            .. code-block:: bash

                aws ssm describe-parameters \\
                    --region $your_region_here \\
                    --filters 'Key=Name,Values=/aws/service/ami-amazon-linux-latest/' \\
                    --query 'Parameters[*].Name' |
                    sed 's/\\/aws\\/service\\/ami-amazon-linux-latest\\///g'

            Defaults to `al2023-ami-minimal-kernel-6.1-x86_64`.
        :type name_alias: str, optional
        """

        ssm = self.get_aws_client(service='ssm', region_name=region_name)
        param = ssm.get_parameter(
            Name=f'/aws/service/ami-amazon-linux-latest/{name_alias}',
        )
        return param['Parameter']['Value']


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

    :param exclude_from_project: When ``True`` , this prevents this component resource from being registered directly
        with the project. This does not prevent the component resource from being discovered by the project's
        ``flatten`` function, provided that it is nested within some resource that is not excluded from the project.
        This option largely pertains to the ability to debug resources after they have been applied, and is not
        something most users need worry themselves with. When developing a ThunderbirdComponentResource that includes
        other ThunderbirdComponentResources, the child resources should have this set to `True`. Defaults to ``False``.
    :type exclude_from_project: bool, optional

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
        exclude_from_project: bool = False,
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
    ):
        self.name: str = name  #: Identifier for this set of resources.
        self.project: ThunderbirdPulumiProject = project  #: Project this resource is a member of.
        self.exclude_from_project = exclude_from_project

        if self.protect_resources:
            pulumi.info(
                f'Resource protection has been enabled on {name}. To disable, export TBPULUMI_DISABLE_PROTECTION=True'
            )

        # Merge provided opts with defaults before calling superconstructor
        default_opts = pulumi.ResourceOptions(protect=self.protect_resources)
        final_opts = default_opts.merge(opts)
        super().__init__(t=pulumi_type, name=name, opts=final_opts)

        self.tags: dict = self.project.common_tags.copy()  #: Tags to apply to all taggable resources
        self.tags.update(tags)

        self.resources: dict = {}  #: Resources which are members of this ComponentResource.

    def finish(self, outputs: dict[str, Any] = {}, resources: dict[str, Flattenable] = {}):
        """Stores the mapping of ``resources`` internally as the ``resources`` member of this component resource's
        ``ThunderbirdPulumiProject``, where they can be acted on collectively. Any implementation of this class should
        call this function at the end of its ``__init__`` function to ensure its state is properly represented.

        Values in ``resources`` should be of a type compatible with the :py:data:`Flattenable` custom type.

        :param outputs: Dict of outputs to register with Pulumi's ``register_outputs`` function. This parameter is
            deprecated and will be removed in a future version. Defaults to {}.
        :type outputs: dict[str, Any], optional

        :param resources: Dict of Pulumi resources this component reosurce contains. Defaults to {}.
        :type resources: dict[str, Flattenable], optional
        """

        # Register resources internally; register outputs with Pulumi
        self.resources = resources
        if len(outputs) > 0:
            pulumi.warn(FINISH_OUTPUTS_DEPRECATION_MESSAGE)
        self.register_outputs(outputs)

        # Register resources within the project if not excluded
        if not self.exclude_from_project:
            self.project.resources[self.name] = self.resources

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


def flatten(item: Flattenable) -> set[pulumi.Resource]:
    """Recursively traverses a nested collection of Pulumi ``Resource`` s, converting them into a flat set which can be
    more easily iterated over.

    :param item: An item which we intend to flatten. Must be one of the recognized types or collections defined in
        the Flattenable type alias.
    :type item: dict | list | ThunderbirdComponentResource

    :return: A ``set`` of Pulumi ``Resource`` s contained within the collection.
    :rtype: set(pulumi.Resource)
    """

    # The item could be of a variety of types. When the item is some kind of collection, we should compress it down into
    # a flat list first, then operate on its items.
    flattened = []
    to_flatten = None
    if type(item) is list:
        to_flatten = item
    elif type(item) is dict:
        to_flatten = item.values()
    elif isinstance(item, ThunderbirdComponentResource):
        to_flatten = item.resources.values()
    elif isinstance(item, pulumi.Resource) or isinstance(item, pulumi.Output):
        return [item]

    if to_flatten is not None:
        for item in to_flatten:
            flattened.extend(flatten(item))

    return set(flattened)
