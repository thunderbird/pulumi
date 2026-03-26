"""Infrastructural patterns related to `Amazon EKS
<https://docs.aws.amazon.com/eks/latest/userguide/what-is-eks.html>`_."""

from __future__ import annotations

import json
import pulumi
import pulumi_aws as aws
import pulumi_eks as eks
import pulumi_kubernetes as k8s
import tb_pulumi


class EksCluster(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:eks:EksCluster``

    Builds an EKS cluster with managed node groups, EKS managed add-ons, KMS envelope encryption,
    OIDC provider for IRSA, and a gp3 default StorageClass. Wraps ``pulumi_eks.Cluster`` with
    tb_pulumi conventions (config-driven, tagging, resource protection).

    Produces the following ``resources``:

        - *cluster* - The :py:class:`pulumi_eks.Cluster` managing the EKS control plane.
        - *node_groups* - Dict of :py:class:`pulumi_eks.ManagedNodeGroup` resources keyed by name.
        - *addons* - Dict of `aws.eks.Addon <https://www.pulumi.com/registry/packages/aws/api-docs/eks/addon/>`_
          resources keyed by add-on name.
        - *kms_key* - The `aws.kms.Key <https://www.pulumi.com/registry/packages/aws/api-docs/kms/key/>`_
          used for envelope encryption of etcd secrets, or ``None`` if encryption is disabled.
        - *gp3_storage_class* - The Kubernetes StorageClass defaulting to gp3, or ``None`` if disabled.

    :param name: A string identifying this set of resources.
    :type name: str

    :param project: The ThunderbirdPulumiProject to add these resources to.
    :type project: tb_pulumi.ThunderbirdPulumiProject

    :param vpc_id: The VPC ID to deploy the cluster into.
    :type vpc_id: pulumi.Input[str]

    :param subnet_ids: Subnet IDs for the EKS cluster (control plane ENIs and default node placement).
    :type subnet_ids: list[pulumi.Input[str]]

    :param private_subnet_ids: Private subnet IDs for node groups. Falls back to ``subnet_ids`` if not provided.
    :type private_subnet_ids: list[pulumi.Input[str]], optional

    :param public_subnet_ids: Public subnet IDs for public load balancers. Defaults to [].
    :type public_subnet_ids: list[pulumi.Input[str]], optional

    :param kubernetes_version: Kubernetes version for the cluster (e.g. ``"1.31"``). Defaults to ``"1.31"``.
    :type kubernetes_version: str, optional

    :param cluster_logging: List of EKS control plane log types to enable. Defaults to
        ``["api", "audit", "authenticator"]``.
    :type cluster_logging: list[str], optional

    :param endpoint_private_access: Whether the cluster API endpoint is accessible from within the VPC.
        Defaults to ``True``.
    :type endpoint_private_access: bool, optional

    :param endpoint_public_access: Whether the cluster API endpoint is publicly accessible.
        Defaults to ``True``.
    :type endpoint_public_access: bool, optional

    :param public_access_cidrs: CIDR blocks allowed to reach the public API endpoint.
        Defaults to ``["0.0.0.0/0"]``.
    :type public_access_cidrs: list[str], optional

    :param enable_kms_encryption: Whether to create a KMS key for etcd secret encryption.
        Defaults to ``True``.
    :type enable_kms_encryption: bool, optional

    :param node_groups: Dict of managed node group configurations. Each key is the node group name and
        the value is a dict of options passed to ``pulumi_eks.ManagedNodeGroup`` (e.g. ``instance_types``,
        ``scaling_config``, ``ami_type``, ``disk_size``, ``labels``, ``taints``). Defaults to {}.
    :type node_groups: dict, optional

    :param addons: Dict of EKS add-on configurations. Keys are add-on names (e.g. ``"vpc-cni"``), values
        are dicts of additional ``aws.eks.Addon`` arguments (e.g. ``addon_version``). Defaults to the standard
        set: vpc-cni, kube-proxy, coredns, aws-ebs-csi-driver.
    :type addons: dict, optional

    :param enable_gp3_storage_class: Whether to create a gp3 StorageClass and set it as default.
        Defaults to ``True``.
    :type enable_gp3_storage_class: bool, optional

    :param opts: Additional pulumi.ResourceOptions to apply to these resources. Defaults to None.
    :type opts: pulumi.ResourceOptions, optional

    :param tags: Additional tags to merge with project common tags. Defaults to {}.
    :type tags: dict, optional

    :raises ValueError: When no subnet IDs are provided.
    """

    # vpc-cni and kube-proxy are managed by pulumi_eks.Cluster internally;
    # only include addons not already handled by the cluster provider.
    DEFAULT_ADDONS = ['coredns', 'aws-ebs-csi-driver']
    DEFAULT_LOG_TYPES = ['api', 'audit', 'authenticator']

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        vpc_id: pulumi.Input[str],
        subnet_ids: list[pulumi.Input[str]],
        private_subnet_ids: list[pulumi.Input[str]] = None,
        public_subnet_ids: list[pulumi.Input[str]] = None,
        kubernetes_version: str = '1.31',
        cluster_logging: list[str] = None,
        endpoint_private_access: bool = True,
        endpoint_public_access: bool = True,
        public_access_cidrs: list[str] = None,
        enable_kms_encryption: bool = True,
        node_groups: dict = {},
        addons: dict = None,
        enable_gp3_storage_class: bool = True,
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
    ):
        if not subnet_ids:
            raise ValueError('You must provide at least one subnet ID.')

        super().__init__('tb:eks:EksCluster', name, project, opts=opts, tags=tags)

        if cluster_logging is None:
            cluster_logging = self.DEFAULT_LOG_TYPES
        if public_access_cidrs is None:
            public_access_cidrs = ['0.0.0.0/0']
        # pulumi_eks.Cluster treats subnet_ids and private/public_subnet_ids as
        # mutually exclusive. Use the split approach when either is provided;
        # fall back to subnet_ids only when neither is given.
        use_split_subnets = private_subnet_ids is not None or public_subnet_ids is not None
        if private_subnet_ids is None:
            private_subnet_ids = subnet_ids
        if public_subnet_ids is None:
            public_subnet_ids = []

        # --- KMS key for envelope encryption of etcd secrets ---
        kms_key = None
        encryption_config_key_arn = None
        if enable_kms_encryption:
            kms_key = aws.kms.Key(
                f'{name}-eks-kms',
                description=f'KMS key for EKS cluster {name} etcd secret encryption',
                enable_key_rotation=True,
                tags=self.tags,
                opts=pulumi.ResourceOptions(parent=self),
            )
            aws.kms.Alias(
                f'{name}-eks-kms-alias',
                name=f'alias/{name}-eks',
                target_key_id=kms_key.key_id,
                opts=pulumi.ResourceOptions(parent=self),
            )
            encryption_config_key_arn = kms_key.arn

        # --- Shared IAM role for managed node groups ---
        # Created before the cluster so it can be registered in instanceRoles
        # (required by pulumi_eks for aws-auth ConfigMap mapping).
        node_role = aws.iam.Role(
            f'{name}-node-role',
            name=f'{name}-node',
            assume_role_policy=json.dumps(
                {
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Effect': 'Allow',
                            'Principal': {'Service': 'ec2.amazonaws.com'},
                            'Action': 'sts:AssumeRole',
                        }
                    ],
                }
            ),
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )
        for policy_arn in [
            'arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy',
            'arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy',
            'arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly',
        ]:
            policy_name = policy_arn.rsplit('/', 1)[-1]
            aws.iam.RolePolicyAttachment(
                f'{name}-node-{policy_name}',
                role=node_role.name,
                policy_arn=policy_arn,
                opts=pulumi.ResourceOptions(parent=self),
            )

        # --- EKS Cluster via pulumi_eks ---
        cluster_subnet_kwargs = (
            {'private_subnet_ids': private_subnet_ids, 'public_subnet_ids': public_subnet_ids}
            if use_split_subnets
            else {'subnet_ids': subnet_ids}
        )
        cluster = eks.Cluster(
            f'{name}-cluster',
            name=name,
            vpc_id=vpc_id,
            **cluster_subnet_kwargs,
            instance_roles=[node_role],
            version=kubernetes_version,
            enabled_cluster_log_types=cluster_logging,
            endpoint_private_access=endpoint_private_access,
            endpoint_public_access=endpoint_public_access,
            public_access_cidrs=public_access_cidrs,
            encryption_config_key_arn=encryption_config_key_arn,
            create_oidc_provider=True,
            skip_default_node_group=True,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # --- IAM role for EBS CSI driver (IRSA) ---
        ebs_csi_role = None
        if addons is None or 'aws-ebs-csi-driver' in (addons or {}):
            ebs_csi_role = self._create_ebs_csi_irsa_role(name, cluster)

        # --- Managed Node Groups ---
        managed_node_groups = {}
        for ng_name, ng_config in node_groups.items():
            ng_config = ng_config.copy()

            # Extract scaling config
            scaling = ng_config.pop('scaling_config', {})
            scaling_config = aws.eks.NodeGroupScalingConfigArgs(
                desired_size=scaling.get('desired_size', 2),
                min_size=scaling.get('min_size', 1),
                max_size=scaling.get('max_size', 3),
            )

            # Extract known args, pass rest through
            instance_types = ng_config.pop('instance_types', ['t3.medium'])
            ami_type = ng_config.pop('ami_type', 'AL2023_x86_64_STANDARD')
            disk_size = ng_config.pop('disk_size', 50)
            labels = ng_config.pop('labels', {})
            taints = ng_config.pop('taints', [])
            ng_subnet_ids = ng_config.pop('subnet_ids', private_subnet_ids)

            taint_args = [
                aws.eks.NodeGroupTaintArgs(
                    key=t['key'],
                    value=t.get('value', ''),
                    effect=t.get('effect', 'NO_SCHEDULE'),
                )
                for t in taints
            ]

            mng = eks.ManagedNodeGroup(
                f'{name}-ng-{ng_name}',
                cluster=cluster,
                node_group_name=f'{name}-{ng_name}',
                node_role=node_role,
                instance_types=instance_types,
                ami_type=ami_type,
                disk_size=disk_size,
                scaling_config=scaling_config,
                labels=labels,
                taints=taint_args if taint_args else None,
                subnet_ids=ng_subnet_ids,
                tags=self.tags,
                opts=pulumi.ResourceOptions(parent=self),
            )
            managed_node_groups[ng_name] = mng

        # --- EKS Managed Add-ons ---
        addon_names = list((addons or {}).keys()) if addons is not None else self.DEFAULT_ADDONS
        addon_configs = addons or {a: {} for a in self.DEFAULT_ADDONS}
        created_addons = {}

        for addon_name in addon_names:
            addon_cfg = addon_configs.get(addon_name, {}).copy()

            addon_kwargs = {}
            if addon_name == 'aws-ebs-csi-driver' and ebs_csi_role is not None:
                addon_kwargs['service_account_role_arn'] = ebs_csi_role.arn

            # Allow overriding addon_version and resolve_conflicts from config
            addon_version = addon_cfg.pop('addon_version', None)
            resolve_conflicts = addon_cfg.pop('resolve_conflicts_on_update', 'OVERWRITE')

            addon = aws.eks.Addon(
                f'{name}-addon-{addon_name}',
                cluster_name=cluster.eks_cluster.name,
                addon_name=addon_name,
                addon_version=addon_version,
                resolve_conflicts_on_update=resolve_conflicts,
                tags=self.tags,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[cluster]),
                **addon_kwargs,
            )
            created_addons[addon_name] = addon

        # --- gp3 default StorageClass ---
        gp3_storage_class = None
        if enable_gp3_storage_class:
            k8s_provider = k8s.Provider(
                f'{name}-k8s-provider',
                kubeconfig=cluster.kubeconfig_json,
                opts=pulumi.ResourceOptions(parent=self),
            )

            gp3_storage_class = k8s.storage.v1.StorageClass(
                f'{name}-gp3-sc',
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    name='gp3',
                    annotations={
                        'storageclass.kubernetes.io/is-default-class': 'true',
                    },
                ),
                provisioner='ebs.csi.aws.com',
                parameters={
                    'type': 'gp3',
                    'fsType': 'ext4',
                },
                volume_binding_mode='WaitForFirstConsumer',
                reclaim_policy='Delete',
                allow_volume_expansion=True,
                opts=pulumi.ResourceOptions(
                    parent=self,
                    provider=k8s_provider,
                    depends_on=[created_addons.get('aws-ebs-csi-driver', cluster)],
                ),
            )

        # --- Expose key outputs ---
        self.cluster = cluster
        self.kubeconfig = cluster.kubeconfig
        self.kubeconfig_json = cluster.kubeconfig_json
        self.oidc_provider_arn = cluster.oidc_provider_arn
        self.oidc_provider_url = cluster.oidc_provider_url
        self.cluster_security_group_id = cluster.cluster_security_group_id
        self.node_security_group_id = cluster.node_security_group_id

        self.finish(
            resources={
                'cluster': cluster,
                'node_groups': managed_node_groups,
                'addons': created_addons,
                'kms_key': kms_key,
                'gp3_storage_class': gp3_storage_class,
                'ebs_csi_role': ebs_csi_role,
                'node_role': node_role,
            }
        )

    def _create_ebs_csi_irsa_role(
        self,
        name: str,
        cluster: eks.Cluster,
    ) -> aws.iam.Role:
        """Creates an IAM role for the EBS CSI driver using IRSA (IAM Roles for Service Accounts).

        :param name: Base name for resource naming.
        :param cluster: The EKS cluster to bind the OIDC provider from.
        :returns: The IAM role for the EBS CSI driver.
        """
        oidc_arn = cluster.oidc_provider_arn
        oidc_issuer = cluster.oidc_issuer  # URL without https:// prefix, for IAM condition keys

        assume_role_policy = pulumi.Output.all(oidc_arn, oidc_issuer).apply(
            lambda args: json.dumps(
                {
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Effect': 'Allow',
                            'Principal': {'Federated': args[0]},
                            'Action': 'sts:AssumeRoleWithWebIdentity',
                            'Condition': {
                                'StringEquals': {
                                    f'{args[1]}:sub': 'system:serviceaccount:kube-system:ebs-csi-controller-sa',
                                    f'{args[1]}:aud': 'sts.amazonaws.com',
                                }
                            },
                        }
                    ],
                }
            )
        )

        role = aws.iam.Role(
            f'{name}-ebs-csi-role',
            name=f'{name}-ebs-csi-driver',
            assume_role_policy=assume_role_policy,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        aws.iam.RolePolicyAttachment(
            f'{name}-ebs-csi-policy',
            role=role.name,
            policy_arn='arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy',
            opts=pulumi.ResourceOptions(parent=self),
        )

        return role
