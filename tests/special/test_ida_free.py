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


def test_get_latest_ida_free_package_all_invalid_versions(mocker: MockerFixture) -> None:
    """Test when all version formats are invalid (non-numeric)."""
    mock_response = mocker.Mock()
    mock_response.text = """
    IDA alpha.beta
    IDA foo.bar
    IDA x.y
    """
    mocker.patch('livecheck.special.ida_free.get_content', return_value=mock_response)
    mock_settings = mocker.Mock()

    result = get_latest_ida_free_package('dev-util/ida-free-9.0', mock_settings)

    # Should return empty string when all versions are invalid
    assert not result


def test_get_latest_ida_free_package_three_part_versions(mocker: MockerFixture) -> None:
    """Test handling of three-part version numbers (not major.minor format)."""
    mock_response = mocker.Mock()
    mock_response.text = """
    IDA 9.5
    IDA 9.0.1
    IDA 8.4.2
    """
    mocker.patch('livecheck.special.ida_free.get_content', return_value=mock_response)
    mock_settings = mocker.Mock()

    result = get_latest_ida_free_package('dev-util/ida-free-9.0', mock_settings)

    # Should only consider 9.5 which has major.minor format
    # Three-part versions (9.0.1, 8.4.2) should be skipped (len(parts) != 2)
    assert result == '9.5'


def test_get_latest_ida_free_package_only_three_part_versions(mocker: MockerFixture) -> None:
    """Test when version strings have more than 2 parts after split."""
    mock_response = mocker.Mock()
    mock_response.text = 'IDA versions here'
    mocker.patch('livecheck.special.ida_free.get_content', return_value=mock_response)
    # Mock re.findall to return versions with 3 parts (simulating edge case)
    mocker.patch('livecheck.special.ida_free.re.findall', return_value=['9.0.1', '10.0.2'])
    mock_settings = mocker.Mock()

    result = get_latest_ida_free_package('dev-util/ida-free-9.0', mock_settings)

    # Should return empty string when no valid major.minor versions found
    # (all have 3 parts: len(parts) != 2)
    assert not result


def test_get_latest_ida_free_package_value_error_in_conversion(mocker: MockerFixture) -> None:
    """Test ValueError handling when version parts can't be converted to int."""
    mock_response = mocker.Mock()
    mock_response.text = 'IDA versions here'
    mocker.patch('livecheck.special.ida_free.get_content', return_value=mock_response)
    # Mock re.findall to return versions that will cause ValueError
    # Even though regex wouldn't match these, test the defensive code
    mocker.patch('livecheck.special.ida_free.re.findall', return_value=['alpha.beta', 'foo.bar'])
    mock_settings = mocker.Mock()

    result = get_latest_ida_free_package('dev-util/ida-free-9.0', mock_settings)

    # Should return empty string when all conversions fail
    assert not result
