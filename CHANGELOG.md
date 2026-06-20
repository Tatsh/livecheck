<!-- markdownlint-configure-file {"MD024": { "siblings_only": true } } -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [unreleased]

### Added

- Add support for extracting versions from changelog files.

### Fixed

- Continuing after an error or an update.
- Ignore date-only changelog headings (for example `## 2024-01-31`) when extracting versions, so
  they are no longer mistaken for releases on normal semantic-versioning packages.
- Verified that a candidate resolved by `get_github_branch_for_commit` is a real branch (via the
  GitHub branches API) before writing it to `EGIT_BRANCH`. The compare API also resolves tags, so a
  version that exists only as a tag (for example `dev-php/composer` `2.10.1`) was previously written
  as a branch, causing `git-r3` to fail because the tag ref has no matching `refs/heads/` entry. The
  existing branch (such as `main`) is now preserved when no version-derived branch exists.

## [0.2.4] - 2026-05-31

### Added

- Heuristic detection for NuGet packages, recognising
  `https://api.nuget.org/v3-flatcontainer/...`, `https://www.nuget.org/packages/...`, and
  `https://www.nuget.org/api/v2/package/...` URLs via both `parse_url` and `parse_metadata`
  (`<remote-id type="nuget">`). #429
- New `livecheck.json` configuration keys:
  - `dotnet_packages` (boolean) - opt-in to build a NuGet `packages/` vendor archive named
    `<pkg>-<ver>-nuget.tar.xz`.
  - `dist_github_repository` (string) - per-package override of `--dist-github-repository`.
  - `dist_github_release` (string) - per-package override of `--dist-github-release`.
- New CLI flags for uploading regenerated vendor archives (composer, gomodule, maven, nodejs,
  dotnet) as GitHub release assets:
  - `--dist-github-repository owner/repo`
  - `--dist-github-release tag`
  - `--dist-force-upload`

  When both the repository and release are configured (via CLI or per-package), every regenerated
  vendor archive is uploaded as a release asset. If the release does not exist, livecheck creates
  a draft release and logs a warning. If a same-named asset already exists, livecheck skips the
  rebuild unless `--dist-force-upload` is passed, in which case the existing asset is deleted and
  replaced.

- README section 'Uploading vendor dist archives to GitHub releases' documenting the new flags
  and config keys, with a callout advising users to keep GitHub immutable releases disabled.

### Changed

- Expanded `games-emulation/vita3k` submodule tracking to cover its full set of vendored
  dependencies (including `concurrentqueue`, `dirent`, `glslang`, `googletest`, `libadrenotools`,
  `psvpfstools`, and `substitute`) and namespaced the related SHA variable names by parent
  submodule (for example `LIBB64_SHA` → `PSVPFSTOOLS_LIBB64_SHA`) so nested submodules can be
  distinguished.

### Fixed

- Rolled back the renamed ebuild via the existing recovery path when `update_dotnet_ebuild` or
  the archive build raises (for example on a malformed `NUGETS=` block), instead of leaving the
  ebuild in a broken state.
- Resolved the GitHub branch that contains a commit when rewriting an ebuild to a new commit SHA,
  so `EGIT_BRANCH` points at a branch the commit actually belongs to. The lookup is now deferred
  until an ebuild rewrite is about to happen and skipped when the SHA is unchanged, avoiding
  unnecessary GitHub compare-API calls. #476

## [0.2.3] - 2026-05-08

### Fixed

- Honour `restrict_version` while checking a fixed major or minor version, so candidates outside
  that restricted prefix are filtered during package processing. #464
- Restored green `INFO` output and corrected progress logging flag behaviour after the upgrade to
  the latest `bascom` logging stack. #465

## [0.2.2] - 2026-05-02

### Fixed

- Reject candidate tags whose surrounding filename pattern does not match the current ebuild's
  reference, preventing false version updates when an upstream publishes an unrelated package
  (such as `helm-loki-7.0.0` being picked up for `loki-3.7.1`) under the same release feed. #461
- PyPI and directory-listing handlers strip the archive extension from the version reference
  before comparing against candidate filenames, so a release that ships only under a different
  archive format (e.g. switching from `.tar.gz` to `.zip`) is no longer silently skipped. The
  prefix check that filters unrelated upstream packages still applies.

## [0.2.1] - 2026-04-23

### Fixed

- Removed `pad_version_components` which was corrupting version comparisons by padding single-digit
  components with trailing zeros (e.g. `0.9.1` became `0.90.1`), causing downgrades to be reported
  as upgrades.

## [0.2.0] - 2026-04-22

### Added

- Custom handler for `dev-util/ida-free` to check IDA release notes. #423
- Handler for libretro packages to convert slash-based version tags to dots. #423
- Tests for edge cases in golang, ida_free, yarn, and main modules improving coverage to 99%.

### Changed

- Filter tags with long unrecognised suffixes (>10 characters) when they have trailing digits. #423
- Filter `^vcpkg-.*` tags to prevent incorrect version detection for rpcs3. #423
- Improved version padding to handle shorter versions correctly. #427
- Enhanced submodule processing to support nested submodules (3-tuple format). #427
- Better handling of SHA vs COMMIT variable names in ebuilds. #427
- Migrated the HTTP stack from `requests` to `niquests` with async sessions, SQLite-backed caching,
  and a shared concurrency semaphore. The GitHub session honours `retry-after`,
  `x-ratelimit-remaining`/`x-ratelimit-reset`, and 403 rate-limit bodies.
- Ebuild file I/O and portage metadata calls (`aux_get`, `xmatch`, `getFetchMap`) now run through
  async helpers so heuristic checks no longer block the event loop.
- Dropped 403 from the retry status list and capped retries at 3.
- Added debug logging for handler dispatch and progress.
- Added niquests and urllib3_future loggers to `setup_logging`.
- Converted `check_instance` dispatch to a `match` statement.
- Removed the 2+ ebuild filter from `get_highest_matches`.

### Fixed

- Fixed `update_go_ebuild()` to filter out `/go.mod` entries from `EGO_SUM`. #423
- Fixed `update_yarn_ebuild()` to write packages only once (was duplicating for each old line). #423
- Fixed PyPI URL path handling for pythonhosted.org links. #427
- Fixed ebuild manifest recovery when digest operations fail. #427
- Fixed vapoursynth version parsing to ignore test tags like `R71-limited-api-test1`. #423
- Fixed rpcs3 version parsing to ignore vcpkg dependency tags like `vcpkg-v1.0`. #423
- Fixed docstring section ordering in `livecheck/utils/portage.py` to resolve pydocstyle D420
  errors where 'See Also' appeared before 'Parameters' and 'Returns' sections.
- Closed the temporary file descriptor in `EbuildTempFile` explicitly rather than relying on
  garbage collection to release it.
- Fixed a crash when using `-a` (auto-update) caused by `portage.doebuild` calling
  `run_until_complete()` inside an already-running async event loop. Synchronous `digest_ebuild()`
  calls are now wrapped with `asyncio.to_thread()`.

### Removed

- Dropped Flatpak and Snap build pipelines.

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

[unreleased]: https://github.com/Tatsh/livecheck/compare/v0.2.4...HEAD
[0.2.4]: https://github.com/Tatsh/livecheck/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/Tatsh/livecheck/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/Tatsh/livecheck/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/Tatsh/livecheck/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Tatsh/livecheck/compare/v0.1.4...v0.2.0
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
