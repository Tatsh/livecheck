<!-- markdownlint-configure-file {"MD024": { "siblings_only": true } } -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [unreleased]

### Added

- Custom handler for `dev-util/ida-free` to check IDA release notes. #423
- Handler for libretro packages to convert slash-based version tags to dots. #423
- Tests for edge cases in golang, ida_free, yarn, and main modules improving coverage to 99%.

### Changed

- Only update ebuilds when a package has 2 or more non-9999 versions. #423
- Filter tags with long unrecognized suffixes (>10 characters) when they have trailing digits. #423
- Filter `^vcpkg-.*` tags to prevent incorrect version detection for rpcs3. #423
- Improved version padding to handle shorter versions correctly. #427
- Enhanced submodule processing to support nested submodules (3-tuple format). #427
- Better handling of SHA vs COMMIT variable names in ebuilds. #427

### Fixed

- Fixed `update_go_ebuild()` to filter out `/go.mod` entries from `EGO_SUM`. #423
- Fixed `update_yarn_ebuild()` to write packages only once (was duplicating for each old line). #423
- Fixed PyPI URL path handling for pythonhosted.org links. #427
- Fixed ebuild manifest recovery when digest operations fail. #427
- Fixed vapoursynth version parsing to ignore test tags like `R71-limited-api-test1`. #423
- Fixed rpcs3 version parsing to ignore vcpkg dependency tags like `vcpkg-v1.0`. #423

## [0.1.4]

### Added

- Support for headers, query parameters, method, data, and `multiline` (for `regex.MULTILINE`) in
  `livecheck.json`. #249

## [0.1.3]

### Added

- Add configurable Node.js package manager support. #397 Thanks to @inode64.

### Fixed

- Detect compressed files with extension .gh.tar.gz

## [0.1.2]

### Added

- Maven support. #395 Thanks to @inode64.

### Changed

- Ignore releaseNum when normalizing DaVinci versions and return major.minor.
- Do not consider build numbers when normalising versions for Portage. #396 Thanks to @inode64.

### Fixed

- Fix the real SHA from GitHub for a version.

## [0.1.1]

## Changed

- Do not export `main` at the top level.

## [0.1.0]

### Added

- Added back Python 3.10 support.
- Support for URIs from BitBucket, Composer, CPAN, Davinci, PECL, Repology, Rubygems, SourceForge, and
  SourceHut. Thanks to @inode64.

### Changed

- Updated man page to not have unnecessary API docs.

### Fixed

- Always search for settings from the repository root even if inside a directory within.

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

[unreleased]: https://github.com/Tatsh/livecheck/compare/v0.1.4...HEAD
[0.1.4]: https://github.com/Tatsh/livecheck/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/Tatsh/livecheck/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/Tatsh/livecheck/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Tatsh/livecheck/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Tatsh/livecheck/compare/v0.0.13...v0.1.0
[0.0.9]: https://github.com/Tatsh/livecheck/compare/v0.0.8...v0.0.9
[0.0.8]: https://github.com/Tatsh/livecheck/compare/v0.0.7...v0.0.8
[0.0.7]: https://github.com/Tatsh/livecheck/compare/v0.0.6...v0.0.7
[0.0.4]: https://github.com/Tatsh/livecheck/compare/v0.0.3...v0.0.4
[0.0.3]: https://github.com/Tatsh/livecheck/compare/v0.0.2...v0.0.3
[0.0.1]: https://github.com/Tatsh/livecheck/releases/tag/v0.0.1
