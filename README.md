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

If you prefer a dark theme, ``export TBPULUMI_DARK_MODE=yes`` before running ``make clean html``.