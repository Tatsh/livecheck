from __future__ import annotations

from livecheck.utils.string import (
    InvalidPackageName,
    dash_to_underscore,
    dotize,
    extract_sha,
    is_sha,
    parse_npm_package_name,
    prefix_v,
)
import pytest


def test_parse_npm_package_name_scoped() -> None:
    result = parse_npm_package_name('@scope/pkg@1.2.3')
    assert result == ('@scope/pkg', '1.2.3', None)


def test_parse_npm_package_name_scoped_with_path() -> None:
    result = parse_npm_package_name('@scope/pkg@1.2.3/path/to/file')
    assert result == ('@scope/pkg', '1.2.3', '/path/to/file')


def test_parse_npm_package_name_scoped_no_version() -> None:
    result = parse_npm_package_name('@scope/pkg')
    assert result == ('@scope/pkg', None, None)


def test_parse_npm_package_name_non_scoped() -> None:
    result = parse_npm_package_name('pkg@2.0.0')
    assert result == ('pkg', '2.0.0', None)


def test_parse_npm_package_name_non_scoped_with_path() -> None:
    result = parse_npm_package_name('pkg@2.0.0/lib/index.js')
    assert result == ('pkg', '2.0.0', '/lib/index.js')


def test_parse_npm_package_name_non_scoped_no_version() -> None:
    result = parse_npm_package_name('pkg')
    assert result == ('pkg', None, None)


def test_parse_npm_package_name_invalid() -> None:
    with pytest.raises(InvalidPackageName):
        parse_npm_package_name('@invalid@@')


def test_prefix_v_simple() -> None:
    assert prefix_v('1.2.3') == 'v1.2.3'


def test_prefix_v_already_prefixed() -> None:
    # Should still prefix even if already starts with 'v'
    assert prefix_v('v2.0.0') == 'vv2.0.0'


def test_prefix_v_empty_string() -> None:
    assert prefix_v('') == 'v'


def test_prefix_v_numeric() -> None:
    assert prefix_v('123') == 'v123'


def test_prefix_v_with_leading_whitespace() -> None:
    assert prefix_v(' 1.0.0') == 'v 1.0.0'


def test_dash_to_underscore_basic() -> None:
    assert dash_to_underscore('foo-bar') == 'foo_bar'


def test_dash_to_underscore_multiple_dashes() -> None:
    assert dash_to_underscore('foo-bar-baz') == 'foo_bar_baz'


def test_dash_to_underscore_no_dashes() -> None:
    assert dash_to_underscore('foo') == 'foo'


def test_dash_to_underscore_only_dashes() -> None:
    assert dash_to_underscore('---') == '___'


def test_dash_to_underscore_empty_string() -> None:
    assert not dash_to_underscore('')


def test_dash_to_underscore_mixed_chars() -> None:
    assert dash_to_underscore('foo-bar_baz-qux') == 'foo_bar_baz_qux'


def test_dotize_basic() -> None:
    assert dotize('foo-bar') == 'foo.bar'


def test_dotize_underscore() -> None:
    assert dotize('foo_bar') == 'foo.bar'


def test_dotize_dash_and_underscore() -> None:
    assert dotize('foo-bar_baz') == 'foo.bar.baz'


def test_dotize_multiple_dashes_and_underscores() -> None:
    assert dotize('foo--bar__baz') == 'foo..bar..baz'


def test_dotize_no_special_chars() -> None:
    assert dotize('foo') == 'foo'


def test_dotize_only_dashes() -> None:
    assert dotize('---') == '...'


def test_dotize_only_underscores() -> None:
    assert dotize('___') == '...'


def test_dotize_empty_string() -> None:
    assert not dotize('')


def test_dotize_mixed_chars() -> None:
    assert dotize('-foo_bar-baz_') == '.foo.bar.baz.'


def test_dotize_already_dots() -> None:
    assert dotize('foo.bar') == 'foo.bar'


def test_extract_sha_40_char_sha() -> None:
    sha = 'a' * 40
    text = f'Commit hash: {sha} in the log.'
    assert extract_sha(text) == sha


def test_extract_sha_7_char_sha() -> None:
    sha = 'abcdef1'
    text = f'Short SHA: {sha} is here.'
    assert extract_sha(text) == sha


def test_extract_sha_prefers_first_sha() -> None:
    sha1 = 'abcdef1'
    sha2 = 'b' * 40
    text = f'First: {sha1}, then: {sha2}'
    assert extract_sha(text) == sha1


def test_extract_sha_no_sha() -> None:
    text = 'No hashes here!'
    assert not extract_sha(text)


def test_extract_sha_sha_embedded_in_word() -> None:
    # Should not match if not word-boundary
    sha = 'abcdef1'
    text = f'foo{sha}bar'
    assert not extract_sha(text)


def test_extract_sha_multiple_shas() -> None:
    sha1 = '1234567'
    sha2 = 'c' * 40
    text = f'{sha1} and {sha2}'
    assert extract_sha(text) == sha1


def test_extract_sha_sha_with_uppercase_letters() -> None:
    # Should not match uppercase, only lowercase hex
    sha = 'ABCDEF1'
    text = f'SHA: {sha}'
    assert not extract_sha(text)


def test_extract_sha_sha_with_mixed_case() -> None:
    sha = 'abcDEF1'
    text = f'SHA: {sha}'
    assert not extract_sha(text)


def test_extract_sha_sha_at_start_of_string() -> None:
    sha = '1234567'
    text = f'{sha} is at the start'
    assert extract_sha(text) == sha


def test_extract_sha_sha_at_end_of_string() -> None:
    sha = '1234567'
    text = f'Ends with {sha}'
    assert extract_sha(text) == sha


def test_extract_sha_sha_with_surrounding_punctuation() -> None:
    sha = 'abcdef1'
    text = f'({sha})'
    assert extract_sha(text) == sha


def test_is_sha_full_sha_in_url() -> None:
    sha = 'a' * 40
    url = f'https://example.com/commit/{sha}'
    assert is_sha(url) == 40


def test_is_sha_short_sha_in_url() -> None:
    sha = 'abcdef1'
    url = f'https://example.com/commit/{sha}'
    assert is_sha(url) == 7


def test_is_sha_no_sha_in_url() -> None:
    url = 'https://example.com/commit/notasha'
    assert is_sha(url) == 0


def test_is_sha_full_sha_as_string() -> None:
    sha = 'b' * 40
    assert is_sha(sha) == 40


def test_is_sha_short_sha_as_string() -> None:
    sha = '1234567'
    assert is_sha(sha) == 7


def test_is_sha_empty_string() -> None:
    assert is_sha('') == 0


def test_is_sha_sha_with_uppercase() -> None:
    sha = 'ABCDEF1'
    url = f'https://example.com/commit/{sha}'
    assert is_sha(url) == 0


def test_is_sha_sha_with_mixed_case() -> None:
    sha = 'abcDEF1'
    url = f'https://example.com/commit/{sha}'
    assert is_sha(url) == 0


def test_is_sha_sha_in_middle_of_url() -> None:
    sha = 'abcdef1'
    url = f'https://example.com/{sha}/commit'
    assert is_sha(url) == 0


def test_is_sha_sha_with_query_params() -> None:
    sha = '1234567'
    url = f'https://example.com/commit/{sha}?foo=bar'
    assert is_sha(url) == 7


def test_is_sha_sha_with_fragment() -> None:
    sha = '1234567'
    url = f'https://example.com/commit/{sha}#section'
    assert is_sha(url) == 7


def test_is_sha_sha_with_path_and_extra_slash() -> None:
    sha = 'abcdef1'
    url = f'https://example.com/commit/{sha}/'
    assert is_sha(url) == 0


def test_is_sha_non_hex_sha() -> None:
    sha = 'zzzzzzz'
    url = f'https://example.com/commit/{sha}'
    assert is_sha(url) == 0
