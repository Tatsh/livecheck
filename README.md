# livecheck

Tool for overlays to update ebuilds.

## Installation

```shell
pip install livecheck
```

## Command line usage

```shell
livecheck
```

## Development use

Fully copy `/etc/portage` to the root of your virtualenv. Then you must fix `make.profile`. Also
consider making changes in `repos.conf` if necessary.

Example:

```shell
cd "${VIRTUAL_ENV}/etc"
cp -R /etc/portage .
cd portage
ln -sf "$(readlink -f /etc/portage/make.profile)" make.profile
```
