"""Some global values that should not change often and do not rely on runtime data."""

#: AWS IAM Assume Role Policies often follow this template.
ASSUME_ROLE_POLICY = {
    'Version': '2012-10-17',
    'Statement': [{'Sid': '', 'Effect': 'Allow', 'Principal': {'Service': None}, 'Action': 'sts:AssumeRole'}],
}

#: Most common settings for Cloudwatch metric alarms
CLOUDWATCH_METRIC_ALARM_DEFAULTS = {
    'enabled': True,
    'evaluation_periods': 2,
    'period': 60,
    'statistic': 'Average',
    'threshold': 10,
}

# Global default values to fall back on
DEFAULT_AWS_SSL_POLICY = 'ELBSecurityPolicy-2016-08'  #: Good default policy when setting up SSL termination with an ELB
DEFAULT_PROTECTED_STACKS = ['prod']  #: Which Pulumi stacks should get resource protection by default

#: IAM policies often extend this template.
IAM_POLICY_DOCUMENT = {'Version': '2012-10-17', 'Statement': [{'Sid': 'DefaultSid', 'Effect': 'Allow'}]}

#: Map of common services to their typical ports
SERVICE_PORTS = {
    'mariadb': 3306,
    'mysql': 3306,
    'postgres': 5432,
}
