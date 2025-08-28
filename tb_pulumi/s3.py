"""Infrastructural patterns related to `AWS S3 <https://docs.aws.amazon.com/s3/>`_."""

import json
import mimetypes
import pulumi
import pulumi_aws as aws
import tb_pulumi
import tb_pulumi.constants

from pathlib import Path


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

    :param bucket_name: The name of the S3 bucket to create.
    :type bucket_name: str

    :param enable_server_side_encryption: Enables AWS-managed AES256 server-side encryption on bucket objects. Defaults
        to True.
    :type enable_server_side_encryption: bool, optional

    :param enable_versioning: Enables versioning on bucket object. Defaults to False.
    :type enable_versioning: bool, optional

    :param object_dir: The path to a directory containing files which should be uploaded to the bucket. **These files
        will all be publicly accessible. Do not ever indicate files which contain sensitive data.** Defaults to None.
    :type str: str, optional

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param tags: Key/value pairs to merge with the default tags which get applied to all resources in this group.
        Defaults to {}.
    :type tags: dict, optional

    :param kwargs: Additional arguments to pass into the `aws.s3.S3BucketV2
        <https://www.pulumi.com/registry/packages/aws/api-docs/s3/bucketv2/>`_ constructor.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        bucket_name: str,
        enable_server_side_encryption: bool = True,
        enable_versioning: bool = False,
        object_dir: str = None,
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
        **kwargs,
    ):
        exclude_from_project = kwargs.pop('exclude_from_project', False)
        super().__init__(
            'tb:s3:S3Bucket',
            name=name,
            project=project,
            exclude_from_project=exclude_from_project,
            opts=opts,
            tags=tags,
        )

        bucket = aws.s3.BucketV2(
            f'{self.name}-s3', bucket=bucket_name, tags=self.tags, opts=pulumi.ResourceOptions(parent=self), **kwargs
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

        s3_objects = {}
        if object_dir:
            # Discover files to upload
            local_root = Path(object_dir)
            local_files = [file for file in local_root.glob('**') if file.is_file()]

            # Create object for each file
            s3_objects = {
                str(file): aws.s3.BucketObjectv2(
                    f'{name}-object-{str(file).replace("/", "_").replace("-", "_").replace(".", "_")}',
                    bucket=bucket_name,
                    content_type=mimetypes.guess_file_type(str(file))[0] or 'text/plain',
                    key=str(file).replace(str(local_root), ''),
                    source=pulumi.asset.FileAsset(file),
                    tags=self.tags,
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[bucket]),
                )
                for file in local_files
            }

        self.finish(
            resources={
                'bucket': bucket,
                'encryption_config': encryption_config,
                's3_objects': s3_objects,
                'versioning_config': versioning_config,
            }
        )


class S3BucketWebsite(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:s3:S3BucketWebsite``

    Builds an S3 bucket and sets up a **public access** static website from its contents.

    Produces the following ``resources``:

        - **bucket** - A :py:class:`tb_pulumi.s3.S3Bucket` to host the static files.
        - **bucket_acl** - An `aws.s3.BucketAclV2
          <https://www.pulumi.com/registry/packages/aws/api-docs/s3/bucketaclv2/>`_ describing public read access.
        - **bucket_oc** - An `aws.s3.BucketOwnershipControls
          <https://www.pulumi.com/registry/packages/aws/api-docs/s3/bucketownershipcontrols/>`_ describing how object
          ownership works.
        - **bucket_pab** - An `aws.s3.BucketPublicAccessBlock
          <https://www.pulumi.com/registry/packages/aws/api-docs/s3/bucketpublicaccessblock/>`_ which disables the
          blocks on public access.
        - **objects** - A dict where the keys are files discovered in the ``content_dir`` local directory and the values
          are `aws.s3.BucketObjectv2 <https://www.pulumi.com/registry/packages/aws/api-docs/s3/bucketobjectv2/>`_ s.
        - **policy** - An `aws.s3.BucketPolicy
          <https://www.pulumi.com/registry/packages/aws/api-docs/s3/bucketpolicy/#inputs>`_ allowing public read access
          to the bucket contents.
        - **website** - An `aws.s3.BucketWebsiteConfigurationV2
          <https://www.pulumi.com/registry/packages/aws/api-docs/s3/bucketwebsiteconfigurationv2/>`_ defining the
          operating parameters of the website.

    :param name: A string identifying this set of resources.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param bucket_name: The name of the S3 bucket to host a public website in.
    :type bucket_name: str

    :param website_config: A dict of options describing a `BucketWebsiteConfigurationV2 resource
        <https://www.pulumi.com/registry/packages/aws/api-docs/s3/bucketwebsiteconfigurationv2/#inputs>`_ .
    :type website_config: dict

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param tags: Key/value pairs to merge with the default tags which get applied to all resources in this group.
        Defaults to {}.
    :type tags: dict, optional

    :param kwargs: Additional arguments to pass into the :py:class:`S3Bucket` constructor.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        bucket_name: str,
        website_config: dict,
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
        **kwargs,
    ):
        super().__init__('tb:s3:S3BucketWebsite', name=name, project=project, opts=opts, tags=tags)

        bucket = S3Bucket(
            f'{name}-bucket',
            project=project,
            bucket_name=bucket_name,
            enable_server_side_encryption=False,
            enable_versioning=False,
            exclude_from_project=True,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
            **kwargs,
        )

        # Required or else we can't place an ACL on the bucket
        bucket_oc = aws.s3.BucketOwnershipControls(
            f'{name}-bucket-oc',
            bucket=bucket_name,
            rule={'objectOwnership': 'ObjectWriter'},
            opts=pulumi.ResourceOptions(parent=self, depends_on=[bucket]),
        )

        # Required or else we can't apply ACLs or a bucket policy, which are required elements of an S3 website
        bucket_pab = aws.s3.BucketPublicAccessBlock(
            f'{name}-bucket-pab',
            bucket=bucket_name,
            block_public_acls=False,
            block_public_policy=False,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[bucket]),
        )

        bucket_acl = aws.s3.BucketAclV2(
            f'{name}-bucket-acl',
            bucket=bucket_name,
            acl='public-read',
            opts=pulumi.ResourceOptions(parent=self, depends_on=[bucket, bucket_oc, bucket_pab]),
        )

        policy_json = tb_pulumi.constants.IAM_POLICY_DOCUMENT.copy()
        policy_json['Statement'][0] = {
            'Sid': 'PublicReadGetObject',
            'Effect': 'Allow',
            'Principal': '*',
            'Action': ['s3:GetObject'],
            'Resource': [f'arn:aws:s3:::{bucket_name}/*'],
        }
        policy_json = json.dumps(policy_json)
        policy = aws.s3.BucketPolicy(
            f'{name}-policy',
            bucket=bucket_name,
            policy=policy_json,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[bucket, bucket_oc, bucket_pab]),
        )

        website = aws.s3.BucketWebsiteConfigurationV2(
            f'{name}-website',
            bucket=bucket_name,
            **website_config,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[bucket]),
        )

        self.finish(
            resources={
                'bucket': bucket,
                'bucket_acl': bucket_acl,
                'bucket_oc': bucket_oc,
                'bucket_pab': bucket_pab,
                'policy': policy,
                'website': website,
            }
        )


class S3BucketSecureWebsite(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:s3:S3BuckeSecureWebsite``

    Builds an S3 bucket and sets up a **public access** static website from its contents.

    Produces the following ``resources``:

        - **bucket** - A :py:class:`tb_pulumi.s3.S3Bucket` to host the static files.
        - **bucket_acl** - An `aws.s3.BucketAclV2
          <https://www.pulumi.com/registry/packages/aws/api-docs/s3/bucketaclv2/>`_ describing public read access.
        - **bucket_oc** - An `aws.s3.BucketOwnershipControls
          <https://www.pulumi.com/registry/packages/aws/api-docs/s3/bucketownershipcontrols/>`_ describing how object
          ownership works.
        - **bucket_pab** - An `aws.s3.BucketPublicAccessBlock
          <https://www.pulumi.com/registry/packages/aws/api-docs/s3/bucketpublicaccessblock/>`_ which disables the
          blocks on public access.
        - **objects** - A dict where the keys are files discovered in the ``content_dir`` local directory and the values
          are `aws.s3.BucketObjectv2 <https://www.pulumi.com/registry/packages/aws/api-docs/s3/bucketobjectv2/>`_ s.
        - **policy** - An `aws.s3.BucketPolicy
          <https://www.pulumi.com/registry/packages/aws/api-docs/s3/bucketpolicy/#inputs>`_ allowing public read access
          to the bucket contents.
        - **website** - An `aws.s3.BucketWebsiteConfigurationV2
          <https://www.pulumi.com/registry/packages/aws/api-docs/s3/bucketwebsiteconfigurationv2/>`_ defining the
          operating parameters of the website.

    :param name: A string identifying this set of resources.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param bucket_name: The name of the S3 bucket to host a public website in.
    :type bucket_name: str

    :param website_config: A dict of options describing a `BucketWebsiteConfigurationV2 resource
        <https://www.pulumi.com/registry/packages/aws/api-docs/s3/bucketwebsiteconfigurationv2/#inputs>`_ .
    :type website_config: dict

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param tags: Key/value pairs to merge with the default tags which get applied to all resources in this group.
        Defaults to {}.
    :type tags: dict, optional

    :param kwargs: Additional arguments to pass into the :py:class:`S3Bucket` constructor.
    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        # oai_id: pulumi.Input[],
        bucket_name: str,
        website_config: dict,
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
        **kwargs,
    ):
        super().__init__('tb:s3:S3BucketSecureWebsite', name=name, project=project, opts=opts, tags=tags)

        bucket = S3Bucket(
            f'{name}-bucket',
            project=project,
            bucket_name=bucket_name,
            enable_server_side_encryption=False,
            enable_versioning=False,
            exclude_from_project=True,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
            **kwargs,
        )

        # Required or else we can't place an ACL on the bucket
        bucket_oc = aws.s3.BucketOwnershipControls(
            f'{name}-bucket-oc',
            bucket=bucket_name,
            rule={'objectOwnership': 'ObjectWriter'},
            opts=pulumi.ResourceOptions(parent=self, depends_on=[bucket]),
        )

        # Required or else we can't apply ACLs or a bucket policy, which are required elements of an S3 website
        bucket_pab = aws.s3.BucketPublicAccessBlock(
            f'{name}-bucket-pab',
            bucket=bucket_name,
            block_public_acls=False,
            block_public_policy=True,
            ignore_public_acls=True,
            restrict_public_buckets=True,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[bucket]),
        )

        bucket_acl = aws.s3.BucketAclV2(
            f'{name}-bucket-acl',
            bucket=bucket_name,
            acl='public-read',
            opts=pulumi.ResourceOptions(parent=self, depends_on=[bucket, bucket_oc, bucket_pab]),
        )

        # needed for s3 origin config
        # oai = aws.cloudfront.OriginAccessIdentity(
        #     f"{project.name_prefix}-autoconfig-oai",
        #     comment="OAI for autoconfig bucket"
        # )

        policy_json = tb_pulumi.constants.IAM_POLICY_DOCUMENT.copy()
        # policy_json['Statement'][0] = {
        #     'Sid': 'PublicReadGetObject',
        #     'Effect': 'Allow',
        #     'Principal': '*',
        #     'Action': ['s3:GetObject'],
        #     'Resource': [f'arn:aws:s3:::{bucket_name}/*'],
        # }

        policy_json['Statement'] = [
        {
            "Sid": "AllowCloudFrontPrincipalReadOnly",
            "Effect": "Allow",
            "Principal": {
                "Service": "cloudfront.amazonaws.com"
            },
            "Action": [
                "s3:GetObject"
            ],
            "Resource": f"arn:aws:s3:::{bucket_name}/*",
            "Condition": {
                "StringEquals": {
                    "AWS:SourceArn": f"arn:aws:cloudfront::{project.aws_account_id}:distribution/*"
                }
            }
        },
        {
            "Sid": "AllowCloudFrontS3ListBucket",
            "Effect": "Allow",
            "Principal": {
                "Service": "cloudfront.amazonaws.com"
            },
            "Action": [
                "s3:ListBucket"
            ],
            "Resource": f"arn:aws:s3:::{bucket_name}",
            "Condition": {
                "StringEquals": {
                    "AWS:SourceArn": f"arn:aws:cloudfront::{project.aws_account_id}:distribution/*"
                }
            }
        }
        ]
        
        policy_json = json.dumps(policy_json)
        policy = aws.s3.BucketPolicy(
            f'{name}-policy',
            bucket=bucket_name,
            policy=policy_json,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[bucket, bucket_oc, bucket_pab]),
        )

        # website = aws.s3.BucketWebsiteConfigurationV2(
        #     f'{name}-website',
        #     bucket=bucket_name,
        #     **website_config,
        #     opts=pulumi.ResourceOptions(parent=self, depends_on=[bucket]),
        # )

        self.finish(
            resources={
                'bucket': bucket,
                'bucket_acl': bucket_acl,
                'bucket_oc': bucket_oc,
                'bucket_pab': bucket_pab,
                'policy': policy,
                # 'website': website,
            }
        )
