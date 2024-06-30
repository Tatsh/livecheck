"""Main command."""
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from functools import cmp_to_key
from os import chdir
from pathlib import Path
from typing import TypeVar, cast
from urllib.parse import ParseResult, urlparse
import contextlib
import hashlib
import logging
import re
import subprocess as sp
import sys
import xml.etree.ElementTree as etree

from loguru import logger
from portage.versions import vercmp
from requests import ConnectTimeout, ReadTimeout
import click
import requests

from .constants import (
    GIST_HOSTNAMES,
    GITLAB_HOSTNAMES,
    PREFIX_RE,
    RSS_NS,
    SEMVER_RE,
    SUBMODULES,
    TAG_NAME_FUNCTIONS,
)
from .settings import LivecheckSettings, gather_settings
from .special.dotnet import update_dotnet_ebuild
from .special.golang import update_go_ebuild
from .special.yarn import update_yarn_ebuild
from .typing import PropTuple, Response
from .utils import (
    TextDataResponse,
    chunks,
    get_github_api_credentials,
    is_sha,
    latest_jetbrains_versions,
    make_github_grit_commit_re,
    make_github_grit_title_re,
    unique_justseen,
)
from .utils.portage import (
    P,
    catpkg_catpkgsplit,
    find_highest_match_ebuild_path,
    get_first_src_uri,
    get_highest_matches,
    get_highest_matches2,
    sort_by_v,
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


class UnhandledPackage(RuntimeError):
    def __init__(self, catpkg: str, home: str, src_uri: str):
        super().__init__(f'Not handled: {catpkg} (checksum), homepage: {home}, '
                         f'SRC_URI: {src_uri}')


class UnhandledGitHubPackage(ValueError):
    def __init__(self, catpkg: str):
        super().__init__(f'Unhandled GitHub package: {catpkg}')


def get_props(search_dir: str,
              settings: LivecheckSettings,
              names: Sequence[str] | None = None,
              exclude: Sequence[str] | None = None) -> Iterator[PropTuple]:
    logger.debug(f'search_dir={search_dir}')
    exclude = exclude or []
    matches = unique_justseen(sorted(set(
        get_highest_matches(search_dir) if not names else get_highest_matches2(names, search_dir)),
                                     key=cmp_to_key(sort_by_v)),
                              key=lambda a: catpkg_catpkgsplit(a)[0])
    if not matches:
        logger.error('No matches!')
        raise click.Abort
    for match in matches:
        catpkg, cat, pkg, ebuild_version = catpkg_catpkgsplit(match)
        if catpkg in exclude or pkg in exclude:
            logger.debug(f'Ignoring {catpkg}')
            continue
        src_uri = get_first_src_uri(match)
        parsed_uri = urlparse(src_uri)
        if cat.startswith('acct-') or catpkg in settings.ignored_packages:
            logger.debug(f'Ignoring {catpkg}')
            continue
        if catpkg in settings.custom_livechecks:
            url, regex, use_vercmp, version = settings.custom_livechecks[catpkg]
            yield (cat, pkg, version or ebuild_version, version
                   or ebuild_version, url, regex, use_vercmp)
        elif catpkg in settings.checksum_livechecks:
            manifest_file = Path(search_dir) / catpkg / 'Manifest'
            bn = Path(src_uri).name
            found = False
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
                    yield (cat, pkg, ebuild_version,
                           dict(cast(Sequence[tuple[str, str]], chunks(fields_s.split(' '),
                                                                       2)))['SHA512'],
                           f'data:{hashlib.sha512(r.content).hexdigest()}', r'^[0-9a-f]+$', False)
                    break
            if not found:
                home = P.aux_get(match, ['HOMEPAGE'], mytree=search_dir)[0]
                raise UnhandledPackage(catpkg, home, src_uri)
        elif parsed_uri.hostname == 'github.com':
            logger.debug(f'Parsed path: {parsed_uri.path}')
            github_homepage = f'https://github.com{"/".join(parsed_uri.path.split("/")[0:3])}'
            filename = Path(parsed_uri.path).name
            version = re.split(r'\.(?:tar\.(?:gz|bz2)|zip)$', filename, maxsplit=2)[0]
            if (re.match(r'^[0-9a-f]{7,}$', version) and not re.match('^[0-9a-f]{8}$', version)):
                branch = (settings.branches.get(catpkg, 'master'))
                yield (cat, pkg, ebuild_version, version,
                       f'{github_homepage}/commits/{branch}.atom',
                       make_github_grit_commit_re(version), False)
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
                yield (cat, pkg, ebuild_version, ebuild_version, url, regex, True)
            elif m := re.search(r'/raw/([0-9a-f]+)/', parsed_uri.path):
                version = m.group(1)
                branch = (settings.branches.get(catpkg, 'master'))
                yield (cat, pkg, ebuild_version, version,
                       f'{github_homepage}/commits/{branch}.atom',
                       (r'<id>tag:github.com,2008:Grit::Commit/([0-9a-f]{' + str(len(version)) +
                        r'})[0-9a-f]*</id>'), False)
            else:
                raise UnhandledGitHubPackage(catpkg)
        elif parsed_uri.hostname == 'git.sr.ht':
            user_repo = '/'.join(parsed_uri.path.split('/')[1:3])
            branch = (settings.branches.get(catpkg, 'master'))
            yield (cat, pkg, ebuild_version, ebuild_version,
                   f'https://git.sr.ht/{user_repo}/log/{branch}/rss.xml',
                   r'<pubDate>([^<]+)</pubDate>', False)
        elif parsed_uri.hostname in GIST_HOSTNAMES:
            home = P.aux_get(match, ['HOMEPAGE'], mytree=search_dir)[0]
            yield (cat, pkg, ebuild_version, ebuild_version, f'{home}/revisions',
                   r'<relative-time datetime="([0-9-]{10})', False)
        elif src_uri.startswith('mirror://pypi/'):
            dist_name = src_uri.split('/')[4]
            yield (cat, pkg, ebuild_version, ebuild_version,
                   f'https://pypi.org/pypi/{dist_name}/json', r'"version":"([^"]+)"[,\}]', True)
        elif parsed_uri.hostname == 'files.pythonhosted.org':
            dist_name = src_uri.split('/')[-2]
            yield (cat, pkg, ebuild_version, ebuild_version,
                   f'https://pypi.org/pypi/{dist_name}/json', r'"version":"([^"]+)"[,\}]', True)
        elif (parsed_uri.hostname == 'www.raphnet-tech.com'
              and parsed_uri.path.startswith('/downloads')):
            yield (cat, pkg, ebuild_version, ebuild_version,
                   P.aux_get(match, ['HOMEPAGE'], mytree=search_dir)[0],
                   (r'\b' + pkg.replace('-', r'[-_]') + r'-([^"]+)\.tar\.gz'), True)
        elif parsed_uri.hostname == 'download.jetbrains.com':
            yield (cat, pkg, ebuild_version, ebuild_version,
                   'https://www.jetbrains.com/updates/updates.xml', None, True)
        elif (parsed_uri.hostname in GITLAB_HOSTNAMES and '/archive/' in parsed_uri.path):
            author, proj = src_uri.split('/')[3:5]
            m = re.match('^https://([^/]+)', src_uri)
            assert m is not None
            domain = m.group(1)
            yield (cat, pkg, ebuild_version, ebuild_version,
                   f'https://{domain}/{author}/{proj}/-/tags?format=atom',
                   r'<title>v?([0-9][^>]+)</title', True)
        elif parsed_uri.hostname == 'cgit.libimobiledevice.org':
            proj = src_uri.split('/')[3]
            yield (cat, pkg, ebuild_version, ebuild_version,
                   f'https://cgit.libimobiledevice.org/{proj}/',
                   r"href='/" + re.escape(proj) + r"/tag/\?h=([0-9][^']+)", True)
        elif parsed_uri.hostname == 'registry.yarnpkg.com':
            path = ('/'.join(parsed_uri.path.split('/')[1:3])
                    if parsed_uri.path.startswith('/@') else parsed_uri.path.split('/')[1])
            yield (cat, pkg, ebuild_version, ebuild_version, f'https://registry.yarnpkg.com/{path}',
                   r'"latest":"([^"]+)",?', True)
        else:
            home = P.aux_get(match, ['HOMEPAGE'], mytree=search_dir)[0]
            raise UnhandledPackage(catpkg, home, src_uri)


def special_vercmp(x: str, y: str) -> int:
    return 1 if (ret := vercmp(x, y)) is None else ret


class ExpectedSHALine(RuntimeError):
    def __init__(self) -> None:
        super().__init__('Expected SHA line to be present')


def get_old_sha(ebuild: str) -> str:
    with open(ebuild) as f:
        for line in f.readlines():
            if line.startswith('SHA="'):
                return line.split('"')[1]
    raise ExpectedSHALine


class UnsupportedSHASource(ValueError):
    def __init__(self, src: str) -> None:
        super().__init__(f'Unsupported SHA source: {src}')


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
    raise UnsupportedSHASource(src)


class UnhandledState(RuntimeError):
    def __init__(self, cat: str, pkg: str, url: str, regex: str | None = None) -> None:
        super().__init__(f'Unhandled state: regex={regex}, cat={cat}, pkg={pkg}, url={url}')


def do_main(*, auto_update: bool, cat: str, ebuild_version: str, parsed_uri: ParseResult, pkg: str,
            r: Response, regex: str | None, search_dir: str, settings: LivecheckSettings, url: str,
            use_vercmp: bool, version: str) -> None:
    r.raise_for_status()
    cp = f'{cat}/{pkg}'
    prefixes: dict[str, str] | None = None
    if not regex:
        if 'www.jetbrains.com/updates' in url:
            if pkg.startswith('idea'):
                jb_versions = list(latest_jetbrains_versions(r.text, 'IntelliJ IDEA'))
                results = [x['fullNumber'] for x in jb_versions]
                prefixes = {z['fullNumber']: f"{z['version']}." for z in jb_versions}
            else:
                raise UnhandledState(cat, pkg, url)
        else:
            raise UnhandledState(cat, pkg, url)
    else:
        needs_adjustment = (re.match(SEMVER_RE, version) and regex.startswith('archive/')
                            and settings.semver.get(cp, True))
        logger.debug(f'Using RE: "{regex}"')
        # Ignore beta/alpha/etc if semantic and coming from GitHub
        if needs_adjustment:
            logger.debug('Adjusting RE for semantic versioning')
        new_regex = (regex.replace(r'([^"]+)', r'v?(\d+\.\d+(?:\.\d+)?)')
                     if needs_adjustment else regex)
        if needs_adjustment:
            logger.debug(f'Adjusted RE: {new_regex}')
        results = re.findall(new_regex, r.text)
    if tf := settings.transformations.get(cp, None):
        results = [tf(x) for x in results]
    logger.debug(f'Result count: {len(results)}')
    top_hash = (sorted(results, key=cmp_to_key(special_vercmp), reverse=True)
                if use_vercmp else results)[0]
    logger.debug(f're.findall() -> "{top_hash}"')
    if update_sha_too_source := settings.sha_sources.get(cp, None):
        logger.debug('Package also needs a SHA update')
    if cp == 'games-emulation/play':
        top_hash = top_hash.replace('-', '.')
    if prefixes:
        assert top_hash in prefixes
        top_hash = f'{prefixes[top_hash]}{top_hash}'
    if (re.match(r'[0-9]{4}-[0-9]{2}-[0-9]{2}$', top_hash)
            and parsed_uri.hostname == 'gist.github.com'):
        top_hash = top_hash.replace('-', '')
    else:
        try:
            top_hash = datetime.strptime(' '.join(top_hash.split(' ')[0:-2]),
                                         '%a, %d %b %Y').astimezone(UTC).strftime('%Y%m%d')
            logger.debug('Succeeded converting top_hash to datetime')
        except ValueError:
            logger.debug('Attempted to fix top_hash date but it failed. Ignoring this error.')
    logger.debug(f'top_hash = {top_hash}')
    logger.debug(f'Comparing current ebuild version {version} with live version {top_hash}')
    assert isinstance(use_vercmp, bool)
    if ((use_vercmp and (vercmp(top_hash, version, silent=0) or 0) > 0) or top_hash != version):
        if auto_update and cp not in settings.no_auto_update:
            ebuild = find_highest_match_ebuild_path(cp, search_dir)
            with open(ebuild) as f:
                old_content = f.read()
            content = old_content.replace(version, top_hash)
            ps_ref = top_hash
            if not is_sha(top_hash) and cp in TAG_NAME_FUNCTIONS:
                ps_ref = TAG_NAME_FUNCTIONS[cp](top_hash)
            content = process_submodules(cp, ps_ref, content, url)
            if update_sha_too_source:
                old_sha = get_old_sha(ebuild)
                new_sha = get_new_sha(update_sha_too_source)
                if old_sha != new_sha:
                    content = content.replace(old_sha, new_sha)
            dn = Path(ebuild).parent
            new_filename = f'{dn}/{pkg}-{top_hash}.ebuild'
            if is_sha(top_hash):
                updated_el = etree.fromstring(r.text).find('entry/updated', RSS_NS)
                assert updated_el is not None
                assert updated_el.text is not None
                if re.search(r'(2[0-9]{7})', ebuild_version):
                    new_date = updated_el.text.split('T')[0].replace('-', '')
                    new_filename = (f'{dn}/{pkg}-{re.sub(r"2[0-9]{7}", new_date, ebuild_version)}'
                                    '.ebuild')
            if ebuild == new_filename:
                name = Path(ebuild).stem
                ext = Path(ebuild).suffix
                new_filename = f'{name}-r1{ext}'
            print(f'{ebuild} -> {new_filename}')
            sp.run(('mv', ebuild, new_filename), check=True)
            with open(new_filename, 'w') as f:
                f.write(content)
            if cp in settings.yarn_base_packages:
                update_yarn_ebuild(new_filename, settings.yarn_base_packages[cp], pkg,
                                   settings.yarn_packages.get(cp))
            elif cp in settings.go_sum_uri:
                update_go_ebuild(new_filename, pkg, top_hash, settings.go_sum_uri[cp])
            elif cp in settings.dotnet_projects:
                update_dotnet_ebuild(new_filename, settings.dotnet_projects[cp], cp)
        else:
            new_date = ''
            if is_sha(top_hash):
                doc = etree.fromstring(r.text)
                updated_el = doc.find('entry/updated', RSS_NS)
                assert updated_el is not None
                assert updated_el.text is not None
                if m := re.search(r'^(2[0-9]{7})', ebuild_version):
                    new_date = (' (' + ebuild_version[:m.span()[0]] +
                                updated_el.text.split('T')[0].replace('-', '') + ')')
            sha_str = ''
            new_sha = ''
            if update_sha_too_source:
                ebuild = find_highest_match_ebuild_path(cp, search_dir)
                old_sha = get_old_sha(ebuild)
                sha_str = f' ({old_sha}) '
                logger.debug(f'Fetching {update_sha_too_source}')
                new_sha = f' ({get_new_sha(update_sha_too_source)})'
            ebv_str = (f' ({ebuild_version}) ' if ebuild_version != version else '')
            print(f'{cat}/{pkg}: {version}{ebv_str}{sha_str} -> '
                  f'{top_hash}{new_date}{new_sha}')


@click.command()
@click.option('-a', '--auto-update', is_flag=True, help='Rename and modify ebuilds.')
@click.option('-d', '--debug', is_flag=True, help='Enable debug logging.')
@click.option('-e', '--exclude', multiple=True, help='Exclude package(s) from updates.')
@click.option('-W',
              '--working-dir',
              default='.',
              help='Working directory. Should be a port tree root.',
              type=click.Path(file_okay=False,
                              exists=True,
                              resolve_path=True,
                              readable=True,
                              writable=True))
@click.argument('package_names', nargs=-1)
def main(
    auto_update: bool = False,
    debug: bool = False,
    exclude: tuple[str] | None = None,
    package_names: tuple[str] | list[str] | None = None,
    working_dir: str | None = '.',
) -> int:
    if working_dir and working_dir != '.':
        chdir(working_dir)
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    if exclude:
        logger.debug(f'Excluding {", ".join(exclude)}')
    search_dir = working_dir or '.'
    session = requests.Session()
    settings = gather_settings(search_dir)
    package_names = sorted(package_names or [])
    for cat, pkg, ebuild_version, version, url, regex, _use_vercmp in get_props(
            search_dir, settings, package_names, exclude):
        logger.debug(f'Fetching {url}')
        headers = {}
        parsed_uri = urlparse(url)
        if parsed_uri.hostname == 'api.github.com':
            logger.debug('Attempting to add authorization header')
            with contextlib.suppress(KeyError):
                headers['Authorization'] = f'token {get_github_api_credentials()}'
        if url.endswith('.atom'):
            logger.debug('Adding Accept header for XML')
            headers['Accept'] = 'application/xml'  # atom+xml does not work
        r: TextDataResponse | requests.Response  # only Mypy wants this
        try:
            r = (TextDataResponse(url[5:])
                 if url.startswith('data:') else session.get(url, headers=headers, timeout=30))
        except (ReadTimeout, ConnectTimeout, requests.exceptions.HTTPError,
                requests.exceptions.SSLError) as e:
            logger.debug(f'Caught error {e} attempting to fetch {url}')
            continue
        try:
            do_main(r=r,
                    cat=cat,
                    pkg=pkg,
                    url=url,
                    regex=regex,
                    search_dir=search_dir,
                    auto_update=auto_update,
                    settings=settings,
                    use_vercmp=_use_vercmp,
                    parsed_uri=parsed_uri,
                    ebuild_version=ebuild_version,
                    version=version)
        except (requests.exceptions.HTTPError, requests.exceptions.SSLError) as e:
            logger.warning(f'Caught error while checking {cat}/{pkg}: {e}')
        except Exception:
            print(f'Exception while checking {cat}/{pkg}', file=sys.stderr)
            raise
    return 0
