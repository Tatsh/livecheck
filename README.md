# livecheck

[![Python versions](https://img.shields.io/pypi/pyversions/livecheck.svg?color=blue&logo=python&logoColor=white)](https://www.python.org/)
[![PyPI - Version](https://img.shields.io/pypi/v/livecheck)](https://pypi.org/project/livecheck/)
[![GitHub tag (with filter)](https://img.shields.io/github/v/tag/Tatsh/livecheck)](https://github.com/Tatsh/livecheck/tags)
[![License](https://img.shields.io/github/license/Tatsh/livecheck)](https://github.com/Tatsh/livecheck/blob/master/LICENSE.txt)
[![GitHub commits since latest release (by SemVer including pre-releases)](https://img.shields.io/github/commits-since/Tatsh/livecheck/v0.1.2/master)](https://github.com/Tatsh/livecheck/compare/v0.1.2...master)
[![CodeQL](https://github.com/Tatsh/livecheck/actions/workflows/codeql.yml/badge.svg)](https://github.com/Tatsh/livecheck/actions/workflows/codeql.yml)
[![QA](https://github.com/Tatsh/livecheck/actions/workflows/qa.yml/badge.svg)](https://github.com/Tatsh/livecheck/actions/workflows/qa.yml)
[![Tests](https://github.com/Tatsh/livecheck/actions/workflows/tests.yml/badge.svg)](https://github.com/Tatsh/livecheck/actions/workflows/tests.yml)
[![Coverage Status](https://coveralls.io/repos/github/Tatsh/livecheck/badge.svg?branch=master)](https://coveralls.io/github/Tatsh/livecheck?branch=master)
[![Documentation Status](https://readthedocs.org/projects/livecheck/badge/?version=latest)](https://livecheck.readthedocs.org/?badge=latest)
[![mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![pydocstyle](https://img.shields.io/badge/pydocstyle-enabled-AD4CD3)](http://www.pydocstyle.org/en/stable/)
[![pytest](https://img.shields.io/badge/pytest-zz?logo=Pytest&labelColor=black&color=black)](https://docs.pytest.org/en/stable/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Downloads](https://static.pepy.tech/badge/livecheck/month)](https://pepy.tech/project/livecheck)
[![Stargazers](https://img.shields.io/github/stars/Tatsh/livecheck?logo=github&style=flat)](https://github.com/Tatsh/livecheck/stargazers)

[![@Tatsh](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fpublic.api.bsky.app%2Fxrpc%2Fapp.bsky.actor.getProfile%2F%3Factor%3Ddid%3Aplc%3Auq42idtvuccnmtl57nsucz72%26query%3D%24.followersCount%26style%3Dsocial%26logo%3Dbluesky%26label%3DFollow%2520%40Tatsh&query=%24.followersCount&style=social&logo=bluesky&label=Follow%20%40Tatsh)](https://bsky.app/profile/Tatsh.bsky.social)
[![Mastodon Follow](https://img.shields.io/mastodon/follow/109370961877277568?domain=hostux.social&style=social)](https://hostux.social/@Tatsh)

Tool for overlays to update ebuilds. Inspired by the MacPorts `port` subcommand of the same name
and [nvchecker](https://github.com/lilydjwg/nvchecker).

## Internal workings

The script uses the first url of the ebuild using the SRC_URI variable to search for new versions,
using logic for github, PyPI, PECL or if it is configured in the livecheck.json file within the
same package directory.
Then if you do not find a new version, try to use the repositories within the metadata.xml file
That is why it is important to have the first download url well defined and thus automatically
update the ebuild.

It is recommended to activate the oauth_token of both github and gitlab to avoid
Rate Limiting problems for the REST API.
Use your secret storage to store `github.com` or `gitlab.com` tokens with the `livecheck` user.
See [keyring](https://github.com/jaraco/keyring) to manage tokens.

## Installation

On Gentoo, add my overlay and install:

```shell
eselect overlay enable tatsh-overlay
emerge --sync
emerge livecheck
```

## Command line usage

```plain
Usage: livecheck [OPTIONS] [PACKAGE_NAMES]...

Options:
  -a, --auto-update            Rename and modify ebuilds.
  -d, --debug                  Enable debug logging.
  -D, --development            Include development packages.
  -e, --exclude TEXT           Exclude package(s) from updates.
  -g, --git                    Use git and pkgdev to make changes.
  -H, --hook-dir               Run a hook directory scripts with various parameters.
  -k, --keep-old               Keep old ebuild versions.
  -p, --progress               Enable progress logging.
  -W, --working-dir DIRECTORY  Working directory. Should be a port tree root.
  --help                       Show this message and exit.
```

## Heuristic update detection

This package can do automated lookups based on commonly used hosts. Currently:

- Bitbucket
- Davinci products
- GitHub archives
- GitHub commit hashes
- GitHub releases
- Gitlab releases
- JetBrains products
- PECL
- Packages from Yarnpkg and Npmjs
- Perl CPAN
- PyPI
- Raphnet
- Repology
- RubyGems
- Search in a url directory
- SourceHut releases / commit hashes
- Sourceforge

This works as long as the version system is usable with Portage's version
comparison function. For anything else, see [Package configuration](#package-configuration).

## Package configuration

For packages that will not work with currently heuristic checking, a configuration file named
`livecheck.json` can be placed in the directory alongside the ebuild.

## Hook directory

The hooks directory structure is subdivided into actions, currently `post` and `pre`, within each
action directory there can be several scripts that are executed in order of name.

## Hook arguments

- Root portage directory, e.g. `/var/db/repos/gentoo`.
- Category and package name, e.g. `dev-lang/php`.
- Previous version, e.g. `8.2.32-r2`.
- New version, e.g. `8.2.33`.
- SHA hash of the old version. Optional.
- SHA hash of the new version. Optional.
- Date associated with the hash. Optional.

### Configuration keys

- `branch` - string- The GitHub branch name to use for commits.
- `composer_packages` - boolean - Download composer vendor modules.
- `composer_path` - path - Where is 'composer.json' located (need composer_packages).
- `maven_packages` - boolean - Download Maven dependencies.
- `maven_path` - path - Where is 'pom.xml' located (need maven_packages).
- `development` - bool - Include development packages.
- `gomodule_packages` - boolean - Download go vendor modules.
- `gomodule_path` - path - Where is 'go.mod' located (need gomodule_packages).
- `jetbrains_packages` - boolean - Update internal ID.
- `keep_old` - boolean - Keep old ebuild versions.
- `no_auto_update` - boolean - Do not allow auto-updating of this package.
- `nodejs_packages` - boolean - Download nodejs node_modules.
- `nodejs_path` - path - Where is 'package.json' located (need nodejs_packages).
- `sha_source`- string - Url to get the sha value.
- `stable_version`- string - Regular expression to determine if it is a stable version.
- `sync_version` - string - Category and ebuild with version to sync.
- `transformation_function` - string - Function to use to transform the version string.
  Currently only `dotize` is supported. Others are for internal use.
- `type` - string - Only one `none`, `davinci`, `regex`, `directory`, `commit`,
  `repology` or `checksum`.

Use the pattern to adjust the version using a regular expression

- `pattern_version` - string - The pattern string
- `replace_version` - string - The replace string

Only then `type` is `regex` or `directory`

- `url` - URL of the document to run regular expressions against. Required

Only then `type` is `regex`

- `regex` - string - The regular expression to use. Required

Only then `type` is `repology`

- `package` - string - The package to search in repology. Required

## Development use

### Creating new downloads

There are 2 types of downloads: _file_ and _latest commit_ (currently only Git is supported) and this
is evident from the first download URL of the ebuild itself.

- To download a file, a search is performed by version/tag, and optionally you can include the
  commit of said version, including all the results in a list so that the highest one can be
  selected, according to the search criteria or limit.

- To locate the last commit of an ebuild, we need the SHA of the commit and the date. This is
  necessary to be able to adjust the name of the ebuild using
  the a.b.c_pYYYYMMDD version as a scheme. If a different SHA is detected the version is updated.

### Set up PYTHONPATH

As root, set the environment variable `PYTHONPATH` to include where the `livecheck` module is
located. Use `python -m livecheck` instead of `livecheck` to execute commands.

### With a virtualenv

Run `poetry install --all-extras --with=dev,docs,tests` to set up a virtualenv. You must also add
Portage to this virtualenv manually.

Fully copy `/etc/portage` to the root of your virtualenv. Then you must fix `make.profile`. Also
consider making changes in `repos.conf` if necessary.

Example:

```shell
eval "$(poetry env activate)"
pip install git+https://github.com/gentoo/portage.git
pip install keyrings-alt
cp -R /etc/portage "${VIRTUAL_ENV}/etc/"
ln -sf "$(readlink -f /etc/portage/make.profile)" "${VIRTUAL_ENV}/etc/portage/make.profile"
```
