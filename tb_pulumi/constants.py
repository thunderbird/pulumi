"""Some global values that should not change often and do not rely on runtime data."""

#: AWS IAM Assume Role Policies often follow this template.
ASSUME_ROLE_POLICY = {
    'Version': '2012-10-17',
    'Statement': [{'Sid': '', 'Effect': 'Allow', 'Principal': {'Service': None}, 'Action': 'sts:AssumeRole'}],
}

CLOUDFRONT_CACHE_POLICY_ID_OPTIMIZED = '658327ea-f89d-4fab-a63d-7e88639e58f6'  # "Managed-CachingOptimized" policy
CLOUDFRONT_CACHE_POLICY_ID_DISABLED = '4135ea2d-6df8-44a3-9df3-4b5a84be39ad'  # "Managed-CachingDisabled" policy
CLOUDFRONT_ORIGIN_REQUEST_POLICY_ID_ALLVIEWER = '216adef6-5c7f-47e4-b989-5492eafa07d3'  # "Managed-AllViewer" policy

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

#: IAM ARNs have a "path" portion, and these are the valid values
IAM_RESOURCE_PATHS = [
    'access-report',
    'federated-user',
    'group',
    'instance-profile',
    'mfa',
    'oidc-provider',
    'policy',
    'report',
    'role',
    'saml-provider',
    'server-certificate',
    'sms-mfa',
    'user',
]
#: Map of common services to their typical ports
SERVICE_PORTS = {
    'mariadb': 3306,
    'mysql': 3306,
    'postgres': 5432,
}
