# pulumi

Common Pulumi elements for use in Thunderbird infrastructure development.

## Usage

Typically, you want to implement the classes defined in these modules which extend the
`ThunderbirdComponentResource` class. These represent common infrastructural patterns which you can
customize to some degree.

See the [Documentation](#documentation) section below for details on how to include this in your
project and use each kind of resource.


## Pulumi setup

Our Pulumi code is developed against Python 3.12 or later. If this is not your default version, you'll need to manage your own virtual environment.

Check your default version:

```sh
$ python -V
Python 3.12.4
```

If you need a newer Python, [download and install it](https://www.python.org/downloads/). Then you'll have to set up the virtual environment yourself with something like this:

```sh
virtualenv -p /path/to/python3.12 venv
./venv/bin/pip install -r requirements.txt
```

After this, `pulumi` commands should work. If 3.12 is your default version of Python, Pulumi should set up its own virtualenv, and you should not have to do this.


## Start a new Pulumi project

### S3 bucket

Create an S3 bucket in which to store state for the project. Generally, you should follow this
naming scheme:

```
tb-$PROJECT_NAME-pulumi
```

One bucket can hold states for all of that project's stacks, so you only need to create the one
bucket per project.


### Repo setup

You probably already have a code repo with your application code in it. If not, create such a repo.

Create a directory there called `pulumi` and create a new project and stack in it. You'll need the
name of the S3 bucket from the previous step here. If you are operating in an AWS region other than
what is set as your default for AWSCLI, be sure to `export AWS_REGION=us-east-1` or whatever else
you may need to do to override that.

```sh
cd pulumi
pulumi login s3://$S3_BUCKET_NAME
pulumi new aws-python
```

Follow the prompts to get everything named.


### Set up this module

Add this repo as a submodule to your application's repo. The `-b` argument is optional, though you
can use this to ensure your code is locked to a specific version of this module. Note that git only
accepts branch names, and you cannot use things like tags or commit hashes for this function.

```sh
# Run from the root directory of the repo
git submodule add -b $BRANCH_NAME git@github.com:thunderbird/pulumi.git tb_pulumi
```

Create symlinks to the `tb_pulumi` module and its pip requirements:

```sh
cd pulumi
ln -s ../tb_pulumi/tb_pulumi ./tb_pulumi
ln -s ../tb_pulumi/requirements.txt ./requirements.txt
```

Commit these symlinks to your repo.

Pulumi will need these requirements installed. On your first run of a `pulumi preview` command (or
some others), Pulumi will attempt to set up its working environment. If this fails, or you need to
make adjustments later, you can assume Pulumi's virtual environment to perform pip changes. Assuming
Pulumi's virtual environment lives at `venv`, run:

```sh
./venv/bin/pip install -U -r requirements.txt
```

You can now develop Python Pulumi code in that directory, referring to this module with imports such
as these:

```python
import tb_pulumi

# ...or...

from tb_pulumi import (ec2, fargate, secrets)
```


### Use this module

When you issue `pulumi` commands (like "up" and "preview" and so on), it looks for a `__main__.py`
file in your current directory and executes the code in that file. To use this module, you'll import
it into that file and complete a few steps, namely:

 - Create a config file for your stack
 - Define a `ThunderbirdPulumiProject`
 - Declare some `ThunderbirdComponentResource`s

#### Create a config file

It is assumed that a config file will exist at `config.$STACK.yaml` where `$STACK` is the currently
selected Pulumi stack. This file must contain a mapping of names of config settings to their desired
values. Currently, only one such setting is recognized. That is `resources`.

This is a mostly arbitary mapping that you will have to interpret on your own (more on that later),
but some conventions are recommended. Namely:

  - `resources` should be a mapping where the keys are the Pulumi type-strings for the resources
        they are configuring. For example, if you want to build a VPC with several subnets, you
        might use the `tb_pulumi.network.MultiCidrVpc` class. Following this convention, that should
        be accompanied by a `tb:network:MultiCidrVpc` key in this mapping.
  - The values these keys map to should themselves be mappings. This provides a convention where
        more than one of each pattern are configurable. The keys here should be arbitrary but unique
        identifiers for the resources being configured. F/ex: `backend` or `api`.
  - The values these keys map to should be a mapping where the keys are valid configuration
        options for the resources being built. The full listing of these values can be found by
        browsing the [documentation](#documentation).


#### Define a ThunderbirdPulumiProject

In your `__main__.py` file, start with a simple skeleton:

```python
import tb_pulumi

project = tb_pulumi.ThunderbirdPulumiProject()
```

If you have followed the conventions outlined above, `project` is now an object with a key property,
`config`, which gives you access to the config file's data. You can use this in the next step to
feed parameters into resource declarations.


#### Declare ThunderbirdComponentResources

A `pulumi.ComponentResource` is a collection of related resources. In an effort to keep consistent
tagging and such across all Thunderbird infrastructure projects, the resources available in this
module all extend a custom class called a `ThunderbirdComponentResource`. If you have
followed the conventions outlined so far, it should be easy to stamp out common patterns with them
by passing config options into the constructors for these classes.


#### A brief example

Consider a situation where we want to configure a VPC with two subnets in two different AZs. We
might write a config file for our staging environment (`config.staging.yaml`) like so:

```yaml
---
resources:
  tb:network:MultiCidrVpc:
    my_vpc:
      cidr_block: 10.0.0.0/16
      subnets:
        us-east-1a:
          - 10.0.100.0/24
        us-east-1b:
          - 10.0.101.0/24
```

The full `__main__.py` file might look like this (perhaps with less commentary):

```python
import tb_pulumi  # Import the core library
import tb_pulumi.network  # Import the network module

project = tb_pulumi.ThunderbirdPulumiProject()  # Set up the project
resources = project.config.get('resources', {}) # Put resources into a convenience variable
my_vpc_opts = resources['tb:network:MultiCidrVpc']['my_vpc']  # Extract the data we care about
my_vpc = tb_pulumi.network.MultiCidrVpc(  # Build a MultiCidrVpc
    f'{project.name_prefix}-vpc',  # For consistent naming of resources, use project.name_prefix
    project,  # Tell the component resource what project it belongs to
    **my_vpc_opts)  # Unpack the configuration directly into the function call
```

A `pulumi up` would list out several resources to be built:

  - A VPC
  - A subnet for each of the two CIDRs defined
  - Route table/subnet associations
  - An Internet gateway
  - A NAT gateway

Alterations can be made in the YAML file.


## Documentation
<a name="documentation"></a>

Documentation for this module is currently maintained through this readme and the commentary in the
code. If you like, you can browse that commentary using pydoc. `cd` into this repo and run:

```sh
python -m pydoc -p 8080 .
```

Then click [this link](http://localhost:8080/tb_pulumi.html).


## Implementing ThunderbirdComponentResources

So you want to develop a new pattern to stamp out? Here's what you'll need to do:

  - Determine the best place to put the code. Is there an existing module that fits the bill?
  - Determine the Pulumi type string for it. This goes: `org:module:class`. The `org` will always
      be "tb". The `module` will be the Python submodule you're placing the new class in. The
      `class` is whatever you've called the class.
  - Design the class following these guidelines:
    - The constructor should always accept, before any other arguments, the following positional
        options:
        - **name:** The internal name of the resource as Pulumi tracks it.
        - **project:** The ThunderbirdPulumiProject these resources belong to.
    - The constructor should always accept the following keyword arguments:
        - **opts:** A `pulumi.ResourceOptions` object which will get merged into the default set of
            arguments managed by the project.
    - The constructor should explicitly define only those arguments that you intend to have
        default values which differ from the default values the provider will set, or which imply
        larger patterns (such as "build_jumphost" implying other resources, like a security group
        and its rules, not just an EC2 instance).
    - The constructor may accept a final `**kwargs` argument with arbitrary meaning. Because the
        nature of a component resource is to compile many other resources into one class, it is
        not implicitly clear what "everything else" should apply to. If this is implemented, its
        function should be clearly documented in the class.
    - The class should extend `tb_pulumi.ThunderbirdComponentResource`.
    - The class should call its superconstructor in the following way:
      - `super().__init__(typestring, name, project, opts=opts)`
    - Any resources you create should always be assigned a key in `self.resources`.
    - Any resources you create must have the `parent=self` pulumi.ResourceOption set.
    - At the end of the `__init__` function, you must call `self.finish()`
