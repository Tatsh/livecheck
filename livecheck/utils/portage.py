"""Portage utilities."""
from __future__ import annotations

from functools import cache
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlparse
import logging
import re

from portage import exception  # type: ignore[attr-defined]  # ty: ignore[unresolved-import]
from portage.versions import catpkgsplit, vercmp
import portage

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping

    from livecheck.settings_model import LivecheckSettings
    from portage.dbapi import _AuxKey

__all__ = ('P', 'catpkg_catpkgsplit', 'catpkgsplit2', 'compare_versions', 'fetch_ebuild', 'get_aux',
           'get_distdir', 'get_fetch_map', 'get_first_src_uri', 'get_highest_matches',
           'get_last_version', 'get_repository_catpkgs', 'get_repository_root_if_inside',
           'remove_leading_zeros', 'sanitize_version', 'unpack_ebuild')

P = portage.db[portage.root]['porttree'].dbapi
"""Portage tree database API instance.

:meta hide-value:
"""
log = logging.getLogger(__name__)


def mask_version(cp: str, version: str, restrict_version: str | None = 'full') -> str:
    if restrict_version == 'major':
        return cp + ':' + re.sub(r'^(\d+).*', r'\1', version) + ':'
    if restrict_version == 'minor':
        return cp + ':' + re.sub(r'^(\d+\.\d+).*', r'\1', version) + ':'
    return cp


def _repository_categories() -> frozenset[str]:
    # `portage-stubs` does not declare `portdbapi.settings`.
    return frozenset(cast('Any', P).settings.categories)


def _all_catpkgs(repo_root: Path) -> list[str]:
    # `portage-stubs` does not declare `portdbapi.cp_all()`.
    return [str(catpkg) for catpkg in cast('Any', P).cp_all(trees=[str(repo_root)])]


def _log_unknown_categories(repo_root: Path) -> None:
    categories = _repository_categories()
    for path in sorted(p for p in repo_root.iterdir()
                       if p.is_dir() and not p.name.startswith('.') and p.name not in categories):
        if next(path.glob('*/*.ebuild'), None) is not None:
            log.warning(
                'Skipping directory `%s` because it is not a known category. Add it to '
                '`profiles/categories` for it to be checked.', path.name)


def get_repository_catpkgs(search_dir: Path, repo_root: Path) -> list[str]:
    """
    Get the package names in a repository, limited to the search directory.

    Only directories that Portage recognises as ``category/package`` are returned, so unrelated
    directories in the repository (build artefacts, version control data, and so on) are ignored.

    Parameters
    ----------
    search_dir : Path
        Directory to limit the search to. It may be the repository root, a category directory, or
        a package directory (or anything inside one).
    repo_root : Path
        Repository root path.

    Returns
    -------
    list[str]
        Sorted list of ``category/package`` names.
    """
    repo_root = repo_root.resolve()
    try:
        parts = search_dir.resolve().relative_to(repo_root).parts
    except ValueError:
        log.debug('`%s` is not inside `%s`. Searching the whole repository.', search_dir, repo_root)
        parts = ()
    catpkgs = _all_catpkgs(repo_root)
    if not parts:
        _log_unknown_categories(repo_root)
        return catpkgs
    if len(parts) == 1:
        return [catpkg for catpkg in catpkgs if catpkg.startswith(f'{parts[0]}/')]
    return [catpkg for catpkg in catpkgs if catpkg == f'{parts[0]}/{parts[1]}']


async def get_highest_matches(names: Iterable[str], repo_root: Path | None,
                              settings: LivecheckSettings) -> list[str]:
    """
    Get the highest matching versions for an iterable of package names.

    Parameters
    ----------
    names : Iterable[str]
        Package names to search for.
    repo_root : Path | None
        Repository root path to filter matches, or ``None`` to accept any repository.
    settings : LivecheckSettings
        Livecheck settings instance.

    Returns
    -------
    list[str]
        List of highest matching package version strings.
    """
    log.debug('Searching for %s.', ', '.join(names))
    result: dict[str, str] = {}
    for name in names:
        try:
            matches = await P.async_xmatch('match-all', name)
        except exception.InvalidAtom:
            log.warning('Ignoring `%s` because it is not a valid package name.', name)
            continue
        if not matches:
            log.debug('Found no matches with xmatch("match-all").')
            continue
        for m in matches:
            # Check if the package structure is valid.
            try:
                cp_a, _, _, version = catpkg_catpkgsplit(m)
            except ValueError:
                log.debug('Ignoring invalid package structure.')
                continue

            if repo_root and (actual_root := P.findname2(m)[1]) != str(repo_root):
                log.debug('Ignoring invalid repository root. Expected `%s` and received `%s`.',
                          repo_root, actual_root)
                continue

            if '9999' in version or not cp_a or not version:
                log.debug('Ignoring 9999 version.')
                continue

            restrict_version = settings.restrict_version.get(name, 'full')
            cp_mask = mask_version(cp_a, version, restrict_version)

            if cp_mask not in result or (vercmp(version, result[cp_mask]) or 0) > 0:
                result[cp_mask] = version

    return [f'{cp}-{version}' for cp, version in result.items()]


CATPKGSPLIT_SIZE = 4


@cache
def catpkgsplit2(atom: str) -> tuple[str | None, str, str, str]:
    """
    Split an atom string. This function always returns a four-string tuple.

    Parameters
    ----------
    atom : str
        String to split.

    Returns
    -------
    tuple[str | None, str, str, str]
        Tuple consisting of four strings. If category is not set, the first item is ``None``.

    Raises
    ------
    ValueError
        If :py:func:`catpkgsplit` returns ``None`` or a tuple of size not equal to 4.
    """
    result = catpkgsplit(atom)
    if result is None or len(result) != CATPKGSPLIT_SIZE:
        msg = f'Invalid atom: {atom}'
        raise ValueError(msg)

    return result[0], result[1], result[2], result[3]


@cache
def catpkg_catpkgsplit(atom: str) -> tuple[str, str, str, str]:
    """
    Split an atom string into category, package, and version, but also return CP.

    Parameters
    ----------
    atom : str
        Atom string to split.

    Returns
    -------
    tuple[str, str, str, str]
        Tuple consisting of CP, category, PN, and PV.

    Raises
    ------
    ValueError
        If the atom has no category after splitting.
    """
    cat, pkg, ebuild_version, revision = catpkgsplit2(atom)
    if cat is None:
        msg = f'Atom missing category: {atom}'
        raise ValueError(msg)

    if revision and revision != 'r0':
        return f'{cat}/{pkg}', cat, pkg, f'{ebuild_version}-{revision}'

    return f'{cat}/{pkg}', cat, pkg, ebuild_version


async def get_aux(match: str, keys: Iterable[_AuxKey], mytree: str | None = None) -> list[str]:
    """
    Get ebuild metadata values via :py:func:`P.async_aux_get`.

    Parameters
    ----------
    match : str
        CPV string to look up.
    keys : Iterable[str]
        Ebuild metadata keys to fetch (e.g. ``SRC_URI``, ``HOMEPAGE``).
    mytree : str | None
        Canonical path of the tree in which the ebuild is located, or ``None`` for automatic
        lookup.

    Returns
    -------
    list[str]
        Values for the requested keys, in order.
    """
    return await P.async_aux_get(match, list(keys), mytree=mytree)


async def get_fetch_map(cpv: str) -> dict[str, tuple[str, ...]]:
    """
    Get the ``SRC_URI`` fetch map via :py:func:`P.async_fetch_map`.

    Parameters
    ----------
    cpv : str
        CPV string for an ebuild.

    Returns
    -------
    dict[str, tuple[str, ...]]
        Mapping of each file name to a tuple of alternative URIs.
    """
    return await P.async_fetch_map(cpv)


async def get_first_src_uri(match: str, search_dir: Path | None = None) -> str:
    """
    Get the first source URI for a match string.

    Parameters
    ----------
    match : str
        Match string passed to :py:func:`P.async_aux_get`.
    search_dir : Path | None
        Directory to search in, or ``None`` to use the default.

    Returns
    -------
    str
        The first source URI, or an empty string if none is found.
    """
    try:
        values = await P.async_aux_get(match, ['SRC_URI'], mytree=str(search_dir))
        if (found_uri := next((uri for uri in chain(*(x.split() for x in map(str, values)))
                               if uri.startswith(('http://', 'https://', 'mirror://', 'ftp://'))),
                              None)):
            return found_uri
    except KeyError:
        pass
    return ''


def get_repository_root_if_inside(directory: Path) -> tuple[str, str]:
    """
    Get the repository root if the current working directory is inside a repository.

    Parameters
    ----------
    directory : Path
        Directory path to check.

    Returns
    -------
    tuple[str, str]
        Tuple of repository root path and repository name, or empty strings if not found.
    """
    # Get Portage configuration.
    settings = portage.config(clone=portage.settings)

    # Get repositories from the settings object.
    repos = [*settings['PORTDIR_OVERLAY'].split(), settings['PORTDIR']]

    # Normalise the directory path to check.
    directory = directory.resolve(strict=True)
    directory_str = str(directory) + '/'
    selected_repo_root = ''
    selected_repo_name = ''

    # Check each repository.
    for repo_root in repos:
        if Path(repo_root).is_dir():
            repo_root_ = str(Path(repo_root).resolve(strict=True))
            # Check if the directory is inside the repository root.
            # Select the most specific repository (deepest path).
            if directory_str.startswith(f'{repo_root_}/') and not selected_repo_root:
                selected_repo_root = repo_root_
                selected_repo_name = Path(repo_root_).name

    if '/local/' in directory_str and '/local/' not in str(selected_repo_root):
        return '', ''

    # Return the most specific repository root, if found.
    return selected_repo_root, selected_repo_name


def is_version_development(version: str) -> bool:
    return bool(re.search(r'(alpha|beta|pre|dev|rc)', version, re.IGNORECASE))


def remove_initial_match(a: str, b: str) -> str:
    i = 0
    while i < len(a) and i < len(b) and a[i] == b[i]:
        i += 1
    return a[i:]


_QUALIFIER_ONLY_RE = re.compile(r'^(?:alpha|beta|rc|pre|dev|post|patchlevel|pl)[._\- ]?\d*$')


def extract_version(s: str, repo: str) -> str:
    # Force-convert to string to avoid an int object having no attribute 'lower'.
    s = str(s).lower().strip()

    # Filter out tags with known invalid prefixes.
    invalid_prefixes = ('vcpkg-', 'vcpkg_')
    if any(s.startswith(prefix) for prefix in invalid_prefixes):
        return ''

    # Check if the first word of s is equal to repo and remove repo from s.
    s = remove_initial_match(s, repo.lower())
    s.strip()

    # A pre-release qualifier followed only by its own number (for example `FFMS2beta10`) is a
    # pre-release counter, not a version.
    if _QUALIFIER_ONLY_RE.match(s.strip('.-_ ')):
        return ''

    if m := re.search(r'[-_]?([0-9][0-9\._-].*)', s):
        return m.group(1).strip()

    m = re.search(r'(?:^|[^-_])(\d.*)', s)
    return m.group(1).strip() if m else ''


def sanitize_version(ver: str, repo: str = '') -> str:
    """
    Sanitise a version string.

    Parameters
    ----------
    ver : str
        The version string to sanitise.
    repo : str
        Repository name used to strip matching prefixes.

    Returns
    -------
    str
        The sanitised version string.
    """
    ver = extract_version(ver, repo)
    ver = normalize_version(ver)
    return remove_leading_zeros(ver)


def remove_leading_zeros(ver: str) -> str:
    """
    Remove leading zeros from date-like version components.

    Parameters
    ----------
    ver : str
        The version string to process.

    Returns
    -------
    str
        The version string with leading zeros removed from date-like components.
    """
    if not re.match(r'\d{4}|\d{2}\.\d{2}\.\d{2}', ver):
        return ver
    if match := re.match(r'(\d+)\.(\d+)\.(\d+)(.*)', ver):
        a, b, c, suffix = match.groups()
        return f'{int(a)}.{int(b)}.{int(c)}{suffix}'
    return ver


def normalize_version(ver: str) -> str:
    """
    Normalise a version string to Gentoo ebuild format.

    Parameters
    ----------
    ver : str
        The version string to normalise.

    Returns
    -------
    str
        The normalised version string.

    See Also
    --------
    `Guide <https://devmanual.gentoo.org/ebuild-writing/file-format/ebuild-format.html>`_
    """
    i = 0
    sep = '._-'
    while i < len(ver) and (ver[i].isdigit() or ver[i] in sep):
        if ver[i] in sep:
            sep = ver[i]
        i += 1
    main = re.sub(r'[-_]', '.', ver[:i])
    suf = ver[i:]

    if not (main := main.rstrip('.')):
        return ver

    suf = re.sub(r'[-_\. ]', '', suf)
    if suf.isdigit():
        return f'{main}.{suf}'
    if suf.startswith('build'):
        return f'{main}'

    if m := re.match(r'^([A-Za-z]+)([0-9]+)?', suf):
        letters, digits = m.groups()
    else:
        letters, digits = '', ''

    if digits:
        if letters == 'a':
            letters = 'alpha'
        if letters == 'b':
            letters = 'beta'
    if digits == '0':
        digits = ''

    if letters in {'test', 'dev'}:
        letters = 'beta'
    if letters.startswith(('pl', 'patchlevel')):
        letters = 'p'

    allowed = ('pre', 'beta', 'rc', 'p', 'alpha', 'post')

    if letters in allowed:
        if letters in ('post'):
            letters = 'p'
        if digits:
            return f'{main}_{letters}{digits}'
        return f'{main}_{letters}'

    # Single-letter suffix with no digits -> preserve as lowercase.
    if len(letters) == 1 and not digits:
        return f'{main}{letters}'
    # Discard tags with long unrecognised suffixes (likely test/development tags),
    # e.g. 'limitedapitest1' from 'R71-limited-api-test1'.
    if len(letters) > 10 and digits:  # ruff:ignore[magic-value-comparison]
        return ''
    # An unrecognised suffix such as `api4` in `R55-API4-test3` numbers something other than the
    # release, so its digits are dropped rather than appended to the version.
    # If the version ends with a letter like 1.2.20a (and not recognised),
    # the requirement says 'it is preserved' only if it is exactly a single letter.
    # For multi-letter unknown suffix -> discard.
    return main


def compare_versions(old: str, new: str) -> bool:
    """
    Compare two version strings using Portage's :py:func:`~portage.versions.vercmp`.

    Parameters
    ----------
    old : str
        The old version string.
    new : str
        The new version string.

    Returns
    -------
    bool
        ``True`` if the old version is less than the new version, ``False`` otherwise.
    """
    return bool(vercmp(old, new) == -1)


def get_distdir() -> Path:
    """
    Get the ``DISTDIR`` path from Portage settings.

    Falls back to default ``/var/cache/distfiles``.

    Returns
    -------
    Path
        The distfiles directory path.
    """
    settings = portage.config(clone=portage.settings)
    if distdir := settings.get('DISTDIR'):
        return Path(distdir)
    return Path('/var/cache/distfiles')


def fetch_ebuild(ebuild_path: str) -> bool:
    """
    Perform ``ebuild fetch`` operation.

    Parameters
    ----------
    ebuild_path : str
        Path to the ebuild file.

    Returns
    -------
    bool
        ``True`` if the fetch succeeded.
    """
    settings = portage.config(clone=portage.settings)
    return bool(portage.doebuild(ebuild_path, 'fetch', settings=settings, tree='porttree') == 0)


def digest_ebuild(ebuild_path: str) -> bool:
    settings = portage.config(clone=portage.settings)
    return bool(portage.doebuild(ebuild_path, 'digest', settings=settings, tree='porttree') == 0)


def unpack_ebuild(ebuild_path: str) -> str:
    """
    Perform ``ebuild unpack`` operation and return the ``WORKDIR`` path.

    Parameters
    ----------
    ebuild_path : str
        Path to the ebuild file.

    Returns
    -------
    str
        The ``WORKDIR`` path, or an empty string on failure.
    """
    settings = portage.config(clone=portage.settings)

    if portage.doebuild(ebuild_path, 'clean', settings=settings, tree='porttree') != 0:
        return ''

    if portage.doebuild(ebuild_path, 'unpack', settings=settings, tree='porttree') != 0:
        return ''

    workdir = Path(settings['WORKDIR'])

    if workdir.exists() and workdir.is_dir():
        return str(workdir)

    return ''


def _candidate_version_reference(result: Mapping[str, str], tag: str) -> str:
    if url := result.get('url', ''):
        return Path(urlparse(url).path).name or tag
    return tag


_REFERENCE_PREFIX_RE = re.compile(r'^\D+(?=\d)')


def _candidate_version_from_reference(candidate: str, reference: str,
                                      ebuild_version: str) -> str | None:
    if not reference:
        return ''

    reference_version = re.sub(r'-r\d+$', '', ebuild_version)
    if match := re.search(re.escape(reference_version), reference):
        prefix = reference[:match.start()]
        suffix = reference[match.end():]
    elif (prefix_match :=
          _REFERENCE_PREFIX_RE.match(reference)) and prefix_match.group().strip('vV-_.'):
        # The ebuild version does not appear in the reference, which happens when the ebuild
        # renames it (for example through `MY_PV`). Fall back to the fixed text before the
        # version, but only when it names the project. A bare `v` marker is used by too many
        # tag schemes in the same repository to tell them apart.
        prefix = prefix_match.group()
        suffix = ''
    else:
        return ''

    if not candidate.startswith(prefix) or not candidate.endswith(suffix):
        return None
    end = -len(suffix) if suffix else None
    return sanitize_version(candidate[len(prefix):end])


def get_last_version(results: Collection[Mapping[str, str]],
                     repo: str,
                     ebuild: str,
                     settings: LivecheckSettings,
                     version_reference: str = '') -> dict[str, str]:
    """
    Get the latest version from the results.

    Parameters
    ----------
    results : Collection[Mapping[str, str]]
        Collection of result mappings containing version information.
    repo : str
        Repository name.
    ebuild : str
        Ebuild atom string.
    settings : LivecheckSettings
        Livecheck settings instance.
    version_reference : str
        Current upstream tag or filename whose versioned pattern candidates must match.

    Returns
    -------
    dict[str, str]
        Dictionary with the latest version information, or an empty dictionary if no update found.
    """
    log.debug('Result count: %d', len(results))

    catpkg, _, _, ebuild_version = catpkg_catpkgsplit(ebuild)
    last_version: dict[str, str] = {}

    for result in results:
        tag = version = result['tag']
        if tf := settings.transformations.get(catpkg, None):
            version = tf(tag)
            log.debug('Applying transformation %s -> %s', tag, version)
        if catpkg in settings.regex_version:
            regex, replace = settings.regex_version[catpkg]
            version = re.sub(regex, replace, version)
            log.debug('Applying regex %s -> %s', tag, version)
        else:
            version = sanitize_version(version, repo)
            log.debug('Convert Tag: %s -> %s', tag, version)
        if not version:
            continue
        reference_version = _candidate_version_from_reference(
            _candidate_version_reference(result, tag), version_reference, ebuild_version)
        if reference_version is None:
            log.debug('Skip tag with mismatched version pattern: %s', tag)
            continue
        if reference_version:
            version = reference_version
        # Skip extraneous version without dots, e.g. Post120ToMaster.
        if ebuild_version.count('.') > 1 and version.count('.') == 0:
            log.debug('Skip version without dots: %s', version)
            continue
        # Check valid version.
        try:
            _, _, _, _ = catpkg_catpkgsplit(f'{catpkg}-{version}')
        except ValueError:
            log.debug('Skip non-version tag: %s', version)
            continue
        if not version.startswith(settings.restrict_version_process):
            continue
        if accept_version(ebuild_version, version, catpkg, settings):
            last = last_version.get('version', '')
            if not last or compare_versions(last, version):
                last_version = dict(result).copy()
                last_version['version'] = version

    if not last_version:
        log.debug('No new update for %s.', ebuild)

    return last_version


def accept_version(ebuild_version: str, version: str, catpkg: str,
                   settings: LivecheckSettings) -> bool:
    stable_version = settings.stable_version.get(catpkg, '')
    if is_version_development(ebuild_version) or settings.is_devel(catpkg) or (
            stable_version and re.match(stable_version, version)):
        return True

    return not (is_version_development(version) or
                (stable_version and not re.match(stable_version, version)))
