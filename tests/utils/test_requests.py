from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING
import hashlib
import re

from livecheck.utils.requests import get_content, get_last_modified, hash_url, session_init
import niquests
import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from pytest_mock import MockerFixture
    from tests.conftest import NiquestsMocker


@pytest.mark.asyncio
async def test_get_content_success_github(requests_mock: NiquestsMocker,
                                          mocker: MockerFixture) -> None:
    mocker.patch('livecheck.utils.requests.get_api_credentials', return_value=None)
    url = 'https://api.github.com/repos/octocat/Hello-World'
    requests_mock.get(url, json={'name': 'Hello-World'}, status_code=HTTPStatus.OK)
    r = await get_content(url)
    assert r.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_get_content_success_gitlab(requests_mock: NiquestsMocker,
                                          mocker: MockerFixture) -> None:
    mocker.patch('livecheck.utils.requests.get_api_credentials', return_value=None)
    url = 'https://api.gitlab.com/projects/123'
    requests_mock.get(url, json={'id': 123}, status_code=HTTPStatus.OK)
    r = await get_content(url)
    assert r.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_get_content_success_bitbucket(requests_mock: NiquestsMocker,
                                             mocker: MockerFixture) -> None:
    mocker.patch('livecheck.utils.requests.get_api_credentials', return_value=None)
    url = 'https://api.bitbucket.org/2.0/repositories'
    requests_mock.get(url, json={'values': []}, status_code=HTTPStatus.OK)
    r = await get_content(url)
    assert r.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_get_content_success_repology(requests_mock: NiquestsMocker) -> None:
    url = 'https://repology.org/api/v1/projects.json'
    requests_mock.get(url, json={}, status_code=HTTPStatus.OK)
    r = await get_content(url)
    assert r.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_get_content_xml(requests_mock: NiquestsMocker) -> None:
    url = 'https://example.com/feed.xml'
    requests_mock.get(url, text='<xml></xml>', status_code=HTTPStatus.OK)
    r = await get_content(url)
    assert r.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_get_content_json(requests_mock: NiquestsMocker) -> None:
    url = 'https://example.com/data.json'
    requests_mock.get(url, json={'key': 'value'}, status_code=HTTPStatus.OK)
    r = await get_content(url)
    assert r.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_get_content_mirror_scheme(requests_mock: NiquestsMocker) -> None:
    url = 'mirror://some/path'
    r = await get_content(url)
    assert r.status_code == HTTPStatus.NOT_IMPLEMENTED


@pytest.mark.asyncio
async def test_get_content_non_ok_status(requests_mock: NiquestsMocker) -> None:
    url = 'https://example.com'
    requests_mock.get(url, status_code=HTTPStatus.BAD_REQUEST)
    r = await get_content(url)
    assert r.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.asyncio
async def test_get_content_empty_text_warns(requests_mock: NiquestsMocker) -> None:
    url = 'https://example.com'
    requests_mock.get(url, text='', status_code=HTTPStatus.OK)
    r = await get_content(url)
    assert r.status_code == HTTPStatus.OK


def test_session_init_github_sets_headers_and_token(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.utils.requests.get_api_credentials', return_value='gh-token')
    session = session_init('github')
    assert session.headers['Authorization'] == 'Bearer gh-token'
    assert session.headers['Accept'] == 'application/vnd.github.v3+json'
    assert session.headers['timeout'] == '30'


def test_session_init_github_no_token(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.utils.requests.get_api_credentials', return_value=None)
    session = session_init('github')
    assert 'Authorization' not in session.headers
    assert session.headers['Accept'] == 'application/vnd.github.v3+json'
    assert session.headers['timeout'] == '30'


def test_session_init_gitlab_sets_headers_and_token(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.utils.requests.get_api_credentials', return_value='gl-token')
    session = session_init('gitlab')
    assert session.headers['Authorization'] == 'Bearer gl-token'
    assert session.headers['Accept'] == 'application/json'
    assert session.headers['timeout'] == '30'


def test_session_init_bitbucket_sets_headers_and_token(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.utils.requests.get_api_credentials', return_value='bb-token')
    session = session_init('bitbucket')
    assert session.headers['Authorization'] == 'Bearer bb-token'
    assert session.headers['Accept'] == 'application/json'
    assert session.headers['timeout'] == '30'


def test_session_init_xml_sets_accept_header() -> None:
    session = session_init('xml')
    assert session.headers['Accept'] == 'application/xml'
    assert session.headers['timeout'] == '30'


def test_session_init_json_sets_accept_header() -> None:
    session = session_init('json')
    assert session.headers['Accept'] == 'application/json'
    assert session.headers['timeout'] == '30'


def test_session_init_default() -> None:
    session = session_init('')
    assert session.headers['timeout'] == '30'


def test_session_init_gitlab_no_token(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.utils.requests.get_api_credentials', return_value=None)
    session = session_init('gitlab')
    assert 'Authorization' not in session.headers
    assert session.headers['Accept'] == 'application/json'
    assert session.headers['timeout'] == '30'


def test_session_init_bitbucket_no_token(mocker: MockerFixture) -> None:
    mocker.patch('livecheck.utils.requests.get_api_credentials', return_value=None)
    session = session_init('bitbucket')
    assert 'Authorization' not in session.headers
    assert session.headers['Accept'] == 'application/json'
    assert session.headers['timeout'] == '30'


@pytest.mark.asyncio
async def test_hash_url_success(mocker: MockerFixture) -> None:
    url = 'https://example.com/file.txt'

    async def _iter_content(chunk_size: int = 8192) -> AsyncGenerator[bytes]:  # noqa: RUF029
        for chunk in (b'abc', b'def'):
            yield chunk

    mock_response = mocker.MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.iter_content = mocker.AsyncMock(return_value=_iter_content())
    mocker.patch.object(session_init(''), 'get', return_value=mock_response)
    h_blake2b, h_sha512, size = await hash_url(url)
    expected_blake2b = hashlib.blake2b(b'abcdef').hexdigest()
    expected_sha512 = hashlib.sha512(b'abcdef').hexdigest()
    assert h_blake2b == expected_blake2b
    assert h_sha512 == expected_sha512
    assert size == 6


@pytest.mark.asyncio
async def test_hash_url_request_exception(mocker: MockerFixture) -> None:
    url = 'https://example.com/file.txt'
    mocker.patch.object(session_init(''), 'get', side_effect=niquests.RequestException('fail'))
    h_blake2b, h_sha512, size = await hash_url(url)
    assert not h_blake2b
    assert not h_sha512
    assert size == 0


@pytest.mark.asyncio
async def test_hash_url_with_headers_and_params(mocker: MockerFixture) -> None:
    url = 'https://example.com/file.txt'

    async def _iter_content(chunk_size: int = 8192) -> AsyncGenerator[bytes]:  # noqa: RUF029
        for chunk in (b'abc',):
            yield chunk

    mock_response = mocker.MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.iter_content = mocker.AsyncMock(return_value=_iter_content())
    mocker.patch.object(session_init(''), 'get', return_value=mock_response)
    h_blake2b, h_sha512, size = await hash_url(url,
                                               headers={'Referer': 'https://example.com'},
                                               params={'key': 'value'})
    expected_blake2b = hashlib.blake2b(b'abc').hexdigest()
    expected_sha512 = hashlib.sha512(b'abc').hexdigest()
    assert h_blake2b == expected_blake2b
    assert h_sha512 == expected_sha512
    assert size == 3


@pytest.mark.asyncio
async def test_get_last_modified_success(requests_mock: NiquestsMocker) -> None:
    url = 'https://example.com/file.txt'
    requests_mock.head(url,
                       headers={'last-modified': 'Wed, 21 Oct 2015 07:28:00 GMT'},
                       status_code=HTTPStatus.OK)
    result = await get_last_modified(url)
    assert result == '20151021'


@pytest.mark.asyncio
async def test_get_last_modified_no_last_modified_header(requests_mock: NiquestsMocker) -> None:
    url = 'https://example.com/file.txt'
    requests_mock.head(url, status_code=HTTPStatus.OK)
    result = await get_last_modified(url)
    assert not result


@pytest.mark.asyncio
async def test_get_last_modified_request_exception(mocker: MockerFixture) -> None:
    url = 'https://example.com/file.txt'
    mocker.patch.object(session_init(''), 'head', side_effect=niquests.RequestException('fail'))
    result = await get_last_modified(url)
    assert not result


@pytest.mark.asyncio
async def test_get_last_modified_with_headers_and_params(requests_mock: NiquestsMocker) -> None:
    url = 'https://example.com/file.txt'
    requests_mock.head(re.compile(r'https://example\.com/file\.txt'),
                       headers={'last-modified': 'Wed, 21 Oct 2015 07:28:00 GMT'},
                       status_code=HTTPStatus.OK)
    result = await get_last_modified(url,
                                     headers={'Referer': 'https://example.com'},
                                     params={'key': 'value'})
    assert result == '20151021'


@pytest.mark.asyncio
async def test_get_content_with_custom_headers(requests_mock: NiquestsMocker) -> None:
    url = 'https://example.com'
    requests_mock.get(url, text='data', status_code=HTTPStatus.OK)
    r = await get_content(url, headers={'Referer': 'https://example.com/ref'})
    assert r.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_get_content_with_params(requests_mock: NiquestsMocker) -> None:
    url = 'https://example.com'
    requests_mock.get(re.compile(r'https://example\.com'), text='data', status_code=HTTPStatus.OK)
    r = await get_content(url, params={'file': 'security', 'agree': 'Yes'})
    assert r.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_get_content_with_post_method_and_data(requests_mock: NiquestsMocker) -> None:
    url = 'https://example.com'
    requests_mock.post(url, text='data', status_code=HTTPStatus.OK)
    r = await get_content(url, data={'countryCode': '', 'productName': 'test'}, method='POST')
    assert r.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_get_content_with_allow_redirects_false(requests_mock: NiquestsMocker) -> None:
    url = 'https://example.com'
    requests_mock.get(url, status_code=HTTPStatus.MOVED_PERMANENTLY)
    r = await get_content(url, allow_redirects=False)
    assert r.status_code == HTTPStatus.MOVED_PERMANENTLY


def test_session_init_raises_when_not_initialised(mocker: MockerFixture) -> None:
    import livecheck.utils.requests as req_mod
    mocker.patch.object(req_mod, '_semaphore', None)
    mocker.patch.object(req_mod, '_sessions', {})
    with pytest.raises(RuntimeError, match='Call init_sessions'):
        session_init('test-module-never-cached')


@pytest.mark.asyncio
async def test_hash_url_raise_for_status_exception(mocker: MockerFixture) -> None:
    url = 'https://example.com/file.txt'
    mock_response = mocker.MagicMock()
    mock_response.raise_for_status.side_effect = niquests.RequestException('bad status')
    mocker.patch.object(session_init(''), 'get', return_value=mock_response)
    h_blake2b, h_sha512, size = await hash_url(url)
    assert not h_blake2b
    assert not h_sha512
    assert size == 0


@pytest.mark.asyncio
async def test_get_content_request_exception(mocker: MockerFixture) -> None:
    url = 'https://example.com/fail'
    mocker.patch.object(session_init(''), 'send', side_effect=niquests.RequestException('fail'))
    r = await get_content(url)
    assert r.status_code == HTTPStatus.SERVICE_UNAVAILABLE


@pytest.mark.asyncio
async def test_hash_url_skips_empty_chunks(mocker: MockerFixture) -> None:
    url = 'https://example.com/file.txt'

    async def _iter_content(chunk_size: int = 8192) -> AsyncGenerator[bytes]:  # noqa: RUF029
        for chunk in (b'abc', b'', b'def'):
            yield chunk

    mock_response = mocker.MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.iter_content = mocker.AsyncMock(return_value=_iter_content())
    mocker.patch.object(session_init(''), 'get', return_value=mock_response)
    h_blake2b, h_sha512, size = await hash_url(url)
    expected_blake2b = hashlib.blake2b(b'abcdef').hexdigest()
    expected_sha512 = hashlib.sha512(b'abcdef').hexdigest()
    assert h_blake2b == expected_blake2b
    assert h_sha512 == expected_sha512
    assert size == 6


@pytest.mark.asyncio
async def test_get_content_atom_url(requests_mock: NiquestsMocker) -> None:
    url = 'https://example.com/feed.atom'
    requests_mock.get(url, text='<feed></feed>', status_code=HTTPStatus.OK)
    r = await get_content(url)
    assert r.status_code == HTTPStatus.OK
