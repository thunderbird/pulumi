"""Infrastructural patterns related to `AWS Secrets Manager
<https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html>`_."""

import json
import pulumi
import pulumi_aws as aws
import tb_pulumi
import typing


class SecretsManagerSecret(tb_pulumi.ThunderbirdComponentResource):
    """Stores a value as a Secrets Manager secret.

    :param name: A string identifying this set of resources.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: ThunderbirdPulumiProject

    :param secret_name: A slash ("/") delimited name for the secret in AWS. The last segment of this will be used as the
        "short name" for abbreviated references.
    :type name: str

    :param secret_value: The secret data to store. This should be a string or some other type that can be serialized
        with `str()`.
    :type name: Any

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param kwargs: Any other keyword arguments which will be passed as inputs to the ThunderbirdComponentResource
        superconstructor.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        secret_name: str,
        secret_value: typing.Any,
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        super().__init__('tb:secrets:SecretsManagerSecret', name, project, opts=opts, **kwargs)

        short_name = secret_name.split('/')[-1]
        self.resources['secret'] = aws.secretsmanager.Secret(
            f'{name}-secret-{short_name}', opts=pulumi.ResourceOptions(parent=self), name=secret_name
        )

        self.resources['version'] = aws.secretsmanager.SecretVersion(
            f'{name}-secretversion-{short_name}',
            secret_id=self.resources['secret'].id,
            secret_string=secret_value,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[self.resources['secret']]),
        )

        self.finish()


class PulumiSecretsManager(tb_pulumi.ThunderbirdComponentResource):
    """Builds a set of AWS SecretsManager Secrets based on specific secrets in Pulumi's config.

    :param name: A string identifying this set of resources.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: ThunderbirdPulumiProject

    :param secret_names: A list of secrets as they are known to Pulumi. To get a list of valid values, run
        ``pulumi config``. For more info on Pulumi secrets, see
        `Working with Secrets <https://www.pulumi.com/learn/building-with-pulumi/secrets/>`_.
    :type secret_names: list[str], optional

    :param opts: Additional pulumi.ResourceOptions to apply to these resources.
    :type opts: pulumi.ResourceOptions, optional

        - kwargs: Any other keyword arguments which will be passed as inputs to the
            ThunderbirdComponentResource superconstructor.

    :param kwargs: Any other keyword arguments which will be passed as inputs to the ThunderbirdComponentResource
        superconstructor.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        secret_names: list[str] = [],
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):

        super().__init__('tb:secrets:PulumiSecretsManager', name, project, opts=opts, **kwargs)
        self.resources['secrets'] = []
        self.resources['versions'] = []

        # First build the secrets
        for secret_name in secret_names:
            # Pull the secret's value from Pulumi's encrypted state
            secret_string = self.project.pulumi_config.require_secret(secret_name)

            # Declare a Secrets Manager Secret
            secret_fullname = f'{self.project.project}/{self.project.stack}/{secret_name}'
            secret = aws.secretsmanager.Secret(
                f'{name}-secret-{secret_name}', opts=pulumi.ResourceOptions(parent=self), name=secret_fullname
            )
            self.resources['secrets'].append(secret)

            # Populate its value
            self.resources['versions'].append(
                aws.secretsmanager.SecretVersion(
                    f'{name}-secretversion-{secret_name}',
                    opts=pulumi.ResourceOptions(parent=self),
                    secret_id=secret.id,
                    secret_string=secret_string,
                )
            )

        # Then create an IAM policy allowing access to them
        secret_arns = [secret.arn for secret in self.resources['secrets']]
        policy = pulumi.Output.all(*secret_arns).apply(
            lambda secret_arns: json.dumps(
                {
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Sid': 'AllowSecretsAccess',
                            'Effect': 'Allow',
                            'Action': 'secretsmanager:GetSecretValue',
                            'Resource': [arn for arn in secret_arns],
                        }
                    ],
                }
            )
        )
        self.resources['policy'] = aws.iam.Policy(
            f'{name}-policy',
            opts=pulumi.ResourceOptions(parent=self),
            name=name,
            description=f'Allows access to secrets related to {name}',
            policy=policy,
        )

        self.finish()
