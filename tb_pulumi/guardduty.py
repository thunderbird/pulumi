"""Patterns related to AWS GuardDuty."""

# import json
import pulumi
import pulumi_aws as aws
import tb_pulumi


class GuardDutyAccount(tb_pulumi.ThunderbirdComponentResource):
    """**Pulumi Type:** ``tb:guardduty:GuardDutyAccount``
    Enable and Configure AWS GuardDuty for an account/region.

    Produces the following ``resources``:

    """

    def __init__(
        self,
        name: str,
        project: tb_pulumi.ThunderbirdPulumiProject,
        features: dict = {},
        opts: pulumi.ResourceOptions = None,
        tags: dict = {},
        **kwargs,
    ):
        exclude_from_project = kwargs.pop('exclude_from_project', False)
        if 'exclude_from_project' in kwargs:
            exclude_from_project = kwargs['exclude_from_project'] or False
            del kwargs['exclude_from_project']

        super().__init__(
            'tb:guardduty:GuardDutyAccount',
            name=f'{name}-gdacc',
            project=project,
            exclude_from_project=exclude_from_project,
            opts=opts,
            tags=tags,
        )
        # create detector for project region
        guardduty_detector = aws.guardduty.Detector(f'{name}-guardduty', enable=True, opts=pulumi.ResourceOptions())

        # enable features as needed
        enabled_features = {}
        if features:
            for feature in features:
                enabled_features[feature['name']] = aws.guardduty.DetectorFeature(
                    f'{name}-{feature["name"]}',
                    detector_id=guardduty_detector.id,
                    name=feature['name'],
                    status=feature['status'],
                    additional_configurations=feature.get('additional_configurations', None),
                    opts=pulumi.ResourceOptions(parent=guardduty_detector),
                )

        # feature:
        self.finish(
            resources={
                'guardduty_detector': guardduty_detector,
                'enabled_features': enabled_features,
            }
        )
