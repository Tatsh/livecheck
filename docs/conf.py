"""
Configuration file for the Sphinx documentation builder.
https://www.sphinx-doc.org/en/master/usage/configuration.html
"""  # noqa: INP001
from datetime import UTC, datetime
from pathlib import Path
from typing import Final
import sys

import toml

with (Path(__file__).parent.parent / 'pyproject.toml').open() as f:
    PROJECT = toml.load(f)
# region Path setup
# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
sys.path.insert(0, str(Path(__file__).parent.parent))
# endregion
author: Final[str] = PROJECT['tool']['poetry']['authors'][0]
copyright: Final[str] = str(datetime.now(tz=UTC).year)  # noqa: A001
project: Final[str] = PROJECT['tool']['poetry']['name']
version: Final[str] = PROJECT['tool']['poetry']['version']
'''The short X.Y version.'''
release: Final[str] = f'v{version}'
'''The full version, including alpha/beta/rc tags.'''
extensions: Final[list[str]] = (
    ['sphinx.ext.autodoc', 'sphinx.ext.napoleon'] +
    (['sphinx_click'] if PROJECT['tool']['poetry'].get('scripts') else []))
'''
Add any Sphinx extension module names here, as strings. They can be extensions
coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
'''
templates_path: Final[list[str]] = ['_templates']
'''Add any paths that contain templates here, relative to this directory.'''
exclude_patterns: Final[list[str]] = []
'''
List of patterns, relative to source directory, that match files and
directories to ignore when looking for source files. This pattern also affects
html_static_path and html_extra_path.
'''
master_doc: Final[str] = 'index'
html_static_path: Final[list[str]] = []
'''
Add any paths that contain custom static files (such as style sheets) here,
relative to this directory. They are copied after the builtin static files, so
a file named "default.css" will overwrite the builtin "default.css".
'''
html_theme: Final[str] = 'alabaster'
'''
The theme to use for HTML and HTML Help pages.  See the documentation for a
list of builtin themes.
'''
