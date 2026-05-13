"""Livecheck settings dataclass (kept separate from loading logic to avoid import cycles)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .dist_github import DistGitHubSettings

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

__all__ = ('LivecheckSettings',)


@dataclass
class LivecheckSettings:
    """All settings."""
    branches: dict[str, str] = field(default_factory=dict)
    custom_livechecks: dict[str, tuple[str, str]] = field(default_factory=dict)
    dotnet_packages: dict[str, bool] = field(default_factory=dict)
    """Dictionary of catpkg to whether a NuGet packages vendor archive should be built."""
    dotnet_projects: dict[str, str] = field(default_factory=dict)
    """Dictionary of catpkg to project or solution file (base name only)."""
    dist_github_repositories: dict[str, str] = field(default_factory=dict)
    """Dictionary of catpkg to ``owner/repo`` override for dist archive uploads."""
    dist_github_releases: dict[str, str] = field(default_factory=dict)
    """Dictionary of catpkg to release tag override for dist archive uploads."""
    go_sum_uri: dict[str, str] = field(default_factory=dict)
    """
    Dictionary of catpkg to full URI to ``go.sum`` with ``@PV@`` used for
    where version gets placed.
    """
    type_packages: dict[str, str] = field(default_factory=dict)
    no_auto_update: set[str] = field(default_factory=set)
    """Disable auto-detection of semantic versioning."""
    sha_sources: dict[str, str] = field(default_factory=dict)
    transformations: Mapping[str, Callable[[str], str]] = field(default_factory=dict)
    yarn_base_packages: dict[str, str] = field(default_factory=dict)
    yarn_packages: dict[str, set[str]] = field(default_factory=dict)
    jetbrains_packages: dict[str, bool] = field(default_factory=dict)
    keep_old: dict[str, bool] = field(default_factory=dict)
    gomodule_packages: dict[str, bool] = field(default_factory=dict)
    gomodule_path: dict[str, str] = field(default_factory=dict)
    nodejs_packages: dict[str, bool] = field(default_factory=dict)
    nodejs_path: dict[str, str] = field(default_factory=dict)
    nodejs_package_managers: dict[str, str] = field(default_factory=dict)
    development: dict[str, bool] = field(default_factory=dict)
    composer_packages: dict[str, bool] = field(default_factory=dict)
    composer_path: dict[str, str] = field(default_factory=dict)
    maven_packages: dict[str, bool] = field(default_factory=dict)
    maven_path: dict[str, str] = field(default_factory=dict)
    regex_version: dict[str, tuple[str, str]] = field(default_factory=dict)
    restrict_version: dict[str, str] = field(default_factory=dict)
    sync_version: dict[str, str] = field(default_factory=dict)
    stable_version: dict[str, str] = field(default_factory=dict)
    request_headers: dict[str, dict[str, str]] = field(default_factory=dict)
    """Dictionary of catpkg to custom HTTP headers."""
    request_params: dict[str, dict[str, str]] = field(default_factory=dict)
    """Dictionary of catpkg to query parameters."""
    request_method: dict[str, str] = field(default_factory=dict)
    """Dictionary of catpkg to HTTP method (GET, POST, etc)."""
    request_data: dict[str, dict[str, str]] = field(default_factory=dict)
    """Dictionary of catpkg to form data for POST requests."""
    regex_multiline: dict[str, bool] = field(default_factory=dict)
    """Dictionary of catpkg to multiline flag for regex."""
    # Settings from command line flag.
    auto_update_flag: bool = False
    debug_flag: bool = False
    development_flag: bool = False
    git_flag: bool = False
    keep_old_flag: bool = False
    progress_flag: bool = False
    default_package_manager: str = 'npm'
    dist_github_repository: str = ''
    """Global ``owner/repo`` for dist archive uploads (from ``--dist-github-repository``)."""
    dist_github_release: str = ''
    """Global release tag for dist archive uploads (from ``--dist-github-release``)."""
    dist_force_upload_flag: bool = False
    """Force re-upload even when an asset with the same name already exists."""
    # Internal settings.
    restrict_version_process: str = ''

    def is_devel(self, catpkg: str) -> bool:
        """
        Check if the package is a development version.

        Parameters
        ----------
        catpkg : str
            Category-package atom.

        Returns
        -------
        bool
            Whether the package is treated as a development version.
        """
        return self.development.get(catpkg, self.development_flag)

    def dist_settings_for(self, catpkg: str) -> DistGitHubSettings | None:
        """
        Resolve GitHub dist upload settings for a package.

        Parameters
        ----------
        catpkg : str
            Category-package atom.

        Returns
        -------
        DistGitHubSettings | None
            Effective dist settings (per-package overriding global), or ``None`` if neither is
            fully configured.
        """
        repo = self.dist_github_repositories.get(catpkg, self.dist_github_repository)
        release = self.dist_github_releases.get(catpkg, self.dist_github_release)
        if not repo or not release:
            return None
        return DistGitHubSettings(repository=repo,
                                  release=release,
                                  force=self.dist_force_upload_flag)

    def get_package_manager(self, catpkg: str) -> str:
        """
        Return the package manager configured for a package.

        Parameters
        ----------
        catpkg : str
            Category-package atom.

        Returns
        -------
        str
            Package manager command name for Node.js fetches.
        """
        return self.nodejs_package_managers.get(catpkg, self.default_package_manager)
