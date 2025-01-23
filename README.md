# livecheck

[![QA](https://github.com/Tatsh/livecheck/actions/workflows/qa.yml/badge.svg)](https://github.com/Tatsh/livecheck/actions/workflows/qa.yml)
[![Tests](https://github.com/Tatsh/livecheck/actions/workflows/tests.yml/badge.svg)](https://github.com/Tatsh/livecheck/actions/workflows/tests.yml)
[![Coverage Status](https://coveralls.io/repos/github/Tatsh/livecheck/badge.svg?branch=master)](https://coveralls.io/github/Tatsh/livecheck?branch=master)
[![Documentation Status](https://readthedocs.org/projects/livecheck/badge/?version=latest)](https://livecheck.readthedocs.io/en/latest/?badge=latest)
[![PyPI - Version](https://img.shields.io/pypi/v/livecheck)](https://pypi.org/project/livecheck/)
![GitHub tag (with filter)](https://img.shields.io/github/v/tag/Tatsh/livecheck)
![GitHub](https://img.shields.io/github/license/Tatsh/livecheck)
![GitHub commits since latest release (by SemVer including pre-releases)](https://img.shields.io/github/commits-since/Tatsh/livecheck/v0.0.13/master)

Tool for overlays to update ebuilds. Inspired by the MacPorts `port` subcommand of the same name
or [nvchecker](https://github.com/lilydjwg/nvchecker).

## Internal workings

The script uses the first url of the ebuild using the SRC_URI variable to search for new versions,
using logic for github, PyPI, PECL or if it is configured in the livecheck.json file within the
same package directory.
Then if you do not find a new version, try to use the repositories within the metadata.xml file
That is why it is important to have the first download url well defined and thus automatically
update the ebuild.

It is recommended to activate the oauth_token of both github and gitlab to avoid
Rate Limiting problems for the REST API.
You must create the file ~/.config/gh/hosts.yml and store the oauth_token.

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
- GitHub archives
- GitHub commit hashes
- GitHub releases
- Gitlab repositories
- JetBrains products
- PyPI
- Sourceforge
- PECL
- RubyGems
- Perl CPAN

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
- `composer_packages` - boolean - Download composer vendor modules
- `composer_path` - path - Where is 'composer.json' located (need composer_packages)
- `development` - bool - Include development packages.
- `keep_old` - boolean - Keep old ebuild versions.
- `no_auto_update` - boolean - Do not allow auto-updating of this package.
- `semver` - bool - When set to `false`, do not allow detection of semantic versioning.
- `transformation_function` - string - Function to use to transform the version string. Currently
  only `dotize` is supported. Others are for internal use.
- `type` - `none`, `regex`, or `checksum`.
- `gomodule_packages` - boolean - Download go vendor modules
- `gomodule_path` - path - Where is 'go.mod' located (need gomodule_packages)
- `jetbrains_packages` - boolean - Update internal ID.
- `nodejs_packages` - boolean - Download nodejs node_modules
- `nodejs_path` - path - Where is 'package.json' located (need nodejs_packages)

Use the pattern to adjust the version using a regular expression

- `pattern_version` - string - The pattern string
- `replace_version` - string - The replace string

Only then `type` is `regex`

- `url` - URL of the document to run regular expressions against. Required
- `regex` - string - The regular expression to use. Required
- `use_vercmp` - boolean - if `vercmp` from Portage should be used. Default: `true`.
- `version` - string - Version of package. Default: `None`.

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

Run `poetry install --all-extras --with=dev,docs,tests` to set up a virtualenv.

Fully copy `/etc/portage` to the root of your virtualenv. Then you must fix `make.profile`. Also
consider making changes in `repos.conf` if necessary.

Example:

```shell
poetry shell
cd "${VIRTUAL_ENV}/etc"
cp -R /etc/portage .
cd portage
ln -sf "$(readlink -f /etc/portage/make.profile)" make.profile
```
