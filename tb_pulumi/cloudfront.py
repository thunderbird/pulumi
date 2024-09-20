import pulumi
import pulumi_aws as aws
import tb_pulumi

"""TODO:

  - S3 bucket for CloudFront logs
    - tb-send-suite-staging-frontend-logs
    - With object-level ACLs on
  - CF function for rewrites
      - send-suite-staging-rewrite
  - CF distro
      - Any reason WAF is off?
      - Frontend bucket policy refers to CF distro arn
          - Must update after distro is created
"""


class CloudFrontS3Service(tb_pulumi.ThunderbirdComponentResource):
    """Serve the static contents of an S3 bucket over a CloudFront Distribution."""

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        service_bucket_name: str,
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        """Construct a CloudFrontS3Service.

        Positional arguments:
            - name: A string identifying this set of resources.
            - project: The ThunderbirdPulumiProject to add these resources to.
            - service_bucket_name: The name of the S3 bucket to store the static content in. This must be globally
                unique within the entire S3 ecosystem.

        Keyword arguments:
            - opts: Additional pulumi.ResourceOptions to apply to these resources.
            - kwargs: Any other keyword arguments which will be passed as inputs to the
                ThunderbirdComponentResource superconstructor.
        """

        super().__init__('tb:cloudfront:CloudFrontS3Service', name=name, project=project, opts=opts, **kwargs)

        # The function supports supplying the bucket policy at this time, but we have to have the CF distro built first.
        # For this reason, we build the bucket without the policy and attach the policy later on.
        self.resources['service_bucket'] = aws.s3.Bucket(
            f'{name}-servicebucket',
            bucket=service_bucket_name,
            server_side_encryption_configuration={
                'rule': {'applyServerSideEncryptionByDefault': {'sseAlgorithm': 'AES256'}, 'bucket_key_enabled': True}
            },
            opts=pulumi.ResourceOptions(parent=self),
            tags=self.tags,
        )

        # S3 bucket to store access logs from CloudFront
        self.resources['logging_bucket'] = aws.s3.Bucket(
            f'{name}-loggingbucket',
            bucket=f'{service_bucket_name}-logs',
            server_side_encryption_configuration={
                'rule': {'applyServerSideEncryptionByDefault': {'sseAlgorithm': 'AES256'}, 'bucket_key_enabled': True}
            },
            opts=pulumi.ResourceOptions(parent=self, ignore_changes=['acl', 'grants']),
            tags=self.tags,
        )

        self.resources['logging_bucket_ownership'] = aws.s3.BucketOwnershipControls(
            f'{name}-bucketownership',
            bucket=self.resources['logging_bucket'].id,
            rule={'object_ownership': 'BucketOwnerPreferred'},
            opts=pulumi.ResourceOptions(parent=self,),
        )

        self.finish()
