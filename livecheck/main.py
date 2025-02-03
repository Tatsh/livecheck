"""Main command."""
from collections.abc import Iterator, Sequence
from os import chdir
from pathlib import Path
from typing import TypeVar, cast, Match
from urllib.parse import urlparse
import hashlib
import logging
import re
import subprocess as sp
import sys
import os
import xml.etree.ElementTree as ET

from loguru import logger
import click

from .constants import (
    GIST_HOSTNAMES,
    GITLAB_HOSTNAMES,
    SUBMODULES,
    TAG_NAME_FUNCTIONS,
)
from .settings import LivecheckSettings, gather_settings

from .special.bitbucket import get_latest_bitbucket_package
from .special.composer import update_composer_ebuild, remove_composer_url, check_composer_requirements
from .special.davinci import get_latest_davinci_package
from .special.dotnet import update_dotnet_ebuild, check_dotnet_requirements
from .special.github import get_latest_github_package, get_latest_github, is_github
from .special.gitlab import get_latest_gitlab_package
from .special.golang import update_go_ebuild
from .special.gomodule import update_gomodule_ebuild, remove_gomodule_url, check_gomodule_requirements
from .special.jetbrains import get_latest_jetbrains_package, update_jetbrains_ebuild
from .special.metacpan import get_latest_metacpan_package
from .special.nodejs import update_nodejs_ebuild, remove_nodejs_url, check_nodejs_requirements
from .special.pecl import get_latest_pecl_package
from .special.regex import get_latest_regex_package
from .special.rubygems import get_latest_rubygems_package
from .special.sourceforge import get_latest_sourceforge_package
from .special.sourcehut import get_latest_sourcehut_package, get_latest_sourcehut, is_sourcehut
from .special.yarn import update_yarn_ebuild, check_yarn_requirements

from .typing import PropTuple
from .utils import (chunks, is_sha, make_github_grit_commit_re, get_content, extract_sha)
from .utils.portage import (P, catpkg_catpkgsplit, get_first_src_uri, get_highest_matches,
                            get_repository_root_if_inside, compare_versions, digest_ebuild,
                            catpkgsplit2)

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


def log_unhandled_pkg(catpkg: str, src_uri: str) -> None:
    logger.warning(f'Unhandled: {catpkg} SRC_URI: {src_uri}')


def log_unhandled_commit(catpkg: str, src_uri: str) -> None:
    logger.warning(f'Unhandled commit: {catpkg} SRC_URI: {src_uri}')


def parse_url(repo_root: str, src_uri: str, match: str,
              settings: LivecheckSettings) -> tuple[str, str, str, str]:
    catpkg, _, pkg, _ = catpkg_catpkgsplit(match)

    parsed_uri = urlparse(src_uri)
    last_version = top_hash = hash_date = ''
    url = src_uri

    if not parsed_uri.hostname:
        return last_version, top_hash, hash_date, url

    logger.debug(f'Parsed URI: {parsed_uri}')
    if parsed_uri.hostname in GIST_HOSTNAMES:
        home = P.aux_get(match, ['HOMEPAGE'], mytree=repo_root)[0]
        last_version, hash_date, url = get_latest_regex_package(
            match, f'{home}/revisions', r'<relative-time datetime="([0-9-]{10})', '', settings)
    elif is_github(src_uri):
        last_version, top_hash, hash_date = get_latest_github(src_uri, match, settings)
    elif is_sourcehut(src_uri):
        last_version, top_hash, hash_date = get_latest_sourcehut(src_uri, match, settings)
    elif parsed_uri.hostname == 'git.sr.ht':
        if is_sha(parsed_uri.path):
            log_unhandled_commit(catpkg, src_uri)
        else:
            user_repo = '/'.join(parsed_uri.path.split('/')[1:3])
            branch = settings.branches.get(catpkg, 'master')
            last_version, hash_date, url = get_latest_regex_package(
                match,
                f'https://git.sr.ht/{user_repo}/log/{branch}/rss.xml',
                r'<pubDate>([^<]+)</pubDate>',
                '',
                settings,
            )
    elif src_uri.startswith('mirror://pypi/'):
        dist_name = src_uri.split('/')[4]
        last_version, hash_date, url = get_latest_regex_package(
            match, f'https://pypi.org/pypi/{dist_name}/json', r'"version":"([^"]+)"[,\}]', '',
            settings)
    elif parsed_uri.hostname == 'files.pythonhosted.org':
        dist_name = src_uri.split('/')[-2]
        last_version, hash_date, url = get_latest_regex_package(
            match, f'https://pypi.org/pypi/{dist_name}/json', r'"version":"([^"]+)"[,\}]', '',
            settings)
    elif (parsed_uri.hostname == 'www.raphnet-tech.com'
          and parsed_uri.path.startswith('/downloads')):
        last_version, hash_date, url = get_latest_regex_package(
            match,
            P.aux_get(match, ['HOMEPAGE'], mytree=repo_root)[0],
            (r'\b' + pkg.replace('-', r'[-_]') + r'-([^"]+)\.tar\.gz'),
            '',
            settings,
        )
    elif parsed_uri.hostname == 'download.jetbrains.com':
        last_version = get_latest_jetbrains_package(match, settings)
    elif 'gitlab' in parsed_uri.hostname:
        if is_sha(parsed_uri.path):
            log_unhandled_commit(catpkg, src_uri)
        else:
            last_version, top_hash = get_latest_gitlab_package(src_uri, match, settings)
    elif parsed_uri.hostname == 'cgit.libimobiledevice.org':
        proj = src_uri.split('/')[3]
        last_version, hash_date, url = get_latest_regex_package(
            match,
            f'https://cgit.libimobiledevice.org/{proj}/',
            r"href='/" + re.escape(proj) + r"/tag/\?h=([0-9][^']+)",
            '',
            settings,
        )
    elif parsed_uri.hostname == 'registry.yarnpkg.com':
        path = ('/'.join(parsed_uri.path.split('/')[1:3])
                if parsed_uri.path.startswith('/@') else parsed_uri.path.split('/')[1])
        last_version, hash_date, url = get_latest_regex_package(
            match,
            f'https://registry.yarnpkg.com/{path}',
            r'"latest":"([^"]+)",?',
            '',
            settings,
        )
    elif parsed_uri.hostname == 'pecl.php.net':
        last_version = get_latest_pecl_package(match, settings)
    elif 'metacpan.org' in parsed_uri.hostname or 'cpan' in parsed_uri.hostname:
        last_version = get_latest_metacpan_package(parsed_uri.path, match, settings)
    elif parsed_uri.hostname == 'rubygems.org':
        last_version = get_latest_rubygems_package(match, settings)
    elif 'sourceforge.' in parsed_uri.hostname or 'sf.' in parsed_uri.hostname:
        last_version = get_latest_sourceforge_package(src_uri, match, settings)
    elif parsed_uri.hostname == 'bitbucket.org':
        if is_sha(parsed_uri.path):
            log_unhandled_commit(catpkg, src_uri)
        else:
            last_version, top_hash = get_latest_bitbucket_package(parsed_uri.path, match, settings)
    else:
        log_unhandled_pkg(catpkg, src_uri)

    return last_version, top_hash, hash_date, url


def parse_metadata(repo_root: str, match: str,
                   settings: LivecheckSettings) -> tuple[str, str, str, str]:
    catpkg, _, _, _ = catpkg_catpkgsplit(match)

    metadata_file = os.path.join(repo_root, catpkg, "metadata.xml")
    if not os.path.exists(metadata_file):
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
                text_val = subelem.text.strip() if subelem.text else ""
                attribs = subelem.attrib
                last_version = top_hash = hash_date = url = ''
                if tag_name == 'remote-id':
                    if attribs['type'] == 'github':
                        last_version, top_hash = get_latest_github_package(
                            f'https://github.com/{text_val}', match, settings)
                    if attribs['type'] == 'bitbucket':
                        last_version, top_hash, hash_date, url = parse_url(
                            repo_root, f'https://bitbucket.org/{text_val}', match, settings)
                    if 'gitlab' in attribs['type']:
                        uri = GITLAB_HOSTNAMES[attribs['type']]
                        last_version, top_hash = get_latest_gitlab_package(
                            f'https://{uri}/{text_val}', match, settings)
                    if last_version or top_hash:
                        return last_version, top_hash, hash_date, url
    return '', '', '', ''


def extract_restrict_version(cp: str) -> tuple[str, str]:
    if match := re.match(r"(.*?):(\d+):-(.*)", cp):
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
    for match in matches_list:
        match, settings.restrict_version_process = extract_restrict_version(match)
        catpkg, cat, pkg, ebuild_version = catpkg_catpkgsplit(match)
        if catpkg in exclude or pkg in exclude:
            logger.debug(f'Ignoring {catpkg}')
            continue
        src_uri = get_first_src_uri(match, repo_root)
        if cat.startswith('acct-') or settings.type_packages.get(catpkg) == 'none':
            logger.debug(f'Ignoring {catpkg}')
            continue
        if settings.debug_flag or settings.progress_flag:
            logger.info(f'Processing {catpkg} version {ebuild_version}')
        last_version = hash_date = top_hash = url = ''
        if catpkg in settings.sync_version:
            matches_sync = get_highest_matches([settings.sync_version[catpkg]], '', settings)
            if not matches_sync:
                logger.error(f'No matches for {catpkg}')
                continue
            _, _, _, last_version = catpkg_catpkgsplit(matches_sync[0])
            # remove -r* from version
            last_version = re.sub(r'-r\d+$', '', last_version)
        if settings.type_packages.get(catpkg) == 'davinci':
            last_version = get_latest_davinci_package(pkg)
        elif catpkg in settings.custom_livechecks:
            url, regex, _, version = settings.custom_livechecks[catpkg]
            last_version, hash_date, url = get_latest_regex_package(match, url, regex, version,
                                                                    settings)
        elif catpkg in settings.checksum_livechecks:
            manifest_file = Path(search_dir) / catpkg / 'Manifest'
            bn = Path(src_uri).name
            found = False
            try:
                with open(manifest_file, 'r', encoding='utf-8') as f:
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
            last_version, top_hash, hash_date, url = parse_url(repo_root, src_uri, match, settings)
            if not last_version and not top_hash:
                last_version, top_hash, hash_date, url = parse_metadata(repo_root, match, settings)
        if last_version or top_hash:
            logger.debug(f'Inserting {catpkg}: {ebuild_version} -> {last_version} : {top_hash}')
            yield (cat, pkg, ebuild_version, last_version, top_hash, hash_date, url)
        else:
            logger.debug(f'Ignoring {catpkg}, update not available')


def get_old_sha(ebuild: str, url: str) -> str:
    sha_pattern = re.compile(r'(SHA|COMMIT|EGIT_COMMIT)=["\']?([a-f0-9]{40})["\']?')

    with open(ebuild, 'r', encoding='utf-8') as file:
        for line in file:
            match = sha_pattern.search(line)
            if match:
                return match.group(2)

    last_part = urlparse(url).path.rsplit('/', 1)[-1] if '/' in url else url
    return extract_sha(last_part)


def log_unsupported_sha_source(src: str) -> None:
    logger.debug(f'Unsupported SHA source: {src}')


def get_new_sha(src: str) -> str:
    content = get_content(src)
    if not content.text:
        return ''

    parsed_src = urlparse(src)
    if (parsed_src.hostname == 'github.com' and src.endswith('.atom')):
        if m := re.search(make_github_grit_commit_re(40 * ' '), content.text):
            return str(m.groups()[0])
    if parsed_src.hostname == 'git.sr.ht' and src.endswith('xml'):
        user_repo = '/'.join(parsed_src.path.split('/')[1:3])
        if m := re.search(rf'<guid>https://git\.sr\.ht/{user_repo}/commit/([a-f0-9]+)</guid>',
                          content.text):
            return str(m.groups()[0])

    log_unsupported_sha_source(src)
    return ''


def log_unhandled_state(cat: str, pkg: str, url: str, regex: str | None = None) -> None:
    logger.debug(f'Unhandled state: regex={regex}, cat={cat}, pkg={pkg}, url={url}')


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
    if old_version != new_version:
        return str(new_version)
    return n


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
    ebuild = os.path.join(search_dir, cp, f'{pkg}-{ebuild_version}.ebuild')
    old_sha = get_old_sha(ebuild, url)
    if len(old_sha) == 7:
        top_hash = top_hash[:7]
    if update_sha_too_source := settings.sha_sources.get(cp, None):
        logger.debug('Package also needs a SHA update')
        #top_hash = get_new_sha(update_sha_too_source)
        _, top_hash, hash_date, _ = parse_url(search_dir, update_sha_too_source,
                                              f'{cp}-{last_version}', settings)

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
        if cp in settings.no_auto_update:
            no_auto_update_str = ' (no_auto_update)'
        else:
            no_auto_update_str = ''
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
            with open(ebuild, 'r', encoding='utf-8') as f:
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
                sp.run(('git', 'add', os.path.join(search_dir, cp, 'Manifest')), check=True)
                try:
                    sp.run(('pkgdev', 'commit'), cwd=os.path.join(search_dir, cp), check=True)
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
        if not os.path.isdir(os.path.join(repo_root, '.git')):
            logger.error(f'Directory {repo_root} is not a git repository')
            raise click.Abort
        # Check if git is installed
        if sp.run(('git', '--version'), stdout=sp.PIPE, check=False).returncode != 0:
            logger.error('Git is not installed')
            raise click.Abort
        # Check if pkgdev is installed
        if sp.run(('pkgdev', '--version'), stdout=sp.PIPE, check=False).returncode != 0:
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
