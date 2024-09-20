import pulumi
import pulumi_aws as aws
import tb_pulumi


CACHE_POLICY_ID_OPTIMIZED = '658327ea-f89d-4fab-a63d-7e88639e58f6'  # "Managed-CachingOptimized" policy
CACHE_POLICY_ID_DISABLED = '4135ea2d-6df8-44a3-9df3-4b5a84be39ad'  # "Managed-CachingDisabled" policy
ORIGIN_REQUEST_POLICY_ID_ALLVIEWER = '216adef6-5c7f-47e4-b989-5492eafa07d3'  # "Managed-AllViewer" policy


class CloudFrontS3Service(tb_pulumi.ThunderbirdComponentResource):
    """Serve the static contents of an S3 bucket over a CloudFront Distribution."""

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        certificate_arn: str,
        service_bucket_name: str,
        behaviors: list[dict] = [],
        distribution: dict = {},
        origins: list[dict] = [],
        opts: pulumi.ResourceOptions = None,
        **kwargs,
    ):
        """Construct a CloudFrontS3Service.

        Positional arguments:
            - name: A string identifying this set of resources.
            - project: The ThunderbirdPulumiProject to add these resources to.
            - certificate_arn: The ARN of the ACM certificate used for TLS in this distribution.
            - service_bucket_name: The name of the S3 bucket to store the static content in. This must be globally
                unique within the entire S3 ecosystem.

        Keyword arguments:
            - behaviors: The default behavior of the CF distribution will always be to look in the S3 bucket. Any other
                behaviors should be defined as an entry in this list. These should be DistributionOrderedCacheBehavior
                objects. Ref: https://www.pulumi.com/registry/packages/aws/api-docs/cloudfront/distribution/#distributionorderedcachebehavior
            - distribution: Additional parameters to pass to the `aws.cloudfront.Distribution` constructor. Ref:
                https://www.pulumi.com/registry/packages/aws/api-docs/cloudfront/distribution
            - origins: List of DistributionOrigin objects to add. This list should not include any references to the S3
                bucket, which is managed by this module. Ref:
                https://www.pulumi.com/registry/packages/aws/api-docs/cloudfront/distribution/#distributionorigin
            - opts: Additional pulumi.ResourceOptions to apply to these resources.
            - kwargs: Any other keyword arguments which will be passed as inputs to the
                `tb_pulumi.ThunderbirdComponentResource` constructor.
        """

        super().__init__('tb:cloudfront:CloudFrontS3Service', name=name, project=project, opts=opts)

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
            grants=[
                {
                    'permissions': ['FULL_CONTROL'],
                    'type': 'CanonicalUser',
                    'id': aws.s3.get_canonical_user_id().id,
                    'uri': '',
                }
            ],
            server_side_encryption_configuration={
                'rule': {'applyServerSideEncryptionByDefault': {'sseAlgorithm': 'AES256'}, 'bucket_key_enabled': True}
            },
            opts=pulumi.ResourceOptions(parent=self),
            tags=self.tags,
        )

        self.resources['logging_bucket_ownership'] = aws.s3.BucketOwnershipControls(
            f'{name}-bucketownership',
            bucket=self.resources['logging_bucket'].id,
            rule={'object_ownership': 'BucketOwnerPreferred'},
            opts=pulumi.ResourceOptions(parent=self, depends_on=[self.resources['logging_bucket']]),
        )

        # Create an Origin Access Control to use when CloudFront talks to S3
        self.resources['oac'] = aws.cloudfront.OriginAccessControl(
            f'{name}-oac',
            origin_access_control_origin_type='s3',
            signing_behavior='always',
            signing_protocol='sigv4',
            description=f'Serve {service_bucket_name} contents via CDN',
            name=service_bucket_name,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[self.resources['service_bucket']]),
        )

        # Define the S3 DistributionOrigin and set up the distribution
        # The `bucket_regional_domain_name` output does not actually seem to contain the region. This may be a bug in
        # the AWS Pulumi provider. For now, we have to form this domain ourselves or it will be incorrect.
        bucket_regional_domain_name = f'{service_bucket_name}.s3.{project.aws_region}.amazonaws.com'
        s3_origin = {
            'domain_name': bucket_regional_domain_name,
            'origin_id': bucket_regional_domain_name,
            'origin_access_control_id': self.resources['oac'].id,
        }
        all_origins = [s3_origin]
        all_origins.extend(origins)

        # Merge logging settings from the config file with this generated bucket name
        logging_config = {'bucket': self.resources['logging_bucket'].bucket_domain_name}
        if 'logging_config' in distribution:
            logging_config.update(distribution['logging_config'])
            # Consume this now so it doesn't create kwarg problems later
            del distribution['logging_config']

        self.resources['cloudfront_distribution'] = aws.cloudfront.Distribution(
            f'{name}-cfdistro',
            default_cache_behavior={
                'allowed_methods': ['HEAD', 'DELETE', 'POST', 'GET', 'OPTIONS', 'PUT', 'PATCH'],
                'cached_methods': ['HEAD', 'GET'],
                'cache_policy_id': CACHE_POLICY_ID_OPTIMIZED,
                'compress': True,
                'target_origin_id': bucket_regional_domain_name,
                'viewer_protocol_policy': 'redirect-to-https',
            },
            enabled=True,
            logging_config=logging_config,
            ordered_cache_behaviors=behaviors,
            origins=all_origins,
            restrictions={'geo_restriction': {'restriction_type': 'none'}},
            viewer_certificate={
                'acm_certificate_arn': certificate_arn,
                'minimum_protocol_version': 'TLSv1.2_2021',
                'ssl_support_method': 'sni-only',
            },
            tags=self.tags,
            opts=pulumi.ResourceOptions(
                parent=self,
                ignore_changes=['defaultCacheBehavior.functionAssociations'],
            ),
            **distribution,
        )

        # Set the policy allowing CloudFront access to the service bucket
        bucket_policy = {
            'Version': '2008-10-17',
            'Id': 'PolicyForCloudFrontPrivateContent',
            'Statement': [
                {
                    'Sid': 'AllowCloudFrontServicePrincipal',
                    'Effect': 'Allow',
                    'Principal': {'Service': 'cloudfront.amazonaws.com'},
                    'Action': 's3:GetObject',
                    'Resource': f'arn:aws:s3:::{service_bucket_name}/*',
                    'Condition': {'StringEquals': {'AWS:SourceArn': self.resources['cloudfront_distribution'].arn}},
                }
            ],
        }

        self.resources['service_bucket_policy'] = aws.s3.BucketPolicy(
            f'{name}-bucketpolicy-service',
            bucket=self.resources['service_bucket'],
            policy=bucket_policy,
            opts=pulumi.ResourceOptions(
                parent=self,
                depends_on=[self.resources['service_bucket'], self.resources['cloudfront_distribution']],
            ),
        )

        self.finish()
