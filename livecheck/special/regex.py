from urllib.parse import urlparse
from datetime import UTC, datetime
import contextlib
import re
import xml.etree.ElementTree as etree
from requests import ConnectTimeout, ReadTimeout
import requests

from loguru import logger

from ..constants import (RSS_NS, SEMVER_RE)

from ..settings import LivecheckSettings
from ..utils import (TextDataResponse, get_github_api_credentials, is_sha)
from ..utils.portage import is_version_development

__all__ = ('get_latest_regex_package',)


def get_latest_regex_package(ebuild_version: str,
                             cp: str,
                             settings: LivecheckSettings,
                             url: str,
                             regex: str,
                             version: str = '',
                             development: bool = False) -> tuple[str, str, str]:
    parsed_uri = urlparse(url)
    logger.debug(f'Fetching {url}')
    headers = {}
    session = requests.Session()
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
            requests.exceptions.SSLError, requests.exceptions.ConnectionError,
            requests.exceptions.MissingSchema) as e:
        logger.debug(f'Caught error {e} attempting to fetch {url}')
        return '', '', ''
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
    if len(results) == 0:
        return '', '', ''
    top_hash = ''
    for result in results:
        if not is_version_development(result) or development:
            top_hash = result
            break
    if not top_hash:
        logger.debug('No updated hash found')
        return '', '', ''
    logger.debug(f're.findall() -> "{top_hash}"')
    hash_date = ''
    if is_sha(top_hash):
        r.raise_for_status()
        try:
            updated_el = etree.fromstring(r.text).find('entry/updated', RSS_NS)
            assert updated_el is not None
            assert updated_el.text is not None
            if re.search(r'(2[0-9]{7})', ebuild_version):
                hash_date = updated_el.text.split('T')[0].replace('-', '')
                logger.debug(f'Use updated date {hash_date} for commit {top_hash}')
        except etree.ParseError:
            logger.error(f'Error parsing {url}')
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
    return top_hash, hash_date, url
