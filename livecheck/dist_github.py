"""GitHub Releases upload helper for vendor dist archives."""
from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Any, NamedTuple
import logging
import mimetypes

from anyio import Path as AnyioPath
from livecheck.utils.requests import session_init

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ('DistGitHubSettings', 'asset_exists', 'parse_repository', 'upload_dist_archive')

log = logging.getLogger(__name__)

_API_BASE = 'https://api.github.com'


class DistGitHubSettings(NamedTuple):
    """GitHub Releases destination for a vendor dist archive."""

    repository: str
    """Repository in ``owner/repo`` form."""
    release: str
    """Release tag name acting as the fixed asset bucket."""
    force: bool = False
    """Whether to rebuild and re-upload even if the asset already exists."""


def parse_repository(spec: str) -> tuple[str, str]:
    """
    Parse an ``owner/repo`` specifier.

    Parameters
    ----------
    spec : str
        Repository specifier.

    Returns
    -------
    tuple[str, str]
        Owner and repository name.

    Raises
    ------
    ValueError
        If the specifier is not in ``owner/repo`` form.
    """
    parts = spec.strip().split('/')
    if len(parts) != 2 or not parts[0] or not parts[1]:  # ruff:ignore[magic-value-comparison]
        msg = f'Invalid GitHub repository specifier: {spec!r}'
        raise ValueError(msg)
    return parts[0], parts[1]


async def _get_release(owner: str, repo: str, tag: str) -> dict[str, Any] | None:
    session = session_init('github')
    response = await session.get(f'{_API_BASE}/repos/{owner}/{repo}/releases/tags/{tag}',
                                 timeout=30)
    if response.status_code == HTTPStatus.NOT_FOUND:
        return None
    if not response.ok:
        log.error('Failed to look up release `%s` on `%s/%s`: HTTP %d.', tag, owner, repo,
                  response.status_code)
        return None
    return dict(response.json())


async def _create_draft_release(owner: str, repo: str, tag: str) -> dict[str, Any] | None:
    session = session_init('github')
    response = await session.post(f'{_API_BASE}/repos/{owner}/{repo}/releases',
                                  json={
                                      'tag_name': tag,
                                      'name': tag,
                                      'draft': True
                                  },
                                  timeout=30)
    if not response.ok:
        log.error('Failed to create draft release `%s` on `%s/%s`: HTTP %d.', tag, owner, repo,
                  response.status_code)
        return None
    release = dict(response.json())
    log.warning(
        'Created draft GitHub release `%s` on `%s/%s`. '
        'Publish it from the GitHub UI so Portage can fetch the assets.', tag, owner, repo)
    return release


async def _delete_asset(owner: str, repo: str, asset_id: int) -> bool:
    session = session_init('github')
    response = await session.delete(f'{_API_BASE}/repos/{owner}/{repo}/releases/assets/{asset_id}',
                                    timeout=30)
    if not response.ok:
        log.error(
            'Failed to delete existing asset `%d` on `%s/%s`: HTTP %d. '
            '(Are immutable releases enabled?)', asset_id, owner, repo, response.status_code)
        return False
    return True


def _find_asset(release: dict[str, Any], filename: str) -> dict[str, Any] | None:
    for asset in release.get('assets') or ():
        if asset.get('name') == filename:
            return dict(asset)
    return None


async def asset_exists(settings: DistGitHubSettings, filename: str) -> bool:
    """
    Check whether a release asset with ``filename`` is already published.

    Parameters
    ----------
    settings : DistGitHubSettings
        GitHub Releases destination.
    filename : str
        Asset basename to check for.

    Returns
    -------
    bool
        ``True`` if the asset already exists at the target release, otherwise ``False``.
    """
    try:
        owner, repo = parse_repository(settings.repository)
    except ValueError:
        log.exception('Invalid `--dist-github-repository` value.')
        return False
    release = await _get_release(owner, repo, settings.release)
    if release is None:
        return False
    return _find_asset(release, filename) is not None


async def upload_dist_archive(settings: DistGitHubSettings, path: Path) -> bool:
    """
    Upload a vendor dist archive to a GitHub release as an asset.

    If a same-named asset already exists, it is deleted and re-uploaded. If the release does
    not exist, a draft release is created and the user is asked to publish it.

    Parameters
    ----------
    settings : DistGitHubSettings
        GitHub Releases destination.
    path : pathlib.Path
        Absolute path to the file to upload.

    Returns
    -------
    bool
        ``True`` on success, otherwise ``False``.
    """
    try:
        owner, repo = parse_repository(settings.repository)
    except ValueError:
        log.exception('Invalid `--dist-github-repository` value.')
        return False
    if not await AnyioPath(path).is_file():
        log.error('Dist archive `%s` does not exist.', path)
        return False
    release = await _get_release(owner, repo, settings.release)
    if release is None:
        release = await _create_draft_release(owner, repo, settings.release)
        if release is None:
            return False
    existing = _find_asset(release, path.name)
    if existing is not None:
        log.warning('Replacing existing asset `%s` on `%s/%s` release `%s`.', path.name, owner,
                    repo, settings.release)
        if not await _delete_asset(owner, repo, int(existing['id'])):
            return False
    upload_url = str(release.get('upload_url', '')).split('{', 1)[0]
    if not upload_url:
        log.error('Release for `%s/%s` tag `%s` has no upload URL.', owner, repo, settings.release)
        return False
    content_type = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    session = session_init('github')
    data = await _read_bytes(path)
    response = await session.post(f'{upload_url}?name={path.name}',
                                  data=data,
                                  headers={'Content-Type': content_type},
                                  timeout=300)
    if not response.ok:
        log.error('Failed to upload `%s` to `%s/%s` release `%s`: HTTP %d.', path.name, owner, repo,
                  settings.release, response.status_code)
        return False
    log.info('Uploaded `%s` to `%s/%s` release `%s`.', path.name, owner, repo, settings.release)
    return True


async def _read_bytes(path: Path) -> bytes:
    return await AnyioPath(path).read_bytes()
