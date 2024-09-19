"""Some global values that should not change often and do not rely on runtime data."""

# Shell for ARPs
ASSUME_ROLE_POLICY = {
    'Version': '2012-10-17',
    'Statement': [{'Sid': '', 'Effect': 'Allow', 'Principal': {'Service': None}, 'Action': 'sts:AssumeRole'}],
}

# Global default values to fall back on
DEFAULT_AWS_SSL_POLICY = 'ELBSecurityPolicy-2016-08'
DEFAULT_PROTECTED_STACKS = ['prod']  # Which Pulumi stacks should get resource protection

# Policy document shell
IAM_POLICY_DOCUMENT = {'Version': '2012-10-17', 'Statement': [{'Sid': 'DefaultSid', 'Effect': 'Allow'}]}

# Map of common services to their typical ports
SERVICE_PORTS = {
    'mariadb': 3306,
    'mysql': 3306,
    'postgres': 5432,
}
