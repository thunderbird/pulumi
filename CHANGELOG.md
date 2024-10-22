# tb_pulumi Changelog

## v0.0.4

  - Resolved issues related to S3 bucket permissions which were preventing clean environment builds from scratch ([Issue #21](https://github.com/thunderbird/pulumi/issues/21)).
  - Resolved a bug where some execution environments were not able to determine the name of the user running the Pulumi command ([Issue #24](https://github.com/thunderbird/pulumi/issues/24)).
  - Redesigned the internal patterns by which resources are tracked; properly divided the concept of resource tracking from that of Pulumi outputs ([Issue #20](https://github.com/thunderbird/pulumi/issues/20)).
  - Added some IAM resources to help manage the capabilities of CI robots ([Issue #26](https://github.com/thunderbird/pulumi/issues/26)).


## v0.0.3

  - Overhauled documentation.
  - Only docstrings have changed with this version.
  - No actual code changes have been altered.


## v0.0.2

  - Added `CloudFrontS3Service` pattern for serving static content over a CDN.


## v0.0.1

  - Initial commit supporting basic infrastructure required to run a Fargate service on private network space.
