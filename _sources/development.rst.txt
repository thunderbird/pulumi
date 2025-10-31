.. _development:

Development
===========

This page contains information about how to develop tb_pulumi itself, as well as how to develop your own infrastructure
code using tb_pulumi.


Developing Projects with tb_pulumi
----------------------------------

Here are some tips on maintaining infrastructure projects using tb_pulumi.


Project setup
^^^^^^^^^^^^^

In most organizations, infrastructure is managed by a plurality of people. When your infrastructure is code, you need to
have some kind of version control in place. We strongly recommend the use of ``git`` or another code control tool.

Your tb_pulumi code should typically live alongside the software it's hosting, which makes continuous integration
simpler. We recommend you store your tb_pulumi code in a directory called ``pulumi/`` alongside your applications.

When you first start a project, we recommend using the :ref:`quickstart` because it walks through all of the first-run
Pulumi steps for you and creates all the files you need. While it may not define the resources you need, it ends with a
working program that you can begin to tweak. If you point this script at your code repo, it will create the ``pulumi/``
directory for you and set up the skeleton project.

You should also source the ``dev-setup.sh`` script each time to begin to work on the project. This ensures that you have
all of the normal development tools installed and ready for use. It also sets up various git hooks to help us ensure
consistently formatted Python files in PRs we review.

.. code-block::

  $ source dev-setup.sh

   · Ensuring this setup tool can log its progress ............. ✅
   · Making sure you're not already in a virtual environment ... ✅
   · Checking for conflicting virtual environment files ........ ✅
   · Building a fresh virtual environment ...................... ✅
   · Activating the virtual environment ........................ ✅
   · Installing/updating dev dependencies ...................... ✅
   · Bootstrapping pre-commit hooks ............................ ✅

**Notes:**

- To leave the virtual environment, run ``deactivate``.

- To destroy the virtual environment, deactivate it, then run ``rm -rf .venv`` in the project root.

- To forcibly rebuild the virtual environment, destroy it, then re-source the script.

- The ``dev-setup.sh`` script can be copied into other Pulumi projects, and it should work as-is. The quickstart script
  does this by default.


Development loop
^^^^^^^^^^^^^^^^

Once you begin, the overall development loop looks something like this:

#. Adjust code to do what you need.

#. ``pulumi preview``.

#. Repeat until you're satisfied with the preview.

#. ``pulumi up``

#. Verify the infrastructure.

#. Tweak and repeat as needed.


Pull request requirements
^^^^^^^^^^^^^^^^^^^^^^^^^

A pull request will not be accepted if our automated tests do not pass. At the current moment, that means:


Linting/formatting must pass
""""""""""""""""""""""""""""

We use the `Ruff <https://docs.astral.sh/ruff/>`_ tool to ensure consistent code style and to prevent common code issues
from cropping up. Before you submit a PR, make sure that you have installed our dev dependencies and have run Ruff
against your code.

.. code-block:: bash

  # You can create your own virtualenv for dev stuff, but it's also okay to reuse Pulumi's
  source ./venv/bin/activate
  pip install .[dev]
  ruff format
  ruff check --fix

If the "check" call produces errors it cannot automatically fix, you will need to fix them before submitting your PR.


Documentation must build
""""""""""""""""""""""""

The dev dependencies also include `sphinx <https://github.com/sphinx-doc/sphinx>`_, the tool we use for generating our
documentation. When a PR is merged into the ``main`` branch, we automatically build and publish these docs to GitHub
Pages. Thus, we do not accept PRs if the documentation does not build without error.

Before submitting a PR, ensure that the documentation builds:

.. code-block:: bash

  # Again with the Pulumi virtualenv
  source ./venv/bin/activate
  pip install .[dev]
  cd docs
  make clean html


Working across multiple projects and stacks
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Here are some good ideas you can have for free:

- The severity of headaches caused by the use of an infrastructure-as-code tool are strongly correlated to the
  complexity of the infrastructure being managed by said tool. Therefore, you will have fewer headaches managing smaller
  chunks of infra supporting smaller chunks of your application than you will trying to control a large network of
  microservices all at once within the same project. Even if you develop many applications within a large monorepo, we
  recommend developing a tb_pulumi project per application; or you can map this concept to your organizational structure
  as it makes sense. The point is to create boundaries of relevance between your resources.
- Secrets should be protected, obviously, but they should also be designed to protect you from the impact of exposure.
  In Pulumi, your secret passphrase is all that stands between your (maybe public?) ``Pulumi.stack.yaml`` file and
  someone decrypting those values. This passphrase should be kept secret, probably should be stored in an encrypted
  password manager, and definitely only doled out to trustworthy folks who actually need it. But moreover, every stack
  you build should have a unique passphrase. That way, if you do expose a passphrase on accident, the data that can be
  plaintexted from that is limited to a single environment.
- Typing a lot of repetitive commands really sucks, and automating things totally rules. You should consider writing a
  script that automates setting the context of your various Pulumi environments. Consider a script such as this:

.. code-block:: bash

  #!/bin/bash
  
  ### Usage:
  #
  #     source pulumi-setup $project $stack $region
  
  # Name some positional command line arguments
  PROJECT=$1
  STACK=$2
  REGION=${3:-us-east-1}
  
  # Unset the passphrase variable if it's set
  if [ "$PULUMI_CONFIG_PASSPHRASE" != "" ]; then
      unset PULUMI_CONFIG_PASSPHRASE
  fi
  
  # Point Pulumi to a file on disk where the passphrase is stored
  export PULUMI_CONFIG_PASSPHRASE_FILE="~/.pulumi.$PROJECT.$STACK.pass"
  export AWS_REGION=$REGION
  export AWS_DEFAULT_REGION=$REGION
  
  # Set up the local Pulumi client
  pulumi login
  pulumi stack select $STACK

With this model, you can place passphrases into dotfiles on your local (and presumably encrypted) disk...

.. code-block:: bash

  # Sure, you could `echo 'my-passphrase' > file`, but then you have your
  # passphrase in your shell history. So open the file with a text editor
  # instead, and paste it in.
  $EDITOR ~/.pulumi.myproject.mystack.pass

...and then assume that environment by sourcing the script (which we'll assume here has been stashed at
``~/bin/pulumi-setup``):

.. code-block:: bash

  source ~/bin/pulumi-setup myproject mystack eu-central-1

Or you can extend this concept however you like. Another cool idea is to have a script that implements your password
manager's API such that the passphrases are pulled live, straight into the environment, without ever touching a disk.
You could even use Pulumi's `automation module
<https://www.pulumi.com/docs/reference/pkg/python/pulumi/#module-pulumi.automation>`_ to wrap your tb_pulumi program in
other Python code that handles this sort of meta-task. The world is your cog to crank.


Developing tb_pulumi Itself
---------------------------

So what if you need tb_pulumi to do something it doesn't? You could implement a fix or an improvement in your downstream
project, but then the rest of us don't get the benefit of those changes. The best thing to do is to change the core
library.

Before you do this...

- Make sure you've tested against the latest tb_pulumi code (use the ``main`` branch).
- Make sure there isn't an `open issue <https://github.com/thunderbird/pulumi/issues/>`_ about your problem.
- `Open a new issue <https://github.com/thunderbird/pulumi/issues/new/choose>`_ describing your problem. Assign it to
  yourself.

When you're ready to work the issue...

- Fork tb_pulumi into your own GitHub repo.
- Create a new branch.

Create or use an infrastructure project to test your change in. It is often best to build a bespoke project that sets up
the bare minimum infrastructure required to demonstrate the change. This helps us understand the change and reproduce
the problem if we need to.

To test a change in tb_pulumi:

- Commit your changes to your forked tb_pulumi branch.
- Push the branch to GitHub or whatever other git service you want to use.
- Adjust your test project's ``requirements.txt`` so it uses your repo and branch.
- Delete Pulumi's virtual environment.
- Run a ``pulumi preview --diff``.

This will cause Pulumi to rebuild its virtual environment using your special version of tb_pulumi. If your change is
effective, you should see the expected result in the diff. Repeat this cycle to make further changes.


Implementing a new ``ThunderbirdComponentResource``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you want to build out a completely new pattern of resources that can be reused commonly, here's what you'll need to
do:

First, determine the best place to put the code. Is there an existing module that fits the bill? Generally, (but
`certainly not always <https://github.com/thunderbird/pulumi/issues/177>`_), our code is organized around the most
prominent service involved in that pattern.

Then determine the Pulumi type string for it. This goes: ``org:module:class``. The ``org`` should be unique to your
organization. For Thunderbird projects, including tb_pulumi, it should be ``tb``. The ``module`` will be the Python
submodule you're placing the new class in (e.g., classes in ``network.py`` should use ``network`` here). The ``class``
is whatever you've called the class.

The best way to work through the requirements of one of these things is to look at an existing
ThunderbirdComponentResource. They all follow very similar patterns. Specifically, they adhere to these guidelines:

#. The class should have a sufficient docstring that contains all of the following:

   - The class's Pulumi type.

   - A description of what the pattern accomplishes.

   - An explicit and complete listing of every resource the class produces. This should indicate what the actual data
     type of each resource is and where to find further documentation on it. This is absolutely necessary from a
     development perspective, as we try to surface as many options from the provider to the user by using the
     code patterns described in :ref:`patterns_of_use`. We don't need to re-document those provider options, but we do
     need to inform users where to find them.

   - A listing of parameters, errors thrown, and return values in `Sphinx autodoc
     <https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html>`_ format. This documentation includes the
     detailed module documentation that lives in these docstrings, so it's important to keep the docstrings up to date.

#. The constructor should always accept, before any other arguments, the following positional options:

   - ``name``: The internal name of the resource as Pulumi tracks it.

   - ``project``: The ThunderbirdPulumiProject these resources belong to.

#. The constructor should always accept the following keyword arguments:

   - ``opts``: A ``pulumi.ResourceOptions`` object which will get merged into the default set of arguments managed
     by the project.

#. The constructor should explicitly define only those arguments which will have default values differing from those the
   provider will set, or which imply larger patterns (like an ``enable_feature_x`` option that results in many resources
   being built to support that feature).

#. The constructor may accept a final ``**kwargs`` argument with arbitrary meaning. Because the nature of a component
   resource is to compile many other resources into one class, it is not implicitly clear what "everything else" really
   means. If this is implemented, its function should be clearly documented in the class. If this isn't passed into the
   superconstructor, you will need to implement all superconstructor arguments into your constructor.

#. The class should extend :py:class:`tb_pulumi.ThunderbirdComponentResource`.

#. The class should make an appropriate call to its superconstructor, which ensures the resources can be properly
   tracked in the project (among other things).

#. Any resources you create must have the ``parent=self`` ``pulumi.ResourceOption`` set. Set an appropriate
   ``depends_on`` value when necessary.

#. If your ThunderbirdComponentResource defines other ThunderbirdComponentResources, you should pass the
   ``exclude_from_project=True`` option into the nested constructor. This prevents the resources defined in that nested
   collection from being referenced at the top level of the project while still remaining accessible programmatically
   through this ThunderbirdComponentResource. This setting is used to add clarity when debugging ProjectResourceGroups.

#. At the end of the ``__init__`` function, you must call ``self.finish()``, passing in a dictionary of ``resources``
   (see :py:meth:`tb_pulumi.ThunderbirdComponentResource.finish`). For
   :py:class:`tb_pulumi.ProjectResourceGroup` derivatives, call this at the end of the
   :py:meth:`tb_pulumi.ProjectResourceGroup.ready` function instead.


Documentation
-------------

This documentation is produced using the `Sphinx tool <https://www.sphinx-doc.org/en/master/>`_, the files in the
``docs`` directory of this repo, and the docstrings present throughout the code. This uses the `RST
<https://thomas-cokelaer.info/tutorials/sphinx/rest_syntax.html>`_ markup system. When submitting code changes, be sure
that any changes to the behavior of this library are reflected with appropriate documentation updates.