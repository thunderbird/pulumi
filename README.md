# pulumi

Common Pulumi elements for use in Thunderbird infrastructure development.

## Usage

Typically, you want to implement the classes defined in this module to define infrastructure
resources to support your application. These represent common infrastructural patterns which you can
customize to some degree.

The `docs` folder contains some documentation, but it is best read in a web browser. To build and view the docs:

```bash
virtualenv venv
. ./venv/bin/activate
pip install .[dev]
cd docs
make clean html
firefox _build/html/index.html
```

If you prefer a dark theme, ``export TBPULUMI_DARK_MODE=yes`` before running ``make clean html``.