"""Infrastructural patterns related to `AWS S3 <https://docs.aws.amazon.com/s3/>`_."""

import pulumi
import pulumi_aws as aws
import tb_pulumi


class S3Bucket(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:s3:S3Bucket``

    Builds an S3 bucket with various optional configurations.

    Produces the following ``resources``:

        - *bucket* - The `aws.s3.BucketV2 <https://www.pulumi.com/registry/packages/aws/api-docs/s3/bucketv2/>`_
          resource.
        - *encryption_config* - The `aws.s3.BucketServerSideEncryptionConfigurationV2
          <https://www.pulumi.com/registry/packages/aws/api-docs/s3/bucketserversideencryptionconfigurationv2/>`_ if
          ``enable_server_side_encryption`` is ``True``.
        - *versioning_config* - The `aws.s3.BucketVersioningV2
          <https://www.pulumi.com/registry/packages/aws/api-docs/s3/bucketversioningv2/>`_ resource if
          ``enable_versioning`` is ``True``.

    :param name: A string identifying this set of resources.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param enable_server_side_encryption: Enables AWS-managed AES256 server-side encryption on bucket objects. Defaults
        to True.
    :type enable_server_side_encryption: bool, optional

    :param enable_versioning: Enables versioning on bucket object. Defaults to False.
    :type enable_versioning: bool, optional

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param tags: Key/value pairs to merge with the default tags which get applied to all resources in this group.
        Defaults to {}.
    :type tags: dict, optional
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        bucket_name: str,
        enable_server_side_encryption: bool = True,
        enable_versioning: bool = False,
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
        **kwargs,
    ):
        super().__init__('tb:s3:S3Bucket', name=name, project=project, opts=opts, tags=tags)

        bucket = aws.s3.BucketV2(
            f'{self.name}-s3', bucket=bucket_name, tags=self.tags, opts=pulumi.ResourceOptions(parent=self)
        )

        encryption_config = (
            aws.s3.BucketServerSideEncryptionConfigurationV2(
                f'{self.name}-s3encryption',
                bucket=bucket.id,
                rules=[
                    {
                        'apply_server_side_encryption_by_default': {
                            'sse_algorithm': 'AES256',
                        }
                    }
                ],
                opts=pulumi.ResourceOptions(parent=self, depends_on=[bucket]),
            )
            if enable_server_side_encryption
            else None
        )

        versioning_config = (
            aws.s3.BucketVersioningV2(
                f'{self.name}-s3versioning',
                bucket=bucket.id,
                versioning_configuration={'status': 'Enabled'},
                opts=pulumi.ResourceOptions(parent=self, depends_on=[bucket]),
            )
            if enable_versioning
            else None
        )

        self.finish(
            resources={'bucket': bucket, 'encryption_config': encryption_config, 'versioning_config': versioning_config}
        )
