"""Tests for ida_free module."""
from __future__ import annotations

from typing import TYPE_CHECKING

from livecheck.special.ida_free import get_latest_ida_free_package

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_get_latest_ida_free_package_success(mocker: MockerFixture) -> None:
    """Test successful retrieval of IDA Free version."""
    mock_response = mocker.Mock()
    mock_response.text = """
    <html>
        <body>
            <h1>IDA 9.3 Release Notes</h1>
            <p>IDA 9.2 was also released</p>
            <p>IDA 9.1 is older</p>
            <p>IDA 8.4 is even older</p>
        </body>
    </html>
    """
    mock_get_content = mocker.patch('livecheck.special.ida_free.get_content',
                                    return_value=mock_response)
    mock_settings = mocker.Mock()

    result = get_latest_ida_free_package('dev-util/ida-free-9.2', mock_settings)

    mock_get_content.assert_called_once_with('https://docs.hex-rays.com/release-notes/')
    assert result == '9.3'


def test_get_latest_ida_free_package_no_content(mocker: MockerFixture) -> None:
    """Test when content fetch fails."""
    mocker.patch('livecheck.special.ida_free.get_content', return_value=None)
    mock_settings = mocker.Mock()

    result = get_latest_ida_free_package('dev-util/ida-free-9.0', mock_settings)

    assert not result


def test_get_latest_ida_free_package_no_versions_found(mocker: MockerFixture) -> None:
    """Test when no version numbers are found in the response."""
    mock_response = mocker.Mock()
    mock_response.text = '<html><body>No versions here</body></html>'
    mocker.patch('livecheck.special.ida_free.get_content', return_value=mock_response)
    mock_settings = mocker.Mock()

    result = get_latest_ida_free_package('dev-util/ida-free-9.0', mock_settings)

    assert not result


def test_get_latest_ida_free_package_mixed_versions(mocker: MockerFixture) -> None:
    """Test with mixed major and minor version numbers."""
    mock_response = mocker.Mock()
    mock_response.text = """
    IDA 10.0 future version
    IDA 9.5 current
    IDA 9.3 older
    IDA 8.9 very old
    """
    mocker.patch('livecheck.special.ida_free.get_content', return_value=mock_response)
    mock_settings = mocker.Mock()

    result = get_latest_ida_free_package('dev-util/ida-free-9.0', mock_settings)

    assert result == '10.0'


def test_get_latest_ida_free_package_invalid_version_format(mocker: MockerFixture) -> None:
    """Test handling of invalid version formats."""
    mock_response = mocker.Mock()
    mock_response.text = """
    IDA 9.5 valid
    IDA invalid.version
    IDA 9.4 also valid
    """
    mocker.patch('livecheck.special.ida_free.get_content', return_value=mock_response)
    mock_settings = mocker.Mock()

    result = get_latest_ida_free_package('dev-util/ida-free-9.0', mock_settings)

    # Should get 9.5, ignoring the invalid format
    assert result == '9.5'
