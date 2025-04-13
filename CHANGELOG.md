<!-- markdownlint-configure-file {"MD024": { "siblings_only": true } } -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.9]

### Added

- Add Python 3.12 to CI
- Add `semver` setting (boolean) to control if automatic detection of semantic versioning is enabled
- Update `EGO_SUM` when updating a `go-module.eclass`-based ebuild
- Update `NUGETS` when updating a `dotnet.eclass`-based ebuild
- Update `YARN_PKGS` array when updating a `yarn.eclass`-based ebuild

### Changed

- Apply transformations to all versions found in the page before doing comparisons
- `special_vercmp`: invalid versions now return `1` (move back)
- Code organisation
- Switch to Ruff from Pylint

### Removed

- Remove Python 3.10 from CI

## [0.0.8]

### Added

- Added handler for `-pl[0-9]` as last number in version, for
  [qpxtool](https://github.com/speed47/qpxtool) releases

## [0.0.7]

### Added

- Added support for packages using `yarn.eclass`. The package URI must be the first `SRC_URI``
(first in`YARN_PKGS`).
- Added gitlab.gentoo.org to `GITLAB_HOSTNAMES`
- Added help text to CLI options.

### Changed

- Bumped dependencies

## [0.0.4] - 2023-09-05

### Fixed

- Added fix for packages that need to use transformation function `dotize`.

## [0.0.3] - 2023-09-05

### Fixed

- Fixed `--exclude` option.

## [0.0.1] - 2023-09-05

### Fixed

- When multiple ebuilds are in the same directory, only the latest one will be considered for updating.
