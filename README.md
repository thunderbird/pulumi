# pulumi

Common Pulumi elements for use in Thunderbird infrastructure development.

## Usage

Typically, you want to implement the classes defined in this module to define infrastructure
resources to support your application. These represent common infrastructural patterns which you can
customize to some degree.

Full documentation is found on [Github Pages](https://thunderbird.github.io/pulumi/).

If you require documentation for a specific version, check out that branch and build the docs yourself:

```bash
git checkout v0.0.7
virtualenv venv
. ./venv/bin/activate
pip install .[dev]
cd docs
make clean html
firefox _build/html/index.html
```

## Preparing a Release

Releases are made as branches because Python/pip does not allow using tags as references. These branches are protected
from push events after the branch is initially created. There is some automation set up to do some of these things, but
it does not work due to some authentication problems. This is currently the process to release a version of this
module.

1. Ensure that all PRs that are going into the release have been merged.
2. Close all issues related to the [Github milestone](https://github.com/thunderbird/pulumi/milestones) for the release.
3. On your local machine, pull the latest commits for the `main` branch.
    - `git checkout main`
    - `git pull`
4. Create a new branch in which we will update the release data.
    - `git checkout -b release-prep`
5. Update `CHANGELOG.md` to include a common-language listing of the major changes. Use the Github milestone as a guide.
6. Update `pyproject.toml` so the version matches the version you are trying to release.
7. Add these files to a commit and open a PR. Get approval and merge the PR.
8. Again, `checkout` and `pull` the `main` branch, which now includes the right version data.
9. Checkout and push a branch named after your version. This should always begin with the lowercase letter `v`, which
    should be followed by the correct [semantic version](https://semver.org), such as `v0.0.10`.
    - `git checkout -b v0.0.10`
    - `git push -u origin v0.0.10`