# livecheck

[![QA](https://github.com/Tatsh/livecheck/actions/workflows/qa.yml/badge.svg)](https://github.com/Tatsh/livecheck/actions/workflows/qa.yml)
[![Tests](https://github.com/Tatsh/livecheck/actions/workflows/tests.yml/badge.svg)](https://github.com/Tatsh/livecheck/actions/workflows/tests.yml)
[![Coverage Status](https://coveralls.io/repos/github/Tatsh/livecheck/badge.svg?branch=master)](https://coveralls.io/github/Tatsh/livecheck?branch=master)
[![Documentation Status](https://readthedocs.org/projects/livecheck/badge/?version=latest)](https://livecheck.readthedocs.io/en/latest/?badge=latest)
![PyPI - Version](https://img.shields.io/pypi/v/portage-livecheck)
![GitHub tag (with filter)](https://img.shields.io/github/v/tag/Tatsh/livecheck)
![GitHub](https://img.shields.io/github/license/Tatsh/livecheck)
![GitHub commits since latest release (by SemVer including pre-releases)](https://img.shields.io/github/commits-since/Tatsh/livecheck/v0.0.9/master)

Tool for overlays to update ebuilds. Inspired by the MacPorts `port` subcommand of the same name.

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
  -e, --exclude TEXT           Exclude package(s) from updates.
  -W, --working-dir DIRECTORY  Working directory. Should be a port tree root.
  --help                       Show this message and exit.
```

## Heuristic update detection

This package can do automated lookups based on commonly used hosts. Currently:

- GitHub archives
- GitHub commit hashes
- GitHub releases
- JetBrains products
- PyPI

This works as long as the version system is usable with Portage's version
comparison function. For anything else, see [Package configuration](#package-configuration).

## Package configuration

For packages that will not work with currently heuristic checking, a configuration file named
`livecheck.json` can be placed in the directory alongside the ebuild.

### Configuration keys

- `type` - `none`, `regex`, or `checksum`
- `branch` - The GitHub branch name to use for commits
- `no_auto_update` - boolean - Do not allow auto-updating of this package
- `regex` - The regular expression to use
- `transformation_function` - string - Function to use to transform the version string. Currently
  only `dotize` is supported. Others are for internal use.
- `url` - URL of the document to run regular expressions against
- `use_vercmp` - boolean - if `vercmp` from Portage should be used. Default: `true`.

## Development use

Run `poetry install --with=dev --with=docs --with=tests` to set up a virtualenv.

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
