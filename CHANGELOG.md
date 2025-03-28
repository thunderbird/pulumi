# tb_pulumi Changelog

## v0.0.13

  - The `build_jumphost` option has been removed from the
    [`tb_pulumi.elasticache.ElastiCacheReplicationGroup`](https://thunderbird.github.io/pulumi/elasticache.html#tb_pulumi.elasticache.ElastiCacheReplicationGroup)
    module. This is because this sort of server is not necessarily purpose-built for testing ElastiCache. If you require
    an SSH bastion or "jump host", you should just construct a
    [`tb_pulumi.ec2.SshableInstance`](https://thunderbird.github.io/pulumi/ec2.html#tb_pulumi.ec2.SshableInstance) on
    your network.
  - Your project's region will now be automatically used when creating AWS clients using the boto3 library, which solves
    problems when your environment's configured default region is different from your project's region.
  - Fixed a bug in the `ci` module where an IAM policy was granting write access to tags for most ECS resources, but not
    task definitions.
  - Added the
    [`get_latest_amazon_linux_ami`](https://thunderbird.github.io/pulumi/tb_pulumi.html#tb_pulumi.ThunderbirdPulumiProject.get_latest_amazon_linux_ami)
    function, which... gets the latest Amazon Linux 2023 AMI. This replaces an old hardcoded AMI, which was not a valid
    or maintainable approach to building servers.
  - Added the [`tb_pulumi.s3`](https://thunderbird.github.io/pulumi/s3.html) module, with a pattern for building out S3
    buckets.
  - Added the [`tb_pulumi.iam`](https://thunderbird.github.io/pulumi/iam.html) module, with a pattern for building an
    IAM user with an access key. The secret key data is stored in AWS Secrets Manager.
  - Removed a hardcoded value in the `description` field of `tb_pulumi.network.SecurityGroupWithRule`'s security group
    resource. **!! WARNING !! This is a particularly ugly change to have to apply. The description field on a security
    group is considered immutable, so this will cause every security group created through this module to be recreated.
    This will almost certainly cause downtime in your application, and so should be applied with caution.**


## v0.0.12

  - Added a class (and documentation for it) to build an ElastiCache replication group.
  - Improved tagging overall, adding tags to resources that were erroneously untagged before this version, and adding
    the special `Name` tag in a couple places.
  - Fixed a bug where security group rules made by the `SecurityGroupWithRules` class had their Pulumi names generated
    partially using the `to_port` value. This creates a lot of room for name clobbers, which are a show-stopper for
    Pulumi. Now these are indexed with sequential integers. **Upgrading `SecurityGroupWithRules` resources to this
    version of tb_pulumi will require some `pulumi state mv` commands to resolve without downtime!**
  - Many documentation updates, including more detail on how monitoring works, explicit listing of Pulumi "type" strings
    for all tb_pulumi classes, and explicit listings of all resources managed by each class.
  - Fixed a simple type (Automationuser -> AutomationUser, with a capital U), but **this will cause CI stacks to have to
    be recreated** since this represents a type change in Pulumi.


## v0.0.11

  - Improved documentation around starting new projects.
  - The Quickstart script now supports Pulumi Cloud and private cloud hosts.
  - Fixed CI bugs where the CI user wasn't able to read details about load balancers and target groups while deploying
    Fargate images.
  - Under the hood, refactored a custom "Flattenable" type that represents the various types and collections we support
    when auto-identifying resources in a `ThunderbirdPulumiProject`. This should be completely transparent to users.
  - Fixed a bug where one single security group with a combined set of rules would be applied to both a load balancer
    and its container targets in a `FargateClusterWithLogging`. This is not secure, as it is permissive in each case of
    traffic not intended to reach the target. With this release, we support defining these groups separately.


## v0.0.10

  - Can now declare recovery period for Secrets Manager Secrets built by the `RdsDatabaseGroup` class.
  - `ThunderbirdPulumiProject`s now detect resources "hidden" by output resolution through the `flatten` function. This may result in some new monitors being created in your stack.
  - Top level `ThunderbirdPulumiProject` resource namespace pollution problem is solved by optional `exclude_from_project` parameter.
  - Remove some redundancy in naming some CI-related IAM resources.


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
        managed through this module. This will result in new ARNs which you will have to update anywhere they are
        used.**
  - These features both serve to make destroying and rebuilding stacks less painful.


## v0.0.4

  - Resolved issues related to S3 bucket permissions which were preventing clean environment builds from scratch ([Issue #21](https://github.com/thunderbird/pulumi/issues/21)).
  - Resolved a bug where some execution environments were not able to determine the name of the user running the Pulumi command ([Issue #24](https://github.com/thunderbird/pulumi/issues/24)).
  - Redesigned the internal patterns by which resources are tracked; properly divided the concept of resource tracking from that of Pulumi outputs ([Issue #20](https://github.com/thunderbird/pulumi/issues/20)).
  - Added some IAM resources to help manage the capabilities of CI robots ([Issue #26](https://github.com/thunderbird/pulumi/issues/26)).


## v0.0.3

  - Overhauled documentation.
  - Only docstrings have changed with this version.
  - No actual code changes have been made.


## v0.0.2

  - Added `CloudFrontS3Service` pattern for serving static content over a CDN.


## v0.0.1

  - Initial commit supporting basic infrastructure required to run a Fargate service on private network space.
