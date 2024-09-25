import os
import sys

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'tb_pulumi'
copyright = '2024, Thunderbird'
author = 'Ryan Jung, et al'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ['sphinx.ext.autodoc']

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# html_theme = 'readable'
# html_theme_path = [sphinx_readable_theme.get_html_theme_path()]

html_theme = 'insegel' # Clean black-on-white theme
# html_theme = 'furo'  # Uncomment if you prefer dark mode
html_static_path = ['_static']

# -- Override path to read our docstrings
sys.path.insert(0, os.path.abspath('..'))
