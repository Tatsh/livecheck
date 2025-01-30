from collections.abc import Sequence
from functools import lru_cache
import logging
import os
import re
from itertools import chain

from portage.versions import catpkgsplit, vercmp
import portage
from ..settings import LivecheckSettings

__all__ = ('P', 'catpkg_catpkgsplit', 'get_first_src_uri', 'get_highest_matches',
           'get_repository_root_if_inside', 'compare_versions', 'sanitize_version', 'get_distdir',
           'fetch_ebuild', 'unpack_ebuild', 'get_last_version')

P = portage.db[portage.root]['porttree'].dbapi
logger = logging.getLogger(__name__)


def mask_version(cp: str, version: str, restrict_version: str | None = 'full') -> str:
    if restrict_version == 'major':
        return cp + ':' + re.sub(r'\.\d+', '', version) + ':'
    if restrict_version == 'minor':
        return cp + ':' + re.sub(r'\.\d+\.\d+', '', version) + ':'
    return cp


def get_highest_matches(names: Sequence[str], repo_root: str,
                        settings: LivecheckSettings) -> list[str]:
    result: dict[str, str] = {}
    for name in names:
        if not (matches := P.xmatch('match-all', name)):
            continue
        for m in matches:
            if repo_root and P.findname2(m)[1] != repo_root:
                continue

            try:
                cp_a, _, _, version_a = catpkg_catpkgsplit(m)
            except ValueError:
                continue

            if '9999' in version_a or not cp_a or not version_a:
                continue

            restrict_version = settings.restrict_version.get(name, 'full')
            cp_mask = mask_version(cp_a, version_a, restrict_version)

            if cp_mask not in result or vercmp(version_a, result[cp_mask]):
                result[cp_mask] = version_a

    return [f"{cp}-{version}" for cp, version in result.items()]


@lru_cache
def catpkg_catpkgsplit(atom: str) -> tuple[str, str, str, str]:
    """
    Split an atom string. This function always returns a four-string tuple.

    Parameters
    ----------
    atom : str
        String to split.

    Returns
    -------
    tuple[str, str, str, str]
        Tuple consisting of four strings.
    """
    result = catpkgsplit(atom)
    if not result or len(result) != 4:
        raise ValueError(f'Invalid atom: {atom}')

    cat, pkg, ebuild_version, revision = result

    if revision and revision != 'r0':
        return f'{cat}/{pkg}', cat, pkg, f'{ebuild_version}-{revision}'

    return f'{cat}/{pkg}', cat, pkg, ebuild_version


def get_first_src_uri(match: str, search_dir: str | None = None) -> str:
    try:
        if (found_uri := next((uri for uri in chain(
                *(x.split() for x in map(str, P.aux_get(match, ['SRC_URI'], mytree=search_dir))))
                               if uri.startswith(('http://', 'https://', 'mirror://', 'ftp://'))),
                              None)):
            return found_uri
    except KeyError:
        pass
    return ''


def get_repository_root_if_inside(directory: str) -> tuple[str, str]:
    # Get Portage configuration
    settings = portage.config(clone=portage.settings)

    # Get repositories from the settings object
    repos = settings['PORTDIR_OVERLAY'].split() + [settings['PORTDIR']]

    # Normalize the directory path to check
    directory = os.path.abspath(directory) + "/"
    selected_repo_root = ''
    selected_repo_name = ''

    # Check each repository
    for repo_root in repos:
        if os.path.isdir(repo_root):
            repo_root = os.path.abspath(repo_root)
            # Check if the directory is inside the repository root
            if directory.startswith(repo_root + "/"):
                # Select the most specific repository (deepest path)
                if selected_repo_root is None or len(repo_root) > len(selected_repo_root):
                    selected_repo_root = repo_root
                    selected_repo_name = os.path.basename(repo_root)

    if '/local/' in directory and '/local/' not in selected_repo_root:
        return '', ''

    # Return the most specific repository root, if found
    return selected_repo_root, selected_repo_name


def is_version_development(version: str) -> bool:
    if re.search(r'(alpha|beta|pre|dev|rc)', version, re.IGNORECASE):
        return True
    return False


def remove_initial_match(a: str, b: str) -> str:
    i = 0
    while i < len(a) and i < len(b) and a[i] == b[i]:
        i += 1
    return a[i:]


def extract_version(s: str, repo: str) -> str:
    # force convert to string to avoid a int object has no attribute lower
    s = str(s).lower().strip()
    # check if first word of s is equal to repo and remove repo from s

    s = remove_initial_match(s, repo.lower())
    s.strip()

    if m := re.search(r'[-_]?([0-9][0-9\._-].*)', s):
        return m.group(1).strip()

    m = re.search(r'(?:^|[^-_])(\d.*)', s)
    return m.group(1).strip() if m else ""


def sanitize_version(ver: str, repo: str = '') -> str:
    ver = extract_version(ver, repo)
    ver = normalize_version(ver)
    return remove_leading_zeros(ver)


def remove_leading_zeros(ver: str) -> str:
    # check if a date format like 2022.12.26 or 24.01.12
    if not re.match(r'\d{4}|\d{2}\.\d{2}\.\d{2}', ver):
        return ver
    if match := re.match(r"(\d+)\.(\d+)(?:\.(\d+))?(.*)", ver):
        a, b, c, suffix = match.groups()
        if c is None:
            return f"{int(a)}.{int(b)}{suffix}"
        return f"{int(a)}.{int(b)}.{int(c)}{suffix}"
    return ver


# Sanitize version to Gentoo Ebuild format
# info: https://dev.gentoo.org/~gokturk/devmanual/pr65/ebuild-writing/file-format/index.html
def normalize_version(ver: str) -> str:
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
        return f"{main}.{suf}"

    if m := re.match(r'^([A-Za-z]+)([0-9]+)?', suf):
        letters, digits = m.groups()
    else:
        suf_clean = re.sub(r'[\s.\-_]+', '', suf)
        m2 = re.match(r'^([A-Za-z]+)([0-9]+)?$', suf_clean)
        if m2:
            letters, digits = m2.groups()
        else:
            letters, digits = '', ''

    if letters in ('test', 'dev'):
        letters = 'beta'
    if letters.startswith('pl') or letters.startswith('patchlevel'):
        letters = 'p'

    allowed = ('pre', 'beta', 'rc', 'p', 'alpha', 'post')

    if letters in allowed:
        if letters in ('post'):
            letters = 'p'
        if digits and digits != '0':
            return f"{main}_{letters}{digits}"
        return f"{main}_{letters}"

    # Single-letter suffix with no digits -> preserve as lowercase
    if len(letters) == 1 and not digits:
        return f"{main}{letters}"
    # No recognized suffix
    if not letters and digits:
        # Just attach the digits directly (e.g. "1.2.3" + "4")
        return f"{main}{digits}"
    # If the version ends with a letter like 1.2.20a (and not recognized),
    # the requirement says "it is preserved" only if it is exactly a single letter.
    # For multi-letter unknown suffix -> discard.
    return main


def compare_versions(old: str, new: str) -> bool:
    return bool(vercmp(old, new, silent=0) == -1)


def get_distdir() -> str:
    settings = portage.config(clone=portage.settings)
    if distdir := settings.get('DISTDIR'):
        return str(distdir)

    return '/var/cache/distfiles'


def fetch_ebuild(ebuild_path: str) -> bool:
    settings = portage.config(clone=portage.settings)

    return bool(portage.doebuild(ebuild_path, 'fetch', settings=settings, tree='porttree') == 0)


def digest_ebuild(ebuild_path: str) -> bool:
    settings = portage.config(clone=portage.settings)

    return bool(portage.doebuild(ebuild_path, 'digest', settings=settings, tree='porttree') == 0)


def unpack_ebuild(ebuild_path: str) -> str:
    settings = portage.config(clone=portage.settings)

    if portage.doebuild(ebuild_path, 'clean', settings=settings, tree='porttree') != 0:
        return ''

    if portage.doebuild(ebuild_path, 'unpack', settings=settings, tree='porttree') != 0:
        return ''

    workdir = settings["WORKDIR"]

    if os.path.exists(workdir) and os.path.isdir(workdir):
        return str(workdir)

    return ''


def get_last_version(results: list[dict[str, str]], repo: str, ebuild: str,
                     settings: LivecheckSettings) -> dict[str, str]:
    logger.debug('Result count: %d', len(results))

    catpkg, _, _, ebuild_version = catpkg_catpkgsplit(ebuild)
    last_version: dict[str, str] = {}

    for result in results:
        tag = version = result["tag"]
        if tf := settings.transformations.get(catpkg, None):
            version = tf(tag)
            logger.debug('Applying transformation %s -> %s', tag, version)
        if catpkg in settings.regex_version:
            regex, replace = settings.regex_version[catpkg]
            version = re.sub(regex, replace, version)
            logger.debug('Applying regex %s -> %s', tag, version)
        else:
            version = sanitize_version(version, repo)
            logger.debug("Convert Tag: %s -> %s", tag, version)
        if not version:
            continue
        # skip version extraneous without dots, example Post120ToMaster
        if ebuild_version.count('.') > 1 and version.count('.') == 0:
            logger.debug("Skip version without dots: %s", version)
            continue
        # Check valid version
        try:
            _, _, _, _ = catpkg_catpkgsplit(ebuild)
        except ValueError:
            logger.debug("Skip non-version tag: %s", version)
            continue
        if not version.startswith(settings.restrict_version_process):
            continue
        if accept_version(ebuild_version, version, catpkg, settings):
            last = last_version.get('version', '')
            if not last or compare_versions(last, version):
                last_version = result.copy()
                last_version['version'] = version

    if not last_version:
        logger.debug("No new update for %s.", ebuild)

    return last_version


def accept_version(ebuild_version: str, version: str, catpkg: str,
                   settings: LivecheckSettings) -> bool:
    stable_version = settings.stable_version.get(catpkg, '')
    if is_version_development(ebuild_version) or settings.is_devel(catpkg) or (
            stable_version and re.match(stable_version, version)):
        return True

    if is_version_development(version) or (stable_version
                                           and not re.match(stable_version, version)):
        return False

    return True
