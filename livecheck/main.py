"""Main command."""
from collections.abc import Iterator, Sequence
from os import chdir
from pathlib import Path
from typing import TypeVar, cast
from urllib.parse import urlparse
import hashlib
import logging
import re
import subprocess as sp
import sys
import os

from loguru import logger
from portage.exception import InvalidAtom
from portage import portdb
import click
import requests
from typing import Match

from .constants import (
    GIST_HOSTNAMES,
    GITLAB_HOSTNAMES,
    PREFIX_RE,
    SUBMODULES,
    TAG_NAME_FUNCTIONS,
)
from .settings import LivecheckSettings, gather_settings
from .special.dotnet import update_dotnet_ebuild
from .special.golang import update_go_ebuild
from .special.gomodule import update_gomodule_ebuild, remove_gomodule_url
from .special.jetbrains import get_latest_jetbrains_package, update_jetbrains_ebuild
from .special.metacpan import get_latest_metacpan_package
from .special.nodejs import update_nodejs_ebuild, remove_nodejs_url
from .special.composer import update_composer_ebuild, remove_composer_url
from .special.pecl import get_latest_pecl_package
from .special.regex import get_latest_regex_package
from .special.rubygems import get_latest_rubygems_package
from .special.sourceforge import get_latest_sourceforge_package

from .special.yarn import update_yarn_ebuild
from .typing import PropTuple
from .utils import (chunks, get_github_api_credentials, is_sha, make_github_grit_commit_re,
                    make_github_grit_title_re)
from .utils.portage import (P, catpkg_catpkgsplit, get_first_src_uri, get_highest_matches,
                            get_highest_matches2, get_repository_root_if_inside, sanitize_version,
                            compare_versions, digest_ebuild, catpkgsplit)

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
        r = requests.get((f'https://api.github.com/repos/{repo_root}/contents/{name}'
                          f'?ref={ref}'),
                         headers=dict(Authorization=f'token {get_github_api_credentials()}'),
                         timeout=30)
        r.raise_for_status()
        remote_sha = r.json()['sha']
        for line in ebuild_lines:
            if (line.startswith(grep_for)
                    and (local_sha := line.split('=')[1].replace('"', '').strip()) != remote_sha):
                contents = contents.replace(local_sha, remote_sha)
    return contents


def log_unhandled_pkg(catpkg: str, home: str, src_uri: str):
    logger.debug(f'Not handled: {catpkg} (checksum), homepage: {home}, '
                 f'SRC_URI: {src_uri}')


def log_unhandled_github_package(catpkg: str):
    logger.debug(f'Unhandled GitHub package: {catpkg}')


def get_props(search_dir: str,
              repo_root: str,
              settings: LivecheckSettings,
              names: Sequence[str] | None = None,
              exclude: Sequence[str] | None = None,
              *,
              progress: bool = False,
              debug: bool = False,
              development: bool = False) -> Iterator[PropTuple]:
    exclude = exclude or []
    try:
        matches_list = sorted(
            get_highest_matches(search_dir, repo_root
                                ) if not names else get_highest_matches2(names, repo_root))
    except InvalidAtom as e:
        logger.error(f"Invalid Atom: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return None
    logger.info(f'Found {len(matches_list)} ebuilds')
    if not matches_list:
        logger.error('No matches!')
        raise click.Abort
    for match in matches_list:
        catpkg, cat, pkg, ebuild_version = catpkg_catpkgsplit(match)
        devel = settings.development.get(catpkg, development)
        if catpkg in exclude or pkg in exclude:
            logger.debug(f'Ignoring {catpkg}')
            continue
        src_uri = get_first_src_uri(match, repo_root)
        parsed_uri = urlparse(src_uri)
        if cat.startswith('acct-') or catpkg in settings.ignored_packages:
            logger.debug(f'Ignoring {catpkg}')
            continue
        # Exclude packages with no SRC_URI
        # live ebuilds o virtual packages
        if not src_uri:
            logger.debug(f'Ignoring {catpkg}')
            continue
        if debug or progress:
            logger.info(f'Processing {catpkg} version {ebuild_version}')
        last_version = ''
        hash_date = ''
        url = ''
        if catpkg in settings.custom_livechecks:
            url, regex, _, version = settings.custom_livechecks[catpkg]
            last_version, hash_date, url = get_latest_regex_package(
                ebuild_version, catpkg, settings, url, regex, version, devel)
        elif catpkg in settings.checksum_livechecks:
            manifest_file = Path(search_dir) / catpkg / 'Manifest'
            bn = Path(src_uri).name
            found = False
            try:
                with open(manifest_file) as f:
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
                        r = requests.get(src_uri, timeout=30)
                        r.raise_for_status()
                        last_version, hash_date, url = get_latest_regex_package(
                            ebuild_version, catpkg, settings,
                            dict(cast(Sequence[tuple[str, str]], chunks(fields_s.split(' '),
                                                                        2)))['SHA512'],
                            f'data:{hashlib.sha512(r.content).hexdigest()}', r'^[0-9a-f]+$', devel)
                        break
            except FileNotFoundError:
                pass
            if not found:
                home = P.aux_get(match, ['HOMEPAGE'], mytree=repo_root)[0]
                log_unhandled_pkg(catpkg, home, src_uri)
        elif parsed_uri.hostname == 'github.com':
            logger.debug(f'Parsed path: {parsed_uri.path}')
            github_homepage = f'https://github.com{"/".join(parsed_uri.path.split("/")[0:3])}'
            filename = Path(parsed_uri.path).name
            version = re.split(r'\.(?:tar\.(?:gz|bz2)|zip)$', filename, maxsplit=2)[0]
            if (re.match(r'^[0-9a-f]{7,}$', version) and not re.match('^[0-9a-f]{8}$', version)):
                branch = (settings.branches.get(catpkg, 'master'))
                last_version, hash_date, url = get_latest_regex_package(
                    ebuild_version, catpkg, settings, f'{github_homepage}/commits/{branch}.atom',
                    make_github_grit_commit_re(40 * ' '), version, devel)
            elif ('/releases/download/' in parsed_uri.path or '/archive/' in parsed_uri.path):
                prefix = ''
                if (m := re.match(PREFIX_RE, filename) if '/archive/' in parsed_uri.path else
                        re.match(PREFIX_RE,
                                 Path(parsed_uri.path).parent.name)):
                    prefix = m.group(1)
                url = f'{github_homepage}/tags'
                regex = f'archive/refs/tags/{prefix}([^"]+)\\.tar\\.gz'
                if re.match(r'^wiimms-(iso|szs)-tools$', pkg):
                    regex = make_github_grit_title_re()
                    url = f'github.com/Wiimm/{pkg}/commits/master.atom'
                last_version, hash_date, url = get_latest_regex_package(
                    ebuild_version, catpkg, settings, url, regex, version, devel)
            elif m := re.search(r'/raw/([0-9a-f]+)/', parsed_uri.path):
                version = m.group(1)
                branch = (settings.branches.get(catpkg, 'master'))
                last_version, hash_date, url = get_latest_regex_package(
                    ebuild_version, catpkg, settings, f'{github_homepage}/commits/{branch}.atom',
                    (r'<id>tag:github.com,2008:Grit::Commit/([0-9a-f]{' + str(len(version)) +
                     r'})[0-9a-f]*</id>'), version, devel)
            else:
                log_unhandled_github_package(catpkg)
        elif parsed_uri.hostname == 'git.sr.ht':
            user_repo = '/'.join(parsed_uri.path.split('/')[1:3])
            branch = (settings.branches.get(catpkg, 'master'))
            last_version, hash_date, url = get_latest_regex_package(
                ebuild_version, catpkg, settings,
                f'https://git.sr.ht/{user_repo}/log/{branch}/rss.xml',
                r'<pubDate>([^<]+)</pubDate>', '', devel)
        elif parsed_uri.hostname in GIST_HOSTNAMES:
            home = P.aux_get(match, ['HOMEPAGE'], mytree=repo_root)[0]
            last_version, hash_date, url = get_latest_regex_package(
                ebuild_version, catpkg, settings, f'{home}/revisions',
                r'<relative-time datetime="([0-9-]{10})', '', devel)
        elif src_uri.startswith('mirror://pypi/'):
            dist_name = src_uri.split('/')[4]
            last_version, hash_date, url = get_latest_regex_package(
                ebuild_version, catpkg, settings, f'https://pypi.org/pypi/{dist_name}/json',
                r'"version":"([^"]+)"[,\}]', '', devel)
        elif parsed_uri.hostname == 'files.pythonhosted.org':
            dist_name = src_uri.split('/')[-2]
            last_version, hash_date, url = get_latest_regex_package(
                ebuild_version, catpkg, settings, f'https://pypi.org/pypi/{dist_name}/json',
                r'"version":"([^"]+)"[,\}]', '', devel)
        elif (parsed_uri.hostname == 'www.raphnet-tech.com'
              and parsed_uri.path.startswith('/downloads')):
            last_version, hash_date, url = get_latest_regex_package(
                ebuild_version, catpkg, settings,
                P.aux_get(match, ['HOMEPAGE'], mytree=repo_root)[0],
                (r'\b' + pkg.replace('-', r'[-_]') + r'-([^"]+)\.tar\.gz'), '', devel)
        elif parsed_uri.hostname == 'download.jetbrains.com':
            last_version = get_latest_jetbrains_package(pkg, devel)
        elif (parsed_uri.hostname in GITLAB_HOSTNAMES and '/archive/' in parsed_uri.path):
            author, proj = src_uri.split('/')[3:5]
            m = re.match('^https://([^/]+)', src_uri)
            assert m is not None
            domain = m.group(1)
            last_version, hash_date, url = get_latest_regex_package(
                ebuild_version, catpkg, settings,
                f'https://{domain}/{author}/{proj}/-/tags?format=atom',
                r'<title>v?([0-9][^>]+)</title', '', devel)
        elif parsed_uri.hostname == 'cgit.libimobiledevice.org':
            proj = src_uri.split('/')[3]
            last_version, hash_date, url = get_latest_regex_package(
                ebuild_version, catpkg, settings, f'https://cgit.libimobiledevice.org/{proj}/',
                r"href='/" + re.escape(proj) + r"/tag/\?h=([0-9][^']+)", '', devel)
        elif parsed_uri.hostname == 'registry.yarnpkg.com':
            path = ('/'.join(parsed_uri.path.split('/')[1:3])
                    if parsed_uri.path.startswith('/@') else parsed_uri.path.split('/')[1])
            last_version, hash_date, url = get_latest_regex_package(
                ebuild_version, catpkg, settings, f'https://registry.yarnpkg.com/{path}',
                r'"latest":"([^"]+)",?', '', devel)
        elif parsed_uri.hostname == 'pecl.php.net':
            last_version = get_latest_pecl_package(pkg, devel)
        elif parsed_uri.hostname == 'metacpan.org' or parsed_uri.hostname == 'cpan':
            last_version = get_latest_metacpan_package(pkg)
        elif parsed_uri.hostname == 'rubygems.org':
            last_version = get_latest_rubygems_package(pkg)
        elif parsed_uri.hostname == 'downloads.sourceforge.net':
            last_version = get_latest_sourceforge_package(pkg)
        else:
            logger.debug(f'Unhandled: {catpkg} {parsed_uri.hostname}')
            home = P.aux_get(match, ['HOMEPAGE'], mytree=repo_root)[0]
            log_unhandled_pkg(catpkg, home, src_uri)
        if last_version:
            logger.debug(f'Inserting {catpkg}: {ebuild_version} -> {last_version}')
            yield (cat, pkg, ebuild_version, last_version, hash_date, url)


def get_old_sha(ebuild: str) -> str:
    sha_pattern = re.compile(r'(SHA|COMMIT|EGIT_COMMIT)=["\']?([a-f0-9]{40})["\']?')

    with open(ebuild, 'r') as file:
        for line in file:
            match = sha_pattern.search(line)
            if match:
                return match.group(2)

    return ''


def log_unsupported_sha_source(src: str) -> None:
    logger.debug(f'Unsupported SHA source: {src}')


def get_new_sha(src: str) -> str:
    parsed_src = urlparse(src)
    if (parsed_src.hostname == 'github.com' and src.endswith('.atom')):
        m = re.search(make_github_grit_commit_re(40 * ' '),
                      requests.get(src, timeout=30).content.decode())
        assert m is not None
        return m.groups()[0]
    if parsed_src.hostname == 'git.sr.ht' and src.endswith('xml'):
        user_repo = '/'.join(parsed_src.path.split('/')[1:3])
        m = re.search(rf'<guid>https://git\.sr\.ht/{user_repo}/commit/([a-f0-9]+)</guid>',
                      requests.get(src, timeout=30).content.decode())
        assert m is not None
        return m.groups()[0]
    log_unsupported_sha_source(src)


def log_unhandled_state(cat: str, pkg: str, url: str, regex: str | None = None) -> None:
    logger.debug(f'Unhandled state: regex={regex}, cat={cat}, pkg={pkg}, url={url}')


def str_version(version: str, revision: str, sha: str) -> str:
    if revision != 'r0':
        version = version + f'-{revision}'
    if sha:
        version = version + f' ({sha})'
    return version


def replace_date_in_ebuild(ebuild: str, new_date: str) -> str:
    patterns = [
        r'(_p|_r|\.|-r|_pre)(\d{8})(-r\d+)?', r'(\d{4}\.\d{2}\.\d{2})(-r\d+)?', r'\d{8}',
        r'(\d+\.\d+\.)(\d{6})(-r\d+)?', r'(\d{4}\.\d+\.\d+)(-r\d+)?'
    ]

    y, m, d = new_date[:4], new_date[4:6], new_date[6:]
    replacements = {"yyyymmdd": new_date, "yyyy.mm.dd": f"{y}.{m}.{d}", "yyMMdd": f"{y[2:]}{m}{d}"}
    for pattern in patterns:
        ebuild = re.sub(pattern, lambda match: _replace_format(match, replacements), ebuild)

    return ebuild


def _replace_format(match: Match[str], replacements: dict[str, str]) -> str:
    if len(match.groups()) == 1 and match.group(1) in ['_p', '_r', '.', '-', '_pre']:
        return f"{match.group(1)}{replacements['yyyymmdd']}"
    elif '.' in match.group(0):
        return replacements['yyyy.mm.dd']
    elif len(match.group(0)) == 8 or '-r' in match.group(0):
        return replacements['yyyymmdd']
    elif len(match.groups()) > 1 and match.group(2):
        return f"{match.group(1)}{replacements['yyMMdd']}"
    return match.group(0)


def do_main(*, auto_update: bool, keep_old: bool, cat: str, ebuild_version: str, pkg: str,
            search_dir: str, settings: LivecheckSettings, top_hash: str, hash_date: str, url: str,
            git: bool) -> None:
    cp = f'{cat}/{pkg}'
    ebuild = os.path.join(search_dir, cp, f'{pkg}-{ebuild_version}.ebuild')
    new_sha = ''
    old_sha = get_old_sha(ebuild)
    if cp in settings.regex_version:
        logger.debug(f'Applying regex for {cp} old version {top_hash}')
        regex, replace = settings.regex_version[cp]
        top_hash = re.sub(regex, replace, top_hash)
    top_hash = sanitize_version(top_hash)
    if cp == 'games-emulation/play':
        top_hash = top_hash.replace('-', '.')
    logger.debug(f'top_hash = {top_hash}')

    if update_sha_too_source := settings.sha_sources.get(cp, None):
        logger.debug('Package also needs a SHA update')
        new_sha = get_new_sha(update_sha_too_source)
        # if empty, it means that the source is not supported
        if not new_sha:
            logger.warning(f'Could not get new SHA for {update_sha_too_source}')
            return
    logger.debug(f'Comparing current ebuild version {ebuild_version} with live version {top_hash}')
    if compare_versions(ebuild_version, top_hash, True, old_sha):
        dn = Path(ebuild).parent
        if hash_date:
            new_pkg = replace_date_in_ebuild(ebuild_version, hash_date)
            new_filename = f'{dn}/{pkg}-{new_pkg}.ebuild'
            logger.debug(f'Updating ebuild {ebuild} to {new_filename}')
            result = catpkgsplit(f'{cat}/{pkg}-{new_pkg}')
        else:
            new_filename = f'{dn}/{pkg}-{top_hash}.ebuild'
            result = catpkgsplit(f'{cp}-{top_hash}')
        if not result:
            logger.error(f'Invalid atom: {cp}-{top_hash}')
            return
        _, _, new_version, new_revision = result
        result = catpkgsplit(f'{cp}-{ebuild_version}')
        if not result:
            logger.error(f'Invalid atom: {cp}-{ebuild_version}')
            return
        _, _, old_version, old_revision = result
        if ebuild == new_filename:
            new_revision = 'r' + str(int(new_revision[1:]) + 1)
            logger.debug(f'Incrementing revision to {new_revision}')
            new_filename = f'{dn}/{pkg}-{new_version}-{new_revision}.ebuild'
        logger.debug(f'Migrating from {ebuild} to {new_filename}')
        if cp in settings.no_auto_update:
            no_auto_update_str = ' (no_auto_update)'
        else:
            no_auto_update_str = ''
        str_new_version = str_version(new_version, new_revision, new_sha)
        str_old_version = str_version(old_version, old_revision, old_sha)
        print(f'{cat}/{pkg}: {str_old_version} -> '
              f'{str_new_version}{no_auto_update_str}')

        if auto_update and cp not in settings.no_auto_update:
            with open(ebuild) as f:
                old_content = content = f.read()
            # Only update the version if it is not a commit
            if new_sha and old_sha:
                content = content.replace(old_sha, new_sha)
            ps_ref = top_hash
            if not is_sha(top_hash) and cp in TAG_NAME_FUNCTIONS:
                ps_ref = TAG_NAME_FUNCTIONS[cp](top_hash)
            content = process_submodules(cp, ps_ref, content, url)
            dn = Path(ebuild).parent
            print(f'{ebuild} -> {new_filename}')
            if settings.keep_old.get(cp, not keep_old):
                if git:
                    sp.run(('git', 'mv', ebuild, new_filename), check=True)
                else:
                    sp.run(('mv', ebuild, new_filename), check=True)
            with open(new_filename, 'w') as f:
                f.write(content)
            fetchlist = portdb.getFetchMap(f"{cp}-{str_new_version}")
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
                with open(new_filename, 'w') as file:
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
                update_go_ebuild(new_filename, pkg, top_hash, settings.go_sum_uri[cp])
            if cp in settings.dotnet_projects:
                update_dotnet_ebuild(new_filename, settings.dotnet_projects[cp], cp)
            if cp in settings.jetbrains_packages:
                update_jetbrains_ebuild(new_filename, url)
            if cp in settings.nodejs_packages:
                update_nodejs_ebuild(new_filename, settings.nodejs_path[cp], fetchlist)
            if cp in settings.gomodule_packages:
                update_gomodule_ebuild(new_filename, settings.gomodule_path[cp], fetchlist)
            if cp in settings.composer_packages:
                update_composer_ebuild(new_filename, settings.composer_path[cp], fetchlist)
            # Restore original ebuild content
            if old_content != content:
                with open(new_filename, 'w') as file:
                    file.write(old_content)
                if not digest_ebuild(new_filename):
                    logger.error(f'Error digesting {new_filename}')
                    return
            if git and sp.run(('ebuild', new_filename, 'digest'), check=False).returncode == 0:
                sp.run(('git', 'add', new_filename), check=True)
                sp.run(('git', 'add', os.path.join(search_dir, cp, 'Manifest')), check=True)
                try:
                    sp.run(('pkgdev', 'commit'), cwd=os.path.join(search_dir, cp), check=True)
                except sp.CalledProcessError:
                    logger.error(f'Error committing {new_filename}')


@click.command()
@click.option('-a', '--auto-update', is_flag=True, help='Rename and modify ebuilds.')
@click.option('-d', '--debug', is_flag=True, help='Enable debug logging.')
@click.option('-D', '--development', is_flag=True, help='Include development packages.')
@click.option('-e', '--exclude', multiple=True, help='Exclude package(s) from updates.')
@click.option('-g', '--git', is_flag=True, help='Use git and pkgdev to make changes.')
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
    keep_old: bool = False,
    git: bool = False,
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
    package_names = sorted(package_names or [])
    for cat, pkg, ebuild_version, last_version, hash_date, url in get_props(
            search_dir,
            repo_root,
            settings,
            package_names,
            exclude,
            progress=progress,
            debug=debug,
            development=development):

        try:
            do_main(cat=cat,
                    pkg=pkg,
                    top_hash=last_version,
                    hash_date=hash_date,
                    url=url,
                    search_dir=repo_root,
                    auto_update=auto_update,
                    keep_old=keep_old,
                    settings=settings,
                    ebuild_version=ebuild_version,
                    git=git)
        except (requests.exceptions.HTTPError, requests.exceptions.SSLError) as e:
            logger.debug(f'Caught error while checking {cat}/{pkg}: {e}')
        except Exception:
            print(f'Exception while checking {cat}/{pkg}', file=sys.stderr)
            raise
    return 0
