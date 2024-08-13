'''Standardization library for the usage of Pulumi in Python at Thunderbird. For an overview of how
to use this library, read the README: https://github.com/thunderbird/pulumi/blob/main/README.md
'''

import boto3
import pulumi
import yaml

from datetime import date
from os import environ, getlogin
from socket import gethostname


# Internalize runtime information
AWS_CLIENTS = {}
AWS_SESSION = boto3.session.Session()
AWS_ACCOUNT_ID = None
AWS_REGION = None
PROJECT = pulumi.get_project()
PULUMI_CONFIG = pulumi.Config()
STACK = pulumi.get_stack()

# Make certain common data accessible through this module
ASSUME_ROLE_POLICY={
    'Version': '2012-10-17',
    'Statement': [{
        'Sid': '',
        'Effect': 'Allow',
        'Principal': {
            'Service': None
        },
        'Action': 'sts:AssumeRole'
    }]
}
COMMON_TAGS = {
    'project': PROJECT,
    'pulumi_last_run_date': str(date.today()),
    'pulumi_last_run_by': f'{getlogin()}@{gethostname()}',
    'pulumi_project': PROJECT,
    'pulumi_stack': STACK}
DEFAULT_PROTECTED_STACKS = [ 'prod' ]
IAM_POLICY_DOCUMENT = {
    'Version': '2012-10-17',
    'Statement': [{
        'Sid': 'DefaultSid',
        'Effect': 'Allow'
    }]}
SERVICE_PORTS = {
    'mariadb': 3306,
    'mysql': 3306,
    'postgres': 5432,
}


class ThunderbirdPulumiProject(object):
    '''Manages Pulumi resources at Thunderbird. This class enforces some usage conventions that help
    keep us organized and consistent.
    '''

    def __init__(self,
        protected_stacks: list[str] = DEFAULT_PROTECTED_STACKS
    ):
        '''Construct a ThunderbirdPulumiProject.

            - protected_stacks: List of stack names which should require explicit instruction to
            modify.
        '''
        self.name_prefix = f'{PROJECT}-{STACK}'
        self.protected_stacks = protected_stacks
        self.resources = {}

        # Start with no config
        self.__config = None

    @property
    def config(self) -> dict:
        '''Provides read-only access to the project configuration'''
        if not self.__config:
            self.__config = self.__read_config()

        return self.__config

    def __read_config(self) -> dict:
        '''Reads the YAML-formatted configuration file for the current Pulumi stack and returns its
        contents as a dict.
        '''

        config_file = f'config.{STACK}.yaml'
        with open(config_file, 'r') as fh:
            return yaml.load(fh.read(), Loader=yaml.SafeLoader)


class ThunderbirdComponentResource(pulumi.ComponentResource):
    '''A special kind of pulumi.ComponentResource which handles common aspects of our resources such
    as naming, tagging, and internal resource organization in code.
    '''

    def __init__(self,
        t: str,
        name: str,
        project: ThunderbirdPulumiProject,
        opts: pulumi.ResourceOptions = None,
        tags: dict = {}
    ):
        '''Construct a ThunderbirdComponentResource.

        - t: The "type" string of the component as described by Pulumi's docs here:
            https://www.pulumi.com/docs/concepts/resources/names/#types
        - name: A string identifying this set of resources.
        - project: The ThunderbirdPulumiProject this resource belongs to.
        - opts: Additional pulumi.ResourceOptions to apply to this resource.
        - tags: Key/value pairs to merge with the default tags which get applied to all resources in
            this group.
        '''
        self.name = name
        self.project = project

        if self.protect_resources:
            pulumi.info(
                f'Resource protection has been enabled on {name}. '
                'To disable, export TBPULUMI_PROTECT_RESOURCES=False')

        # Merge provided opts with defaults before calling superconstructor
        default_opts = pulumi.ResourceOptions(protect=self.protect_resources)
        final_opts = default_opts.merge(opts)
        super().__init__(t, name, None, opts=final_opts)

        self.tags = COMMON_TAGS.copy()
        self.tags.update(tags)

        self.resources = {}

    def finish(self):
        '''Registers outputs based on the contents of `self.resources` and adds those resources to
        the project's internal tracking. All implementations of this class should call this function
        at the end of their __init__ functions.
        '''

        # Register outputs both with the ThunderbirdPulumiProject and Pulumi itself
        self.project.resources[self.name] = self.resources
        self.register_outputs({
            k: self.resources[k]
            for k in self.resources.keys()})

    @property
    def protect_resources(self) -> bool:
        '''Sets or unsets resource protection on the stack based on operating conditions.
        '''

        if STACK not in self.project.protected_stacks:
            protect = False
        else:
            protect = False \
                if environ.get('TBPULUMI_PROTECT_RESOURCES', 't').lower() in ['f', 'false', 'no' ] \
                else True

        return protect


def init():
    '''Initializes some global AWS data'''

    sts = get_aws_client('sts')
    aws_id = sts.get_caller_identity()

    global AWS_ACCOUNT_ID
    global AWS_REGION
    AWS_ACCOUNT_ID = aws_id['Account']
    AWS_REGION = AWS_SESSION.region_name

def get_aws_client(service: str):
    '''Creates and caches an AWS/boto3 client object, then returns it.
    '''

    global AWS_CLIENTS
    if service not in AWS_CLIENTS.keys():
        AWS_CLIENTS[service] = AWS_SESSION.client(service)

    return AWS_CLIENTS[service]


init()