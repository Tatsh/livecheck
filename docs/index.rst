livecheck
=========

.. only:: html

   .. image:: https://img.shields.io/pypi/pyversions/livecheck.svg?color=blue&logo=python&logoColor=white
      :target: https://www.python.org/
      :alt: Python versions

   .. image:: https://img.shields.io/pypi/v/livecheck
      :target: https://pypi.org/project/livecheck/
      :alt: PyPI Version

   .. image:: https://img.shields.io/github/v/tag/Tatsh/livecheck
      :target: https://github.com/Tatsh/livecheck/tags
      :alt: GitHub tag (with filter)

   .. image:: https://img.shields.io/github/license/Tatsh/livecheck
      :target: https://github.com/Tatsh/livecheck/blob/master/LICENSE.txt
      :alt: License

   .. image:: https://img.shields.io/github/commits-since/Tatsh/livecheck/v0.1.4/master
      :target: https://github.com/Tatsh/livecheck/compare/v0.1.4...master
      :alt: GitHub commits since latest release (by SemVer including pre-releases)

   .. image:: https://github.com/Tatsh/livecheck/actions/workflows/codeql.yml/badge.svg
      :target: https://github.com/Tatsh/livecheck/actions/workflows/codeql.yml
      :alt: CodeQL

   .. image:: https://github.com/Tatsh/livecheck/actions/workflows/qa.yml/badge.svg
      :target: https://github.com/Tatsh/livecheck/actions/workflows/qa.yml
      :alt: QA

   .. image:: https://github.com/Tatsh/livecheck/actions/workflows/tests.yml/badge.svg
      :target: https://github.com/Tatsh/livecheck/actions/workflows/tests.yml
      :alt: Tests

   .. image:: https://coveralls.io/repos/github/Tatsh/livecheck/badge.svg?branch=master
      :target: https://coveralls.io/github/Tatsh/livecheck?branch=master
      :alt: Coverage Status

   .. image:: https://readthedocs.org/projects/livecheck/badge/?version=latest
      :target: https://livecheck.readthedocs.org/?badge=latest
      :alt: Documentation Status

   .. image:: https://www.mypy-lang.org/static/mypy_badge.svg
      :target: http://mypy-lang.org/
      :alt: mypy

   .. image:: https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white
      :target: https://github.com/pre-commit/pre-commit
      :alt: pre-commit

   .. image:: https://img.shields.io/badge/pydocstyle-enabled-AD4CD3
      :target: http://www.pydocstyle.org/en/stable/
      :alt: pydocstyle

   .. image:: https://img.shields.io/badge/pytest-zz?logo=Pytest&labelColor=black&color=black
      :target: https://docs.pytest.org/en/stable/
      :alt: pytest

   .. image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
      :target: https://github.com/astral-sh/ruff
      :alt: Ruff

   .. image:: https://static.pepy.tech/badge/livecheck/month
      :target: https://pepy.tech/project/livecheck
      :alt: Downloads

   .. image:: https://img.shields.io/github/stars/Tatsh/livecheck?logo=github&style=flat
      :target: https://github.com/Tatsh/livecheck/stargazers
      :alt: Stargazers

   .. image:: https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fpublic.api.bsky.app%2Fxrpc%2Fapp.bsky.actor.getProfile%2F%3Factor%3Ddid%3Aplc%3Auq42idtvuccnmtl57nsucz72%26query%3D%24.followersCount%26style%3Dsocial%26logo%3Dbluesky%26label%3DFollow%2520%40Tatsh&query=%24.followersCount&style=social&logo=bluesky&label=Follow%20%40Tatsh
      :target: https://bsky.app/profile/Tatsh.bsky.social
      :alt: Follow @Tatsh

   .. image:: https://img.shields.io/mastodon/follow/109370961877277568?domain=hostux.social&style=social
      :target: https://hostux.social/@Tatsh
      :alt: Mastodon Follow

Tool for overlays to update ebuilds. Inspired by the MacPorts ``port`` subcommand of the same name
and `nvchecker <https://github.com/lilydjwg/nvchecker>`_.

Commands
--------

.. click:: livecheck.main:main
   :prog: livecheck
   :nested: full

.. only:: html

   .. toctree::
      :maxdepth: 1

      lib

Indices and tables
==================
* :ref:`genindex`
* :ref:`modindex`
