from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING
import hashlib

from livecheck.utils.requests import get_content, get_last_modified, hash_url, session_init
import requests

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_get_content_success_github(mocker: MockerFixture) -> None:
    url = 'https://api.github.com/repos/octocat/Hello-World'
    mock_session = mocker.Mock()
    mock_response = mocker.Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.text = 'data'
    mock_session.get.return_value = mock_response
    mocker.patch('livecheck.utils.requests.session_init', return_value=mock_session)
    r = get_content(url)
    assert r.status_code == HTTPStatus.OK
    assert r.text == 'data'
    mock_session.get.assert_called_once_with(url)


def test_get_content_success_gitlab(mocker: MockerFixture) -> None:
    url = 'https://api.gitlab.com/projects/123'
    mock_session = mocker.Mock()
    mock_response = mocker.Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.text = 'gitlab'
    mock_session.get.return_value = mock_response
    mocker.patch('livecheck.utils.requests.session_init', return_value=mock_session)
    r = get_content(url)
    assert r.status_code == HTTPStatus.OK
    assert r.text == 'gitlab'
    mock_session.get.assert_called_once_with(url)


def test_get_content_success_bitbucket(mocker: MockerFixture) -> None:
    url = 'https://api.bitbucket.org/2.0/repositories'
    mock_session = mocker.Mock()
    mock_response = mocker.Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.text = 'bitbucket'
    mock_session.get.return_value = mock_response
    mocker.patch('livecheck.utils.requests.session_init', return_value=mock_session)
    r = get_content(url)
    assert r.status_code == HTTPStatus.OK
    assert r.text == 'bitbucket'
    mock_session.get.assert_called_once_with(url)


def test_get_content_success_repology(mocker: MockerFixture) -> None:
    url = 'https://repology.org/api/v1/projects.json'
    mock_session = mocker.MagicMock()
    mock_response = mocker.Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.text = 'repology'
    mock_session.get.return_value = mock_response
    mocker.patch('livecheck.utils.requests.session_init', return_value=mock_session)
    r = get_content(url)
    assert r.status_code == HTTPStatus.OK
    assert r.text == 'repology'
    mock_session.get.assert_called_once_with(url)


def test_get_content_xml(mocker: MockerFixture) -> None:
    url = 'https://example.com/feed.xml'
    mock_session = mocker.Mock()
    mock_response = mocker.Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.text = '<xml></xml>'
    mock_session.get.return_value = mock_response
    mocker.patch('livecheck.utils.requests.session_init', return_value=mock_session)
    r = get_content(url)
    assert r.status_code == HTTPStatus.OK
    assert r.text == '<xml></xml>'
    mock_session.get.assert_called_once_with(url)


def test_get_content_json(mocker: MockerFixture) -> None:
    url = 'https://example.com/data.json'
    mock_session = mocker.Mock()
    mock_response = mocker.Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.text = '{"key": "value"}'
    mock_session.get.return_value = mock_response
    mocker.patch('livecheck.utils.requests.session_init', return_value=mock_session)
    r = get_content(url)
    assert r.status_code == HTTPStatus.OK
    assert r.text == '{"key": "value"}'
    mock_session.get.assert_called_once_with(url)


def test_get_content_mirror_scheme(mocker: MockerFixture) -> None:
    url = 'mirror://some/path'
    r = get_content(url)
    assert r.status_code == HTTPStatus.NOT_IMPLEMENTED


def test_get_content_request_exception(mocker: MockerFixture) -> None:
    url = 'https://example.com'
    mock_session = mocker.Mock()
    mock_session.get.side_effect = requests.RequestException
    mocker.patch('livecheck.utils.requests.session_init', return_value=mock_session)
    r = get_content(url)
    assert r.status_code == HTTPStatus.SERVICE_UNAVAILABLE


def test_get_content_non_ok_status(mocker: MockerFixture) -> None:
    url = 'https://example.com'
    mock_session = mocker.Mock()
    mock_response = mocker.Mock()
    mock_response.status_code = HTTPStatus.BAD_REQUEST
    mock_response.text = 'error'
    mock_session.get.return_value = mock_response
    mocker.patch('livecheck.utils.requests.session_init', return_value=mock_session)
    r = get_content(url)
    assert r.status_code == HTTPStatus.BAD_REQUEST


def test_get_content_empty_text_warns(mocker: MockerFixture) -> None:
    url = 'https://example.com'
    mock_session = mocker.Mock()
    mock_response = mocker.Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.text = ''
    mock_session.get.return_value = mock_response
    mocker.patch('livecheck.utils.requests.session_init', return_value=mock_session)
    r = get_content(url)
    assert r.status_code == HTTPStatus.OK
    assert not r.text


def test_session_init_github_sets_headers_and_token(mocker: MockerFixture) -> None:
    mock_session = mocker.MagicMock()
    mock_session.headers = {}
    mocker.patch('requests.Session', return_value=mock_session)
    mocker.patch('livecheck.utils.requests.get_api_credentials', return_value='gh-token')
    session = session_init('github')
    assert session == mock_session
    assert mock_session.headers['Authorization'] == 'Bearer gh-token'
    assert mock_session.headers['Accept'] == 'application/vnd.github.v3+json'
    assert mock_session.headers['timeout'] == '30'


def test_session_init_github_no_token(mocker: MockerFixture) -> None:
    mock_session = mocker.MagicMock()
    mock_session.headers = {}
    mocker.patch('requests.Session', return_value=mock_session)
    mocker.patch('livecheck.utils.requests.get_api_credentials', return_value=None)
    session_init.cache_clear()
    session = session_init('github')
    assert session == mock_session
    assert 'Authorization' not in mock_session.headers or not mock_session.headers['Authorization']
    assert mock_session.headers['Accept'] == 'application/vnd.github.v3+json'
    assert mock_session.headers['timeout'] == '30'


def test_session_init_gitlab_sets_headers_and_token(mocker: MockerFixture) -> None:
    mock_session = mocker.MagicMock()
    mock_session.headers = {}
    mocker.patch('requests.Session', return_value=mock_session)
    mocker.patch('livecheck.utils.requests.get_api_credentials', return_value='gl-token')
    session = session_init('gitlab')
    assert session == mock_session
    assert mock_session.headers['Authorization'] == 'Bearer gl-token'
    assert mock_session.headers['Accept'] == 'application/json'
    assert mock_session.headers['timeout'] == '30'


def test_session_init_bitbucket_sets_headers_and_token(mocker: MockerFixture) -> None:
    mock_session = mocker.MagicMock()
    mock_session.headers = {}
    mocker.patch('requests.Session', return_value=mock_session)
    mocker.patch('livecheck.utils.requests.get_api_credentials', return_value='bb-token')
    session = session_init('bitbucket')
    assert session == mock_session
    assert mock_session.headers['Authorization'] == 'Bearer bb-token'
    assert mock_session.headers['Accept'] == 'application/json'
    assert mock_session.headers['timeout'] == '30'


def test_session_init_xml_sets_accept_header(mocker: MockerFixture) -> None:
    mock_session = mocker.MagicMock()
    mock_session.headers = {}
    mocker.patch('requests.Session', return_value=mock_session)
    session = session_init('xml')
    assert session == mock_session
    assert mock_session.headers['Accept'] == 'application/xml'
    assert mock_session.headers['timeout'] == '30'


def test_session_init_json_sets_accept_header(mocker: MockerFixture) -> None:
    mock_session = mocker.MagicMock()
    mock_session.headers = {}
    mocker.patch('requests.Session', return_value=mock_session)
    session = session_init('json')
    assert session == mock_session
    assert mock_session.headers['Accept'] == 'application/json'
    assert mock_session.headers['timeout'] == '30'


def test_session_init_default(mocker: MockerFixture) -> None:
    mock_session = mocker.MagicMock()
    mock_session.headers = {}
    mocker.patch('requests.Session', return_value=mock_session)
    session = session_init('')
    assert session == mock_session
    assert mock_session.headers['timeout'] == '30'
    # Should not set Accept or Authorization
    assert 'Accept' not in mock_session.headers or not mock_session.headers['Accept']
    assert 'Authorization' not in mock_session.headers or not mock_session.headers['Authorization']


def test_session_init_gitlab_no_token(mocker: MockerFixture) -> None:
    mock_session = mocker.MagicMock()
    mock_session.headers = {}
    mocker.patch('requests.Session', return_value=mock_session)
    mocker.patch('livecheck.utils.requests.get_api_credentials', return_value=None)
    session_init.cache_clear()
    session = session_init('gitlab')
    assert session == mock_session
    assert 'Authorization' not in mock_session.headers or not mock_session.headers['Authorization']
    assert mock_session.headers['Accept'] == 'application/json'
    assert mock_session.headers['timeout'] == '30'


def test_session_init_bitbucket_no_token(mocker: MockerFixture) -> None:
    mock_session = mocker.MagicMock()
    mock_session.headers = {}
    mocker.patch('requests.Session', return_value=mock_session)
    mocker.patch('livecheck.utils.requests.get_api_credentials', return_value=None)
    session_init.cache_clear()
    session = session_init('bitbucket')
    assert session == mock_session
    assert 'Authorization' not in mock_session.headers or not mock_session.headers['Authorization']
    assert mock_session.headers['Accept'] == 'application/json'
    assert mock_session.headers['timeout'] == '30'


def test_hash_url_success(mocker: MockerFixture) -> None:
    url = 'https://example.com/file.txt'
    mock_response = mocker.MagicMock()
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = False
    mock_response.iter_content.return_value = [b'abc', b'def', b'']
    mock_response.raise_for_status.return_value = None
    mock_requests_get = mocker.patch('requests.get', return_value=mock_response)
    hash_url.cache_clear()
    h_blake2b, h_sha512, size = hash_url(url)
    expected_blake2b = hashlib.blake2b(b'abcdef').hexdigest()
    expected_sha512 = hashlib.sha512(b'abcdef').hexdigest()
    assert h_blake2b == expected_blake2b
    assert h_sha512 == expected_sha512
    assert size == 6
    mock_requests_get.assert_called_once_with(url, stream=True, timeout=30)


def test_hash_url_request_exception(mocker: MockerFixture) -> None:
    url = 'https://example.com/file.txt'
    mocker.patch('requests.get', side_effect=requests.RequestException)
    hash_url.cache_clear()
    h_blake2b, h_sha512, size = hash_url(url)
    assert not h_blake2b
    assert not h_sha512
    assert size == 0


def test_get_last_modified_success(mocker: MockerFixture) -> None:
    url = 'https://example.com/file.txt'
    mock_response = mocker.MagicMock()
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = False
    mock_response.raise_for_status.return_value = None
    mock_response.headers = {'last-modified': 'Wed, 21 Oct 2015 07:28:00 GMT'}
    mocker.patch('requests.head', return_value=mock_response)
    get_last_modified.cache_clear()
    result = get_last_modified(url)
    assert result == '20151021'


def test_get_last_modified_no_last_modified_header(mocker: MockerFixture) -> None:
    url = 'https://example.com/file.txt'
    mock_response = mocker.MagicMock()
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = False
    mock_response.raise_for_status.return_value = None
    mock_response.headers = {}
    mocker.patch('requests.head', return_value=mock_response)
    get_last_modified.cache_clear()
    result = get_last_modified(url)
    assert not result


def test_get_last_modified_request_exception(mocker: MockerFixture) -> None:
    url = 'https://example.com/file.txt'
    mocker.patch('requests.head', side_effect=requests.RequestException)
    get_last_modified.cache_clear()
    result = get_last_modified(url)
    assert not result
