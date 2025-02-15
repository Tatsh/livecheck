"""Main command."""
from collections.abc import Iterator, Sequence
from os import chdir
from pathlib import Path
from re import Match
from typing import TypeVar, cast
from urllib.parse import urlparse
import hashlib
import logging
import os
import re
import subprocess as sp
import sys
import xml.etree.ElementTree as ET

from loguru import logger
import click

from .constants import (
    GIST_HOSTNAMES,
    SUBMODULES,
    TAG_NAME_FUNCTIONS,
)
from .settings import (
    TYPE_CHECKSUM,
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
from .special.composer import (
    check_composer_requirements,
    remove_composer_url,
    update_composer_ebuild,
)
from .special.davinci import get_latest_davinci_package
from .special.directory import get_latest_directory_package
from .special.dotnet import check_dotnet_requirements, update_dotnet_ebuild
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
from .typing import PropTuple
from .utils import check_program, chunks, extract_sha, get_content, is_sha
from .utils.portage import (
    P,
    catpkg_catpkgsplit,
    catpkgsplit2,
    compare_versions,
    digest_ebuild,
    get_first_src_uri,
    get_highest_matches,
    get_repository_root_if_inside,
)

T = TypeVar('T')


def process_submodules(pkg_name: str, ref: str, contents: str, repo_uri: str) -> str:
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
        if (r := get_content(f'https://api.github.com/repos/{repo_root}/contents/{name}'
                             f'?ref={ref}')):
            remote_sha = r.json()['sha']
            for line in ebuild_lines:
                if (line.startswith(grep_for) and
                    (local_sha := line.split('=')[1].replace('"', '').strip()) != remote_sha):
                    contents = contents.replace(local_sha, remote_sha)
    return contents


def log_unhandled_pkg(ebuild: str, src_uri: str) -> None:
    logger.warning(f'Unhandled: {ebuild} SRC_URI: {src_uri}')


def parse_url(repo_root: str, src_uri: str, ebuild: str,
              settings: LivecheckSettings) -> tuple[str, str, str, str]:
    parsed_uri = urlparse(src_uri)
    last_version = top_hash = hash_date = ''
    url = src_uri

    if not parsed_uri.hostname:
        return last_version, top_hash, hash_date, url

    logger.debug(f'Parsed URI: {parsed_uri}')
    if parsed_uri.hostname in GIST_HOSTNAMES:
        home = P.aux_get(ebuild, ['HOMEPAGE'], mytree=repo_root)[0]
        last_version, hash_date, url = get_latest_regex_package(
            ebuild, f'{home}/revisions', r'<relative-time datetime="([0-9-]{10})', '', settings)
    elif is_github(src_uri):
        last_version, top_hash, hash_date = get_latest_github(src_uri, ebuild, settings)
    elif is_sourcehut(src_uri):
        last_version, top_hash, hash_date = get_latest_sourcehut(src_uri, ebuild, settings)
    elif is_pypi(src_uri):
        last_version, url = get_latest_pypi_package(src_uri, ebuild, settings)
    elif is_jetbrains(src_uri):
        last_version = get_latest_jetbrains_package(ebuild, settings)
    elif is_gitlab(src_uri):
        last_version, top_hash, hash_date = get_latest_gitlab(src_uri, ebuild, settings)
    elif is_package(src_uri):
        last_version = get_latest_package(src_uri, ebuild, settings)
    elif is_pecl(src_uri):
        last_version = get_latest_pecl_package(ebuild, settings)
    elif is_metacpan(src_uri):
        last_version = get_latest_metacpan_package(parsed_uri.path, ebuild, settings)
    elif is_rubygems(src_uri):
        last_version = get_latest_rubygems_package(ebuild, settings)
    elif is_sourceforge(src_uri):
        last_version = get_latest_sourceforge_package(src_uri, ebuild, settings)
    elif is_bitbucket(src_uri):
        last_version, top_hash, hash_date = get_latest_bitbucket(parsed_uri.path, ebuild, settings)
    elif not (last_version := get_latest_directory_package(src_uri, ebuild, settings)):
        log_unhandled_pkg(ebuild, src_uri)

    return last_version, top_hash, hash_date, url


def parse_metadata(repo_root: str, ebuild: str,
                   settings: LivecheckSettings) -> tuple[str, str, str, str]:
    catpkg, _, _, _ = catpkg_catpkgsplit(ebuild)

    metadata_file = Path(repo_root) / catpkg / "metadata.xml"
    if not metadata_file.exists():
        return '', '', '', ''
    try:
        root = ET.parse(metadata_file).getroot()
    except ET.ParseError as e:
        logger.error(f'Error parsing {metadata_file}: {e}')
        return '', '', '', ''
    if upstream_list := root.findall("upstream"):
        for upstream in upstream_list:
            for subelem in upstream:
                tag_name = subelem.tag
                last_version = top_hash = hash_date = url = ''
                if tag_name == 'remote-id':
                    if not (remote := subelem.text.strip() if subelem.text else ""):
                        continue
                    _type = subelem.attrib["type"]
                    if GITHUB_METADATA in _type:
                        last_version, top_hash = get_latest_github_metadata(
                            remote, ebuild, settings)
                    if BITBUCKET_METADATA in _type:
                        last_version, top_hash = get_latest_bitbucket_metadata(
                            remote, ebuild, settings)
                    if GITLAB_METADATA in _type:
                        last_version, top_hash = get_latest_gitlab_metadata(
                            remote, _type, ebuild, settings)
                    if SOURCEHUT_METADATA in _type:
                        last_version = get_latest_sourcehut_metadata(remote, ebuild, settings)
                    if METACPAN_METADATA in _type:
                        last_version = get_latest_metacpan_metadata(remote, ebuild, settings)
                    if PECL_METADATA in _type:
                        last_version = get_latest_pecl_metadata(remote, ebuild, settings)
                    if RUBYGEMS_METADATA in _type:
                        last_version = get_latest_rubygems_metadata(remote, ebuild, settings)
                    if SOURCEFORGE_METADATA in _type:
                        last_version = get_latest_sourceforge_metadata(remote, ebuild, settings)
                    if PYPI_METADATA in _type:
                        last_version, url = get_latest_pypi_metadata(remote, ebuild, settings)
                    if last_version or top_hash:
                        return last_version, top_hash, hash_date, url
    return '', '', '', ''


def extract_restrict_version(cp: str) -> tuple[str, str]:
    if match := re.match(r"(.*?):(.*):-(.*)", cp):
        package, slot, version = match.groups()
        cleaned_string = f"{package}-{version}"
        return cleaned_string, slot
    return cp, ''


def get_props(
    search_dir: str,
    repo_root: str,
    settings: LivecheckSettings,
    names: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
) -> Iterator[PropTuple]:
    exclude = exclude or []
    if not names:
        names = [
            f'{path.parent.parent.name}/{path.parent.name}'
            for path in Path(search_dir).glob('**/*.ebuild')
        ]
    matches_list = sorted(get_highest_matches(names, repo_root, settings))
    logger.info(f'Found {len(matches_list)} ebuilds')
    if not matches_list:
        logger.error('No matches!')
        raise click.Abort
    for _match in matches_list:
        match, settings.restrict_version_process = extract_restrict_version(_match)
        catpkg, cat, pkg, ebuild_version = catpkg_catpkgsplit(match)
        if catpkg in exclude or pkg in exclude:
            logger.debug(f'Ignoring {catpkg}')
            continue
        src_uri = get_first_src_uri(match, repo_root)
        if cat.startswith('acct-') or settings.type_packages.get(catpkg) == TYPE_NONE:
            logger.debug(f'Ignoring {catpkg}')
            continue
        if settings.debug_flag or settings.progress_flag:
            logger.info(f'Processing {catpkg} version {ebuild_version}')
        last_version = hash_date = top_hash = url = ''
        ebuild = Path(repo_root) / catpkg / f'{pkg}-{ebuild_version}.ebuild'
        egit, branch = get_egit_repo(ebuild)
        if branch:
            settings.branches[catpkg] = branch
        if catpkg in settings.sync_version:
            matches_sync = get_highest_matches([settings.sync_version[catpkg]], '', settings)
            if not matches_sync:
                logger.error(f'No matches for {catpkg}')
                continue
            _, _, _, last_version = catpkg_catpkgsplit(matches_sync[0])
            # remove -r* from version
            last_version = re.sub(r'-r\d+$', '', last_version)
        if settings.type_packages.get(catpkg) == TYPE_DAVINCI:
            last_version = get_latest_davinci_package(pkg)
        elif settings.type_packages.get(catpkg) == TYPE_METADATA:
            last_version, top_hash, hash_date, url = parse_metadata(repo_root, match, settings)
        elif settings.type_packages.get(catpkg) == TYPE_DIRECTORY:
            url, _, _, _ = settings.custom_livechecks[catpkg]
            last_version = get_latest_directory_package(url, match, settings)
        elif settings.type_packages.get(catpkg) == TYPE_REPOLOGY:
            pkg, _, _, _ = settings.custom_livechecks[catpkg]
            last_version = get_latest_repology(pkg, settings)
        elif settings.type_packages.get(catpkg) == TYPE_REGEX:
            url, regex, _, version = settings.custom_livechecks[catpkg]
            last_version, hash_date, url = get_latest_regex_package(match, url, regex, version,
                                                                    settings)
        elif settings.type_packages.get(catpkg) == TYPE_CHECKSUM:
            manifest_file = Path(repo_root) / catpkg / 'Manifest'
            bn = Path(src_uri).name
            found = False
            try:
                with open(manifest_file, encoding='utf-8') as f:
                    for line in f.readlines():
                        if not line.startswith('DIST '):
                            continue
                        fields_s = ' '.join(line.strip().split(' ')[-4:])
                        rest = line.replace(fields_s, '').strip()
                        filename = rest.replace(f' {rest.strip().split(" ")[-1]}', '')[5:]
                        m = re.match(f'^{pkg}-[0-9\\.]+(?:_(?:alpha|beta|p)[0-9]+)?(tar\\.gz|zip)',
                                     filename)
                        if filename != bn and not m:
                            continue
                        found = True
                        r = get_content(src_uri)
                        if not r or r.content:
                            log_unhandled_pkg(catpkg, src_uri)
                            continue
                        last_version, hash_date, url = get_latest_regex_package(
                            match,
                            dict(cast(Sequence[tuple[str, str]], chunks(fields_s.split(' '),
                                                                        2)))['SHA512'],
                            f'data:{hashlib.sha512(r.content).hexdigest()}', r'^[0-9a-f]+$',
                            settings)
                        break
            except FileNotFoundError:
                pass
            if not found:
                log_unhandled_pkg(catpkg, src_uri)
        else:
            if egit:
                old_sha = get_old_sha(ebuild, '')
                egit = egit + '/commit/' + old_sha
                last_version, top_hash, hash_date, url = parse_url(repo_root, egit, match, settings)
            if not last_version and not top_hash:
                last_version, top_hash, hash_date, url = parse_url(repo_root, src_uri, match,
                                                                   settings)
            if not last_version and not top_hash:
                last_version, top_hash, hash_date, url = parse_metadata(repo_root, match, settings)
            # Try check for homepage
            homes = [
                x for x in ' '.join(P.aux_get(match, ['HOMEPAGE'], mytree=repo_root)).split(' ')
                if x
            ]
            for home in homes:
                if not last_version and not top_hash:
                    last_version, top_hash, hash_date, url = parse_url(
                        repo_root, home, match, settings)
            if not last_version and not top_hash:
                last_version = get_latest_repology(match, settings)
        if last_version or top_hash:
            logger.debug(f'Inserting {catpkg}: {ebuild_version} -> {last_version} : {top_hash}')
            yield (cat, pkg, ebuild_version, last_version, top_hash, hash_date, url)
        else:
            logger.debug(f'Ignoring {catpkg}, update not available')


def get_old_sha(ebuild: Path, url: str) -> str:
    # TODO: Support mix of SHA and COMMIT (example guru/dev-python/tempy/tempy-1.4.0.ebuild)
    sha_pattern = re.compile(r'(SHA|COMMIT|EGIT_COMMIT)=["\']?([a-f0-9]{40})')

    with open(ebuild, encoding='utf-8') as file:
        for line in file:
            if match := sha_pattern.search(line):
                return match.group(2)

    last_part = urlparse(url).path.rsplit('/', 1)[-1] if '/' in url else url
    return extract_sha(last_part)


def get_egit_repo(ebuild: Path) -> tuple[str, str]:
    egit = branch = ''
    with open(ebuild, encoding='utf-8') as file:
        for line in file:
            if match := re.compile(r'^EGIT_REPO_URI=(["\'])?(.*)\1').search(line):
                egit = match.group(2)
            if match := re.compile(r'^EGIT_BRANCH=(["\'])?(.*)\1').search(line):
                branch = match.group(2)
    return egit, branch


def str_version(version: str, sha: str) -> str:
    return version + f' ({sha})' if sha else version


def replace_date_in_ebuild(ebuild: str, new_date: str, cp: str) -> str:
    short_date = new_date[2:]
    pattern = re.compile(r"(\d{4,8})")

    def replace_match(match: Match[str]) -> str:
        matched_text = match.group(0)
        if len(matched_text) == 8 and matched_text.isdigit():
            return new_date
        if len(matched_text) == 6 and matched_text.isdigit():
            return short_date
        return matched_text

    n = pattern.sub(replace_match, ebuild)

    _, _, _, old_version = catpkg_catpkgsplit(f'{cp}-{ebuild}')
    _, _, _, new_version = catpkg_catpkgsplit(f'{cp}-{n}')
    return str(new_version) if old_version != new_version else n


def execute_hooks(hook_dir: str | None, action: str, search_dir: str, cp: str, str_old_version: str,
                  str_new_version: str, old_sha: str, new_sha: str, hash_date: str) -> None:
    if not hook_dir:
        return
    hook_path = Path(hook_dir + '/' + action)
    if not hook_path.is_dir():
        return
    for hook in sorted(hook_path.iterdir()):
        if hook.is_file() and os.access(hook, os.X_OK):
            logger.debug(f'Running hook {hook}')
            result = sp.run([
                hook, search_dir, cp, str_old_version, str_new_version, old_sha, new_sha, hash_date
            ],
                            check=False)
            if result.returncode != 0:
                click.echo(f'Error running hook {hook}.', err=True)
                raise click.Abort


def do_main(*, cat: str, ebuild_version: str, pkg: str, search_dir: str,
            settings: LivecheckSettings, last_version: str, top_hash: str, hash_date: str, url: str,
            hook_dir: str | None) -> None:
    cp = f'{cat}/{pkg}'
    ebuild = Path(search_dir) / cp / f'{pkg}-{ebuild_version}.ebuild'
    # TODO: files.pythonhosted.org use different path structure /xx/yy/sha/archive... for replace
    old_sha = get_old_sha(ebuild, url)
    if len(old_sha) == 7:
        top_hash = top_hash[:7]
    if update_sha_too_source := settings.sha_sources.get(cp, None):
        logger.debug('Package also needs a SHA update')
        _, top_hash, hash_date, _ = parse_url(search_dir, update_sha_too_source,
                                              f'{cp}-{ebuild_version}', settings)

        # if empty, it means that the source is not supported
        if not top_hash:
            logger.warning(f'Could not get new SHA for {update_sha_too_source}')
            return
    if hash_date and not last_version:
        last_version = replace_date_in_ebuild(ebuild_version, hash_date, cp)
        hash_date = ''
    if not last_version:
        last_version = ebuild_version
    if last_version == ebuild_version and old_sha != top_hash and old_sha and top_hash:
        _, _, new_version, new_revision = catpkgsplit2(f'{cp}-{last_version}')
        new_revision = 'r' + str(int(new_revision[1:]) + 1)
        logger.debug(f'Incrementing revision to {new_revision}')
        last_version = f'{new_version}-{new_revision}'
    logger.debug(f'top_hash = {last_version}')

    logger.debug(
        f'Comparing current ebuild version {ebuild_version} with live version {last_version}')
    if compare_versions(ebuild_version, last_version):
        dn = Path(ebuild).parent
        new_filename = f'{dn}/{pkg}-{last_version}.ebuild'
        _, _, _, new_version = catpkg_catpkgsplit(f'{cp}-{last_version}')
        _, _, _, old_version = catpkg_catpkgsplit(f'{cp}-{ebuild_version}')
        logger.debug(f'Migrating from {ebuild} to {new_filename}')
        no_auto_update_str = ' (no_auto_update)' if cp in settings.no_auto_update else ''
        str_new_version = str_version(new_version, top_hash)
        str_old_version = str_version(old_version, old_sha)
        print(f'{cat}/{pkg}: {str_old_version} -> '
              f'{str_new_version}{no_auto_update_str}')

        if settings.auto_update_flag and cp not in settings.no_auto_update:
            # First check requirements before update
            if (cp in settings.dotnet_projects and not check_dotnet_requirements()) or (
                    cp in settings.composer_packages and not check_composer_requirements()
            ) or (cp in settings.yarn_base_packages and not check_yarn_requirements()) or (
                    cp in settings.nodejs_packages
                    and not check_nodejs_requirements()) or (cp in settings.gomodule_packages
                                                             and not check_gomodule_requirements()):
                logger.warning('Update is not possible')
                return
            with open(ebuild, encoding='utf-8') as f:
                old_content = content = f.read()
            # Only update the version if it is not a commit
            if top_hash and old_sha:
                content = content.replace(old_sha, top_hash)
            ps_ref = top_hash
            if not is_sha(top_hash) and cp in TAG_NAME_FUNCTIONS:
                ps_ref = TAG_NAME_FUNCTIONS[cp](top_hash)
            content = process_submodules(cp, ps_ref, content, url)
            dn = Path(ebuild).parent
            print(f'{ebuild} -> {new_filename}')
            if settings.keep_old.get(cp, not settings.keep_old_flag):
                if settings.git_flag:
                    try:
                        sp.run(('git', 'mv', ebuild, new_filename), check=True)
                    except sp.CalledProcessError:
                        logger.error(f'Error moving {ebuild} to {new_filename}')
                        return
                else:
                    sp.run(('mv', ebuild, new_filename), check=True)
            with open(new_filename, 'w', encoding='utf-8') as f:
                f.write(content)
            execute_hooks(hook_dir, 'pre', search_dir, cp, ebuild_version, last_version, old_sha,
                          top_hash, hash_date)
            # We do not check the digest because it may happen that additional files need to be
            # created that have not yet been generated until the main ebuild is downloaded for
            # the first time and the hooks create those additional files.
            # And you cannot remove the digest generation either, but rather the repositories
            # that do not have thin-Manifests ( metadata/layout.conf -> thin-manifests = true)
            # see: https://devmanual.gentoo.org/general-concepts/manifest/index.html
            digest_ebuild(new_filename)
            fetchlist = P.getFetchMap(f"{cp}-{last_version}")
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
            if old_content != content:
                with open(new_filename, 'w', encoding='utf-8') as file:
                    file.write(content)
            if not digest_ebuild(new_filename):
                logger.error(f'Error digesting {new_filename}')
                return
            # Second pass
            # Update ebuild or download news file
            if cp in settings.yarn_base_packages:
                update_yarn_ebuild(new_filename, settings.yarn_base_packages[cp], pkg,
                                   settings.yarn_packages.get(cp))
            if cp in settings.go_sum_uri:
                update_go_ebuild(new_filename, top_hash, settings.go_sum_uri[cp])
            if cp in settings.dotnet_projects:
                update_dotnet_ebuild(new_filename, settings.dotnet_projects[cp])
            if cp in settings.jetbrains_packages:
                update_jetbrains_ebuild(new_filename)
            if cp in settings.nodejs_packages:
                update_nodejs_ebuild(new_filename, settings.nodejs_path[cp], fetchlist)
            if cp in settings.gomodule_packages:
                update_gomodule_ebuild(new_filename, settings.gomodule_path[cp], fetchlist)
            if cp in settings.composer_packages:
                update_composer_ebuild(new_filename, settings.composer_path[cp], fetchlist)
            # Restore original ebuild content
            if old_content != content:
                with open(new_filename, 'w', encoding='utf-8') as file:
                    file.write(old_content)
                if not digest_ebuild(new_filename):
                    logger.error(f'Error digesting {new_filename}')
                    return
            if settings.git_flag and sp.run(
                ('ebuild', new_filename, 'digest'), check=False).returncode == 0:
                sp.run(('git', 'add', new_filename), check=True)
                sp.run(('git', 'add', Path(search_dir) / cp / 'Manifest'), check=True)
                try:
                    sp.run(('pkgdev', 'commit'), cwd=Path(search_dir) / cp, check=True)
                except sp.CalledProcessError:
                    logger.error(f'Error committing {new_filename}')
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
              help="Run a hook directory scripts with various parameters.",
              type=click.Path(file_okay=False,
                              dir_okay=True,
                              exists=True,
                              resolve_path=True,
                              executable=True))
@click.option('-k', '--keep-old', is_flag=True, help='Keep old ebuild versions.')
@click.option('-p', '--progress', is_flag=True, help='Enable progress logging.')
@click.option('-W',
              '--working-dir',
              default='.',
              help='Working directory. Should be a port tree root.',
              type=click.Path(file_okay=False, exists=True, resolve_path=True, readable=True))
@click.argument('package_names', nargs=-1)
def main(
    auto_update: bool = False,
    debug: bool = False,
    development: bool = False,
    exclude: tuple[str] | None = None,
    git: bool = False,
    hook_dir: str | None = None,
    keep_old: bool = False,
    package_names: tuple[str] | list[str] | None = None,
    progress: bool = False,
    working_dir: str | None = '.',
) -> int:
    if working_dir and working_dir != '.':
        chdir(working_dir)
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logger.configure(handlers=[{
            "sink":
                sys.stderr,
            "level":
                "INFO",
            "format":
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>"
        }])
    if exclude:
        logger.debug(f'Excluding {", ".join(exclude)}')
    search_dir = working_dir or '.'
    if auto_update and not os.access(search_dir, os.W_OK):
        raise click.ClickException(
            f'The directory "{working_dir}" must be writable because --auto-update is enabled.')
    repo_root, repo_name = get_repository_root_if_inside(search_dir)
    if not repo_root:
        logger.error('Not inside a repository configured in repos.conf')
        raise click.Abort
    if git:
        if not auto_update:
            logger.error('Git option requires --auto-update')
            raise click.Abort
        if not Path(repo_root, '.git').is_dir():
            logger.error(f'Directory {repo_root} is not a git repository')
            raise click.Abort
        # Check if git is installed
        if not check_program('git', '--version'):
            logger.error('Git is not installed')
            raise click.Abort
        # Check if pkgdev is installed
        if not check_program('pkgdev', '--version'):
            logger.error('pkgdev is not installed')
            raise click.Abort
    logger.info(f'search_dir={search_dir} repo_root={repo_root} repo_name={repo_name}')
    settings = gather_settings(search_dir)

    # update flags in settings
    settings.auto_update_flag = auto_update
    settings.debug_flag = debug
    settings.development_flag = development
    settings.git_flag = git
    settings.keep_old_flag = keep_old
    settings.progress_flag = progress

    package_names = sorted(package_names or [])
    for cat, pkg, ebuild_version, last_version, top_hash, hash_date, url in get_props(
            search_dir, repo_root, settings, package_names, exclude):
        try:
            do_main(cat=cat,
                    pkg=pkg,
                    last_version=last_version,
                    top_hash=top_hash,
                    hash_date=hash_date,
                    url=url,
                    search_dir=repo_root,
                    settings=settings,
                    ebuild_version=ebuild_version,
                    hook_dir=hook_dir)
        except Exception:
            print(f'Exception while checking {cat}/{pkg}', file=sys.stderr)
            raise
    return 0
