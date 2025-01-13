# tb_pulumi Changelog

## v0.0.10

  - Can now declare recovery period for Secrets Manager Secrets built by the `RdsDatabaseGroup` class.
  - `ThunderbirdPulumiProject`s now detect resources "hidden" by output resolution through the `flatten` function. This may result in some new monitors being created in your stack.
  - Top level `ThunderbirdPulumiProject` resource namespace pollution problem is solved by optional `exclude_from_project` parameter.

## v0.0.9

  - Remove Insegel theme from docs builds, relying on Furo for its dark/light modes and respect for user preference.
  - Add several high priority alarms through EC2 and CloudFront.
  - Allow users to set the function associations for default behaviors in a CloudFront distribution.

## v0.0.8

  - Fix a bug where dimensions for some CloudWatch alarms did not get set correctly, resuling in "Insufficient Data" all
    the time.
  - Verification of Pulumi resource dependencies throughout the codebase. This repairs the dependency tree and makes
    destroys and environment rebuilds smooth.

## v0.0.7

  - Lock the AWS provider to a specific version to avoid errors when CI automation runs pulumi commands with `--target`.
  - Add an `environment` tag to all AWS resources for cost tracking purposes.
  - Build the initial patterns to use for developing project-at-once monitoring solutions.

## v0.0.6

  - Fixed bugs in the new CI features of v0.0.5 where certain permissions were lacking in some of the IAM polices.
  - Added documentation of the CI module.

## v0.0.5

  - Added feature to `CloudFrontS3Service`s where S3 buckets can be forcibly destroyed, even if they contain objects.
  - The `secrets` module has been refactored in two ways:
    1.  The `SecretsManagerSecrets` class now passes all extra keyword arguments into the `Secret` resource, allowing
        for configuration of other inputs of that resource.
    2.  The `PulumiSecretsManager` class no longer manages its own `Secret` and `SecretVersion` resources, relying
        instead on the `SecretsManagerSecrets` class to better organize things. **This particular change may present
        challenges at the time your Pulumi code is upgraded to v0.0.5, as it will cause a recreation of all secrets
        managed through this module. This will result in new ARNs which you will have to update anywhere they are used.
  - These features both serve to make destroying and rebuilding stacks less painful.

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
