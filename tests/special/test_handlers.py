from __future__ import annotations

from typing import TYPE_CHECKING

from livecheck.special.handlers import (
    handle_bsnes_hd,
    handle_cython_post_suffix,
    handle_glabels,
    handle_outfox,
    handle_outfox_serenity,
    handle_pl,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_handle_glabels_returns_modified_version_when_hash_date_present(
        mocker: MockerFixture) -> None:
    mock_get_latest = mocker.patch('livecheck.special.handlers.get_latest_github_commit2',
                                   return_value=('abcdef', '20240601'))
    handle_glabels.cache_clear()
    result = handle_glabels('some-ver')
    assert result == '3.99_p20240601'
    mock_get_latest.assert_called_once_with('jimevins', 'glabels-qt', 'master')


def test_handle_glabels_returns_input_when_hash_date_missing(mocker: MockerFixture) -> None:
    mock_get_latest = mocker.patch('livecheck.special.handlers.get_latest_github_commit2',
                                   return_value=('abcdef', None))
    handle_glabels.cache_clear()
    result = handle_glabels('orig-ver')
    assert result == 'orig-ver'
    mock_get_latest.assert_called_once_with('jimevins', 'glabels-qt', 'master')


def test_handle_cython_post_suffix_replaces_post_with_dot() -> None:
    input_version = '0.29.21.post1'
    result = handle_cython_post_suffix(input_version)
    assert result == '0.29.21.1'


def test_handle_cython_post_suffix_no_post() -> None:
    input_version = '0.29.21'
    result = handle_cython_post_suffix(input_version)
    assert result == '0.29.21'


def test_handle_cython_post_suffix_multiple_post() -> None:
    input_version = '1.0.post2.post3'
    result = handle_cython_post_suffix(input_version)
    assert result == '1.0.2.3'


def test_handle_outfox_with_pre_suffix() -> None:
    input_version = '0.4.18-pre0001'
    result = handle_outfox(input_version)
    assert result == '0.4.18_p1'


def test_handle_outfox_with_pre_suffix_multiple_zeros() -> None:
    input_version = '0.4.18-pre0000123'
    result = handle_outfox(input_version)
    assert result == '0.4.18_p123'


def test_handle_outfox_without_pre_suffix() -> None:
    input_version = '0.4.18'
    result = handle_outfox(input_version)
    assert result == '0.4.18'


def test_handle_outfox_with_pre_suffix_and_trailing_text() -> None:
    input_version = '0.4.18-pre0001-extra'
    result = handle_outfox(input_version)
    assert result == '0.4.18_p1-extra'


def test_handle_outfox_serenity_replaces_s_with_dot() -> None:
    input_version = '1s2s3'
    result = handle_outfox_serenity(input_version)
    assert result == '1.2.3'


def test_handle_outfox_serenity_no_s_in_input() -> None:
    input_version = '1.2.3'
    result = handle_outfox_serenity(input_version)
    assert result == '1.2.3'


def test_handle_outfox_serenity_multiple_consecutive_s() -> None:
    input_version = '1ss2'
    result = handle_outfox_serenity(input_version)
    assert result == '1..2'


def test_handle_outfox_serenity_s_at_start_and_end() -> None:
    input_version = 's1.2.3s'
    result = handle_outfox_serenity(input_version)
    assert result == '.1.2.3.'


def test_handle_outfox_serenity_empty_string() -> None:
    input_version = ''
    result = handle_outfox_serenity(input_version)
    assert not result


def test_handle_bsnes_hd_basic() -> None:
    # beta_115_10h2 -> 115.10_beta
    input_version = 'beta_115_10h2'
    result = handle_bsnes_hd(input_version)
    assert result == '115.10_beta'


def test_handle_bsnes_hd_no_h() -> None:
    # beta_2_3 -> 2.3_beta
    input_version = 'beta_2_3'
    result = handle_bsnes_hd(input_version)
    assert result == '2.3_beta'


def test_handle_bsnes_hd_multiple_h() -> None:
    # beta_5_12h3h4 -> 5.12_beta
    input_version = 'beta_5_12h3h4'
    result = handle_bsnes_hd(input_version)
    assert result == '5.12_beta'


def test_handle_bsnes_hd_minor_with_h() -> None:
    # beta_7_8h1 -> 7.8_beta
    input_version = 'beta_7_8h1'
    result = handle_bsnes_hd(input_version)
    assert result == '7.8_beta'


def test_handle_pl_basic() -> None:
    input_version = '1.2.3-pl4'
    result = handle_pl(input_version)
    assert result == '1.2.3.4'


def test_handle_pl_with_v_prefix() -> None:
    input_version = 'v2.5.7-pl10'
    result = handle_pl(input_version)
    assert result == '2.5.7.10'


def test_handle_pl_no_pl_suffix() -> None:
    input_version = '1.2.3'
    result = handle_pl(input_version)
    assert not result


def test_handle_pl_incorrect_format() -> None:
    input_version = '1.2-pl3'
    result = handle_pl(input_version)
    assert not result


def test_handle_pl_non_numeric_pl() -> None:
    input_version = '1.2.3-plx'
    result = handle_pl(input_version)
    assert not result
