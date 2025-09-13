"""Main command."""
from __future__ import annotations

from os import chdir
from pathlib import Path
from re import Match
from typing import TYPE_CHECKING
from urllib.parse import urlparse
import logging
import os
import re
import subprocess as sp

from bascom import setup_logging
from defusedxml import ElementTree as ET  # noqa: N817
import click

from .constants import (
    SUBMODULES,
    TAG_NAME_FUNCTIONS,
)
from .settings import (
    TYPE_CHECKSUM,
    TYPE_COMMIT,
    TYPE_DAVINCI,
    TYPE_DIRECTORY,
    TYPE_METADATA,
    TYPE_NONE,
    TYPE_REGEX,
    TYPE_REPOLOGY,
    LivecheckSettings,
    gather_settings,
)
from .special.bitbucket import (
    BITBUCKET_METADATA,
    get_latest_bitbucket,
    get_latest_bitbucket_metadata,
    is_bitbucket,
)
from .special.checksum import get_latest_checksum_package, update_checksum_metadata
from .special.composer import (
    check_composer_requirements,
    remove_composer_url,
    update_composer_ebuild,
)
from .special.davinci import get_latest_davinci_package
from .special.directory import get_latest_directory_package
from .special.dotnet import check_dotnet_requirements, update_dotnet_ebuild
from .special.gist import get_latest_gist_package, is_gist
from .special.github import (
    GITHUB_METADATA,
    get_latest_github,
    get_latest_github_metadata,
    is_github,
)
from .special.gitlab import (
    GITLAB_METADATA,
    get_latest_gitlab,
    get_latest_gitlab_metadata,
    is_gitlab,
)
from .special.golang import update_go_ebuild
from .special.gomodule import (
    check_gomodule_requirements,
    remove_gomodule_url,
    update_gomodule_ebuild,
)
from .special.jetbrains import get_latest_jetbrains_package, is_jetbrains, update_jetbrains_ebuild
from .special.maven import (
    check_maven_requirements,
    remove_maven_url,
    update_maven_ebuild,
)
from .special.metacpan import (
    METACPAN_METADATA,
    get_latest_metacpan_metadata,
    get_latest_metacpan_package,
    is_metacpan,
)
from .special.nodejs import check_nodejs_requirements, remove_nodejs_url, update_nodejs_ebuild
from .special.package import get_latest_package, is_package
from .special.pecl import PECL_METADATA, get_latest_pecl_metadata, get_latest_pecl_package, is_pecl
from .special.pypi import PYPI_METADATA, get_latest_pypi_metadata, get_latest_pypi_package, is_pypi
from .special.regex import get_latest_regex_package
from .special.repology import get_latest_repology
from .special.rubygems import (
    RUBYGEMS_METADATA,
    get_latest_rubygems_metadata,
    get_latest_rubygems_package,
    is_rubygems,
)
from .special.sourceforge import (
    SOURCEFORGE_METADATA,
    get_latest_sourceforge_metadata,
    get_latest_sourceforge_package,
    is_sourceforge,
)
from .special.sourcehut import (
    SOURCEHUT_METADATA,
    get_latest_sourcehut,
    get_latest_sourcehut_metadata,
    is_sourcehut,
)
from .special.yarn import check_yarn_requirements, update_yarn_ebuild
from .utils import check_program, extract_sha, get_content, is_sha
from .utils.portage import (
    P,
    catpkg_catpkgsplit,
    catpkgsplit2,
    compare_versions,
    digest_ebuild,
    get_first_src_uri,
    get_highest_matches,
    get_repository_root_if_inside,
    remove_leading_zeros,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from .typing import PropTuple

log = logging.getLogger(__name__)

__all__ = ('main',)


def process_submodules(pkg_name: str, ref: str, contents: str, repo_uri: str) -> str:
    """Process submodules in the ebuild contents."""
    if pkg_name not in SUBMODULES:
        return contents
    offset_a, offset_b = ((1, 3) if 'api.github.com/repos/' in repo_uri else (0, 2))
    repo_root = '/'.join([x for x in urlparse(repo_uri).path.split('/') if x][offset_a:offset_b])
    ebuild_lines = contents.splitlines(keepends=True)
    for item in SUBMODULES[pkg_name]:
        name = item
        if isinstance(item, tuple):
            grep_for = f'{item[1]}="'
            name = item[0]
        else:
            grep_for = f'{Path(item).name.upper().replace("-", "_")}_SHA="'
        r = get_content(f'https://api.github.com/repos/{repo_root}/contents/{name}'
                        f'?ref={ref}')
        if not r.ok:
            continue
        remote_sha = r.json()['sha']
        for line in ebuild_lines:
            if (line.startswith(grep_for)
                    and (local_sha := line.split('=')[1].replace('"', '').strip()) != remote_sha):
                contents = contents.replace(local_sha, remote_sha)
    return contents


def log_unhandled_pkg(ebuild: str, src_uri: str) -> None:  # pragma: no cover
    """Log unhandled package name and ``SRC_URI`` at :py:ref:`logging.DEBUG` level."""
    log.debug('Unhandled: %s, SRC_URI: %s', ebuild, src_uri)


def parse_url(src_uri: str, ebuild: str, settings: LivecheckSettings, *,
              force_sha: bool) -> tuple[str, str, str, str]:
    """Parse a URL and return the last version, top hash, hash date, and URL."""
    parsed_uri = urlparse(src_uri)
    last_version = top_hash = hash_date = ''
    url = src_uri

    if not parsed_uri.hostname:
        return last_version, top_hash, hash_date, url

    log.debug('Parsed URI: %s', parsed_uri)
    if is_gist(src_uri):
        top_hash, hash_date = get_latest_gist_package(src_uri)
    elif is_github(src_uri):
        last_version, top_hash, hash_date = get_latest_github(src_uri,
                                                              ebuild,
                                                              settings,
                                                              force_sha=force_sha)
    elif is_sourcehut(src_uri):
        last_version, top_hash, hash_date = get_latest_sourcehut(src_uri,
                                                                 ebuild,
                                                                 settings,
                                                                 force_sha=force_sha)
    elif is_pypi(src_uri):
        last_version, url = get_latest_pypi_package(src_uri, ebuild, settings)
    elif is_jetbrains(src_uri):
        last_version = get_latest_jetbrains_package(ebuild, settings)
    elif is_gitlab(src_uri):
        last_version, top_hash, hash_date = get_latest_gitlab(src_uri,
                                                              ebuild,
                                                              settings,
                                                              force_sha=force_sha)
    elif is_package(src_uri):
        last_version = get_latest_package(src_uri, ebuild, settings)
    elif is_pecl(src_uri):
        last_version = get_latest_pecl_package(ebuild, settings)
    elif is_metacpan(src_uri):
        last_version = get_latest_metacpan_package(src_uri, ebuild, settings)
    elif is_rubygems(src_uri):
        last_version = get_latest_rubygems_package(ebuild, settings)
    elif is_sourceforge(src_uri):
        last_version = get_latest_sourceforge_package(src_uri, ebuild, settings)
    elif is_bitbucket(src_uri):
        last_version, top_hash, hash_date = get_latest_bitbucket(src_uri,
                                                                 ebuild,
                                                                 settings,
                                                                 force_sha=force_sha)
    else:
        log_unhandled_pkg(ebuild, src_uri)

    return last_version, top_hash, hash_date, url


def parse_metadata(repo_root: str, ebuild: str,
                   settings: LivecheckSettings) -> tuple[str, str, str, str]:
    """Parse ``metadata.xml`` for upstream information."""
    catpkg, _, _, _ = catpkg_catpkgsplit(ebuild)
    metadata_file = Path(repo_root) / catpkg / 'metadata.xml'
    if not metadata_file.exists():
        return '', '', '', ''
    try:
        root = ET.parse(metadata_file).getroot()
    except ET.ParseError:
        log.exception('Error parsing %s.', metadata_file)
        return '', '', '', ''
    assert root is not None
    for upstream in root.findall('upstream'):
        for subelem in upstream:
            last_version = top_hash = hash_date = url = ''
            if subelem.tag == 'remote-id':
                if not (remote := subelem.text.strip() if subelem.text else ''):
                    continue
                type_ = subelem.attrib['type']
                if GITHUB_METADATA in type_:
                    last_version, top_hash = get_latest_github_metadata(remote, ebuild, settings)
                if BITBUCKET_METADATA in type_:
                    last_version, top_hash = get_latest_bitbucket_metadata(remote, ebuild, settings)
                if GITLAB_METADATA in type_:
                    last_version, top_hash = get_latest_gitlab_metadata(
                        remote, type_, ebuild, settings)
                if SOURCEHUT_METADATA in type_:
                    last_version = get_latest_sourcehut_metadata(remote, ebuild, settings)
                if METACPAN_METADATA in type_:
                    last_version = get_latest_metacpan_metadata(remote, ebuild, settings)
                if PECL_METADATA in type_:
                    last_version = get_latest_pecl_metadata(remote, ebuild, settings)
                if RUBYGEMS_METADATA in type_:
                    last_version = get_latest_rubygems_metadata(remote, ebuild, settings)
                if SOURCEFORGE_METADATA in type_:
                    last_version = get_latest_sourceforge_metadata(remote, ebuild, settings)
                if PYPI_METADATA in type_:
                    last_version, url = get_latest_pypi_metadata(remote, ebuild, settings)
                if last_version or top_hash:
                    return last_version, top_hash, hash_date, url
    return '', '', '', ''


def extract_restrict_version(cp: str) -> tuple[str, str]:
    """Extract the restrict version from a package string."""
    if match := re.match(r'(.*?):(.*):-(.*)', cp):
        package, slot, version = match.groups()
        cleaned_string = f'{package}-{version}'
        return cleaned_string, slot
    return cp, ''


def get_props(  # noqa: C901, PLR0912, PLR0914
        search_dir: Path,
        repo_root: Path,
        settings: LivecheckSettings,
        names: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None) -> Iterator[PropTuple]:
    """
    Get properties for packages in the search directory.

    Yields
    ------
    PropTuple

    Raises
    ------
    click.Abort
    """
    exclude = exclude or []
    if not names:
        names = [
            f'{path.parent.parent.name}/{path.parent.name}'
            for path in search_dir.glob('**/*.ebuild')
        ]
    matches_list = sorted(get_highest_matches(names, repo_root, settings))
    log.info('Found %d ebuild%s.', len(matches_list), 's' if len(matches_list) != 1 else '')
    if not matches_list:
        log.error('No matches!')
        raise click.Abort
    for _match in matches_list:
        match, settings.restrict_version_process = extract_restrict_version(_match)
        catpkg, cat, pkg, ebuild_version = catpkg_catpkgsplit(match)
        if catpkg in exclude or pkg in exclude:
            log.debug('Ignoring %s.', catpkg)
            continue
        src_uri = get_first_src_uri(match, repo_root)
        if cat.startswith(('acct-', 'virtual')) or settings.type_packages.get(catpkg) == TYPE_NONE:
            log.debug('Ignoring %s.', catpkg)
            continue
        log.info('Processing: %s | Version: %s', catpkg, ebuild_version)
        last_version = hash_date = top_hash = url = ''
        ebuild = Path(repo_root) / catpkg / f'{pkg}-{ebuild_version}.ebuild'
        egit, branch = get_egit_repo(ebuild)
        if egit:
            old_sha = get_old_sha(ebuild, '')
            egit = egit + '/commit/' + old_sha
        if branch:
            settings.branches[catpkg] = branch
        if catpkg in settings.sync_version:
            matches_sync = get_highest_matches([settings.sync_version[catpkg]], None, settings)
            if not matches_sync:
                log.error('No matches for %s.', catpkg)
                continue
            _, _, _, last_version = catpkg_catpkgsplit(matches_sync[0])
            # remove -r* from version
            last_version = re.sub(r'-r\d+$', '', last_version)
        if settings.type_packages.get(catpkg) == TYPE_DAVINCI:
            last_version = get_latest_davinci_package(pkg)
        elif settings.type_packages.get(catpkg) == TYPE_METADATA:
            last_version, top_hash, hash_date, url = parse_metadata(str(repo_root), match, settings)
        elif settings.type_packages.get(catpkg) == TYPE_DIRECTORY:
            url, _ = settings.custom_livechecks[catpkg]
            last_version, url = get_latest_directory_package(url, match, settings)
        elif settings.type_packages.get(catpkg) == TYPE_REPOLOGY:
            package, _ = settings.custom_livechecks[catpkg]
            last_version = get_latest_repology(match, settings, package)
        elif settings.type_packages.get(catpkg) == TYPE_REGEX:
            url, regex = settings.custom_livechecks[catpkg]
            last_version, hash_date, url = get_latest_regex_package(match, url, regex, settings)
        elif settings.type_packages.get(catpkg) == TYPE_CHECKSUM:
            last_version, hash_date, url = get_latest_checksum_package(
                src_uri, match, str(repo_root))
        elif settings.type_packages.get(catpkg) == TYPE_COMMIT:
            last_version, top_hash, hash_date, url = parse_url(egit,
                                                               match,
                                                               settings,
                                                               force_sha=True)
        else:
            if egit:
                last_version, top_hash, hash_date, url = parse_url(egit,
                                                                   match,
                                                                   settings,
                                                                   force_sha=True)
            if not last_version and not top_hash:
                last_version, top_hash, hash_date, url = parse_url(src_uri,
                                                                   match,
                                                                   settings,
                                                                   force_sha=False)
            if not last_version and not top_hash:
                last_version, top_hash, hash_date, url = parse_metadata(
                    str(repo_root), match, settings)
            # Try check for homepage
            homes = [
                x
                for x in ' '.join(P.aux_get(match, ['HOMEPAGE'], mytree=str(repo_root))).split(' ')
                if x
            ]
            for home in homes:
                if not last_version and not top_hash:
                    last_version, top_hash, hash_date, url = parse_url(home,
                                                                       match,
                                                                       settings,
                                                                       force_sha=False)
            if not last_version and not top_hash:
                last_version = get_latest_repology(match, settings)
            # Only check directory if no other method was found
            if not last_version and not top_hash:
                last_version, url = get_latest_directory_package(src_uri, match, settings)
                for home in homes:
                    last_version, url = get_latest_directory_package(home, match, settings)
                    if last_version:
                        break

        if last_version or top_hash:
            log.debug('Inserting %s: %s -> %s : %s', catpkg, ebuild_version, last_version, top_hash)
            yield (cat, pkg, ebuild_version, last_version, top_hash, hash_date, url)
        else:
            log.debug('Ignoring %s. Update not available.', catpkg)


def get_old_sha(ebuild: Path, url: str) -> str:
    sha_pattern = re.compile(r'(SHA|COMMIT|EGIT_COMMIT)=["\']?([a-f0-9]{40})')

    with Path(ebuild).open(encoding='utf-8') as file:
        for line in file:
            if match := sha_pattern.search(line):
                return match.group(2)

    last_part = urlparse(url).path.rsplit('/', 1)[-1] if '/' in url else url
    return extract_sha(last_part)


def get_egit_repo(ebuild: Path) -> tuple[str, str]:
    egit = branch = ''
    with Path(ebuild).open(encoding='utf-8') as file:
        for line in file:
            if match := re.compile(r'^EGIT_REPO_URI=(["\'])?(.*)\1').search(line):
                egit = match.group(2)
            if match := re.compile(r'^EGIT_BRANCH=(["\'])?(.*)\1').search(line):
                branch = match.group(2)
    return egit, branch


def str_version(version: str, sha: str) -> str:
    return version + f' ({sha})' if sha else version


DATE_LENGTH_8 = 8
DATE_LENGTH_6 = 6


def replace_date_in_ebuild(ebuild: str, new_date: str, cp: str) -> str:
    short_date = new_date[2:]
    pattern = re.compile(r'(\d{4,8})')

    def replace_match(match: Match[str]) -> str:
        matched_text = match.group(0)
        if len(matched_text) == DATE_LENGTH_8 and matched_text.isdigit():
            return new_date
        if len(matched_text) == DATE_LENGTH_6 and matched_text.isdigit():
            return short_date
        return matched_text

    n = pattern.sub(replace_match, ebuild)

    _, _, old_version, _ = catpkgsplit2(f'{cp}-{ebuild}')
    _, _, new_version, _ = catpkgsplit2(f'{cp}-{n}')
    return str(new_version) if old_version != new_version else n


def execute_hooks(hook_dir: Path | None, action: str, search_dir: Path, cp: str,
                  str_old_version: str, str_new_version: str, old_sha: str, new_sha: str,
                  hash_date: str) -> None:
    if not hook_dir:
        return
    hook_path = hook_dir / action
    if not hook_path.is_dir():
        return
    for hook in sorted(hook_path.iterdir()):
        if hook.is_file() and os.access(hook, os.X_OK):
            log.debug('Running hook {hook}')
            result = sp.run([
                hook, search_dir, cp, str_old_version, str_new_version, old_sha, new_sha, hash_date
            ],
                            check=False)
            if result.returncode != 0:
                click.echo(f'Error running hook {hook}.', err=True)
                raise click.Abort


def do_main(  # noqa: C901, PLR0912, PLR0915
        *, cat: str, ebuild_version: str, pkg: str, search_dir: Path, settings: LivecheckSettings,
        last_version: str, top_hash: str, hash_date: str, url: str, hook_dir: Path | None) -> None:
    cp = f'{cat}/{pkg}'
    ebuild = Path(search_dir) / cp / f'{pkg}-{ebuild_version}.ebuild'
    old_sha = ''
    if update_sha_too_source := settings.sha_sources.get(cp, None):
        log.debug('Package also needs a SHA update.')
        _, top_hash, hash_date, _ = parse_url(update_sha_too_source,
                                              f'{cp}-{ebuild_version}',
                                              settings,
                                              force_sha=True)

        # if empty, it means that the source is not supported
        if not top_hash:
            log.warning('Could not get new SHA for %s.', update_sha_too_source)
            return
    if top_hash:
        old_sha = get_old_sha(ebuild, url)
        if len(old_sha) == 7:  # noqa: PLR2004
            top_hash = top_hash[:7]
        log.debug('Get old_sha = %s', old_sha)
    if not last_version:
        last_version = ebuild_version
    if hash_date:
        last_version = replace_date_in_ebuild(last_version, hash_date, cp)
    if last_version == ebuild_version and old_sha != top_hash and old_sha and top_hash:
        _, _, new_version, new_revision = catpkgsplit2(f'{cp}-{last_version}')
        new_revision = 'r' + str(int(new_revision[1:]) + 1)
        log.debug('Incrementing revision to %s.', new_revision)
        last_version = f'{new_version}-{new_revision}'
    log.debug('top_hash = %s', last_version)

    # Remove leading zeros to prevent issues with version comparison
    last_version = remove_leading_zeros(last_version)
    ebuild_version = remove_leading_zeros(ebuild_version)

    log.debug('Comparing current ebuild version %s with live version %s.', ebuild_version,
              last_version)
    if compare_versions(ebuild_version, last_version):
        dn = Path(ebuild).parent
        new_filename = f'{dn}/{pkg}-{last_version}.ebuild'
        _, _, _, new_version = catpkg_catpkgsplit(f'{cp}-{last_version}')
        _, _, _, old_version = catpkg_catpkgsplit(f'{cp}-{ebuild_version}')
        log.debug('Migrating from %s to %s.', ebuild, new_filename)
        no_auto_update_str = ' (no_auto_update)' if cp in settings.no_auto_update else ''
        str_new_version = str_version(new_version, top_hash)
        str_old_version = str_version(old_version, old_sha)
        log.info('%s/%s: %s -> %s%s', cat, pkg, str_old_version, str_new_version,
                 no_auto_update_str)

        if settings.auto_update_flag and cp not in settings.no_auto_update:
            # First check requirements before update
            if ((  # noqa: PLR0916
                    cp in settings.dotnet_projects and not check_dotnet_requirements())
                    or (cp in settings.composer_packages and not check_composer_requirements())
                    or (cp in settings.maven_packages and not check_maven_requirements())
                    or (cp in settings.yarn_base_packages and not check_yarn_requirements())
                    or (cp in settings.nodejs_packages and not check_nodejs_requirements())
                    or (cp in settings.gomodule_packages and not check_gomodule_requirements())):
                log.warning('Update is not possible.')
                return
            old_content = content = Path(ebuild).read_text(encoding='utf-8')
            # Only update the version if it is not a commit
            if top_hash and old_sha:
                content = content.replace(old_sha, top_hash)
            ps_ref = top_hash
            if not is_sha(top_hash) and cp in TAG_NAME_FUNCTIONS:
                ps_ref = TAG_NAME_FUNCTIONS[cp](top_hash)
            content = process_submodules(cp, ps_ref, content, url)
            dn = Path(ebuild).parent
            log.debug('%s -> %s', ebuild, new_filename)
            if settings.keep_old.get(cp, not settings.keep_old_flag):
                try:
                    if settings.git_flag:
                        sp.run(('git', 'mv', str(ebuild), new_filename), check=True)
                    else:
                        ebuild.rename(new_filename)
                except (sp.CalledProcessError, OSError):
                    log.exception('Error moving `%s` to `%s`.', ebuild, new_filename)
                    return

            try:
                Path(new_filename).write_text(content, encoding='utf-8')
            except OSError:
                log.exception('Error writing `%s`.', new_filename)
                return
            execute_hooks(hook_dir, 'pre', search_dir, cp, ebuild_version, last_version, old_sha,
                          top_hash, hash_date)
            # We do not check the digest because it may happen that additional files need to be
            # created that have not yet been generated until the main ebuild is downloaded for
            # the first time and the hooks create those additional files.
            # And you cannot remove the digest generation either, but rather the repositories
            # that do not have thin-Manifests ( metadata/layout.conf -> thin-manifests = true)
            # see: https://devmanual.gentoo.org/general-concepts/manifest/index.html
            digest_ebuild(new_filename)
            fetchlist = P.getFetchMap(f'{cp}-{last_version}')
            # Stores the content so that it can be recovered because it had to be modified
            old_content = content
            # First pass
            # Remove URLs that do not yet exist to be able to correctly generate the digest
            if cp in settings.gomodule_packages:
                content = remove_gomodule_url(content)
            if cp in settings.nodejs_packages:
                content = remove_nodejs_url(content)
            if cp in settings.composer_packages:
                content = remove_composer_url(content)
            if cp in settings.maven_packages:
                content = remove_maven_url(content)
            if old_content != content:
                Path(new_filename).write_text(content, encoding='utf-8')
            if not digest_ebuild(new_filename):
                log.error('Error digesting %s.', new_filename)
                return
            # Second pass
            # Update ebuild or download news file
            if cp in settings.yarn_base_packages:
                update_yarn_ebuild(new_filename, settings.yarn_base_packages[cp], pkg,
                                   settings.yarn_packages.get(cp))
            if settings.type_packages.get(cp) == TYPE_CHECKSUM:
                update_checksum_metadata(f'{cp}-{last_version}', url, str(search_dir))
            if cp in settings.go_sum_uri:
                update_go_ebuild(new_filename, top_hash, settings.go_sum_uri[cp])
            if cp in settings.dotnet_projects:
                update_dotnet_ebuild(new_filename, settings.dotnet_projects[cp])
            if cp in settings.jetbrains_packages:
                update_jetbrains_ebuild(new_filename)
            if cp in settings.maven_packages:
                update_maven_ebuild(new_filename, settings.maven_path[cp], fetchlist)
            if cp in settings.nodejs_packages:
                update_nodejs_ebuild(new_filename, settings.nodejs_path[cp], fetchlist)
            if cp in settings.gomodule_packages:
                update_gomodule_ebuild(new_filename, settings.gomodule_path[cp], fetchlist)
            if cp in settings.composer_packages:
                update_composer_ebuild(new_filename, settings.composer_path[cp], fetchlist)
            # Restore original ebuild content
            if old_content != content:
                Path(new_filename).write_text(old_content, encoding='utf-8')
                if not digest_ebuild(new_filename):
                    log.error('Error digesting %s.', new_filename)
                    return
            if settings.git_flag and sp.run(
                ('ebuild', new_filename, 'digest'), check=False).returncode == 0:
                sp.run(('git', 'add', new_filename, str(Path(search_dir) / cp / 'Manifest')),
                       check=True)
                try:
                    sp.run(('pkgdev', 'commit'), cwd=Path(search_dir) / cp, check=True)
                except sp.CalledProcessError:
                    log.exception('Error committing %s.', new_filename)
            execute_hooks(hook_dir, 'post', search_dir, cp, ebuild_version, last_version, old_sha,
                          top_hash, hash_date)


@click.command(context_settings={'help_option_names': ['-h', '--help']})
@click.option('-a', '--auto-update', is_flag=True, help='Rename and modify ebuilds.')
@click.option('-d', '--debug', is_flag=True, help='Enable debug logging.')
@click.option('-D', '--development', is_flag=True, help='Include development packages.')
@click.option('-e', '--exclude', multiple=True, help='Exclude package(s) from updates.')
@click.option('-g', '--git', is_flag=True, help='Use git and pkgdev to make changes.')
@click.option('-H',
              '--hook-dir',
              default=None,
              help='Run a hook directory scripts with various parameters.',
              type=click.Path(file_okay=False, exists=True, resolve_path=True, path_type=Path))
@click.option('-k', '--keep-old', is_flag=True, help='Keep old ebuild versions.')
@click.option('-p', '--progress', is_flag=True, help='Enable progress logging.')
@click.option('-W',
              '--working-dir',
              default='.',
              help='Working directory. Should be a port tree root.',
              type=click.Path(file_okay=False,
                              exists=True,
                              resolve_path=True,
                              readable=True,
                              path_type=Path))
@click.argument('package_names', nargs=-1)
def main(working_dir: Path,
         exclude: tuple[str, ...] | None = None,
         hook_dir: Path | None = None,
         package_names: tuple[str, ...] | list[str] | None = None,
         *,
         auto_update: bool = False,
         debug: bool = False,
         development: bool = False,
         git: bool = False,
         keep_old: bool = False,
         progress: bool = False) -> None:
    """Update ebuilds to their latest versions."""  # noqa: DOC501
    setup_logging(debug=debug,
                  loggers={'livecheck': {
                      'handlers': ('console',),
                      'propagate': False
                  }})
    chdir(working_dir)
    if exclude:
        log.debug('Excluding %s.', ', '.join(exclude))
    search_dir = working_dir or Path()
    if auto_update and not os.access(search_dir, os.W_OK):
        msg = f'The directory "{working_dir}" must be writable because --auto-update is enabled.'
        raise click.ClickException(msg)
    repo_root, repo_name = get_repository_root_if_inside(search_dir)
    if not repo_root:
        log.error('Not inside a repository configured in repos.conf.')
        raise click.Abort
    if git:
        if not auto_update:
            log.error('Git option requires --auto-update.')
            raise click.Abort
        if not Path(repo_root, '.git').is_dir():
            log.error('Directory %s is not a git repository.', repo_root)
            raise click.Abort
        # Check if .git is a writeable directory
        if not os.access(Path(repo_root, '.git'), os.W_OK):
            log.error('Directory %s/.git is not writable.', repo_root)
            raise click.Abort
        # Check if git is installed
        if not check_program('git', ['--version']):
            log.error('Git is not installed.')
            raise click.Abort
        # Check if pkgdev is installed
        if not check_program('pkgdev', ['--version']):
            log.error('pkgdev is not installed.')
            raise click.Abort
    log.debug('search_dir=%s repo_root=%s repo_name=%s', search_dir, repo_root, repo_name)
    settings = gather_settings(Path(repo_root))

    # update flags in settings
    settings.auto_update_flag = auto_update
    settings.debug_flag = debug
    settings.development_flag = development
    settings.git_flag = git
    settings.keep_old_flag = keep_old
    settings.progress_flag = progress

    package_names = sorted(package_names or [])
    cat = pkg = None
    try:
        for cat, pkg, ebuild_version, last_version, top_hash, hash_date, url in get_props(
                search_dir, Path(repo_root), settings, package_names, exclude):
            do_main(cat=cat,
                    pkg=pkg,
                    last_version=last_version,
                    top_hash=top_hash,
                    hash_date=hash_date,
                    url=url,
                    search_dir=Path(repo_root),
                    settings=settings,
                    ebuild_version=ebuild_version,
                    hook_dir=hook_dir)
    except Exception:
        if cat and pkg:
            log.exception('Exception while checking %s/%s.', cat, pkg)
        raise
