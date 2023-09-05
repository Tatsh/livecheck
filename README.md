# livecheck

Tool for overlays to update ebuilds.

## Installation

```shell
pip install portage-livecheck
```

## Command line usage

```shell
livecheck
```

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
