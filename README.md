# pulumi

Common Pulumi elements for use in Thunderbird infrastructure development.


## Usage

Typically, you want to implement the classes defined in this module to define infrastructure
resources to support your application. These represent common infrastructural patterns which you can
customize to some degree.

We recommend approaching the tool through the full documentation, which can be found on
[Github Pages](https://thunderbird.github.io/pulumi/).


## Contributing

To contribute, fork this repository, branch your fork, then commit your changes and push them to your fork. Open a pull
request against our repo's main branch. Tests must pass and the PR must pass review by a primary contributing member. 

We use the [ruff](https://docs.astral.sh/ruff/) tool to format our code and ensure common code problems are detected
without human error. Before submitting a PR, please install the dev requirements for the project and ensure your changes
do not fail ruff executions.

```bash
# Set up a working dev environment
git checkout -b your-branch
virtualenv venv
. ./venv/bin/activate
pip install .[dev]

# Format files so they adhere to our standards
ruff format

# Auto-fix simple code problems; point out others that can't be auto-fixed
ruff check --fix
```


## Building Documentation

Our CI workflows also require that the docs build without error. Before submitting a PR, you should verify this for
yourself:

```bash
cd docs
make clean html
```

This project's documentation is published automatically anytime the `main` branch changes. This may not always align
with the version you are using, since upgrading versions can be sometimes disruptive. If you require documentation for a
specific version, check out that branch and build the docs in the same way. You can view the output locally in your
favorite browser.

```bash
# Checkout version v0.0.11
git checkout v0.0.11
cd docs
make clean html
firefox _build/index.html
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
   If a change to the module introduces breaking changes or changes which potentially cause downtime while upgrading,
   leave a note to this effect in **bolded text!**
6. Update `pyproject.toml` so the version matches the version you are trying to release.
7. Add these files to a commit and open a PR. Get approval and merge the PR.
8. Again, `checkout` and `pull` the `main` branch, which now includes the right version data.
9. Checkout and push a branch named after your version. This should always begin with the lowercase letter `v`, which
    should be followed by the correct [semantic version](https://semver.org), such as `v0.0.11`.
    - `git checkout -b v0.0.11`
    - `git push -u origin v0.0.11`