"""Configuration for Pytest."""
import pytest
from livecheck.utils.portage import sanitize_version


def test_sanitize_version() -> None:
    # Test cases for normalize_version function
    # fmt: off
    test_cases = [
        ("v1.2.3", "1.2.3"),
        ("s1.2.3", "1.2.3"),
        ("1.2.3", "1.2.3"),
        ("1.2.3a", "1.2.3a"),
        ("1.2.3-alpha", "1.2.3_alpha"),
        ("1.2.3-alpha0", "1.2.3_alpha"),
        ("1.2.3-beta1", "1.2.3_beta1"),
        ("1.2.3-beta.1", "1.2.3_beta1"),
        ("1.2.3-rc2", "1.2.3_rc2"),
        ("1.2.3_rc2", "1.2.3_rc2"),
        ("1.2.3 RC 2", "1.2.3_rc2"),
        ("1.2.3-pre", "1.2.3_pre"),
        ("1.2.3-dev", "1.2.3_beta"),
        ("1.2.3-test", "1.2.3_beta"),
        ("1.2.3_test", "1.2.3_beta"),
        ("1.2.3_test 1", "1.2.3_beta1"),
        ("1.2.3p", "1.2.3_p"),
        ("1.2.3-unknown", "1.2.3"),
        ("1.2.3-unknown1", "1.2.3"),
        ("1.2.3-1", "1.2.3.1"),
        ("1.2.3_1", "1.2.3.1"),
        ("1.2.3 1", "1.2.3.1"),
        ("1.2.3-rc", "1.2.3_rc"),
        ("1.2.3-rc-1", "1.2.3_rc1"),
        ("2022.12.26 2022-12-26 19:55", "2022.12.26"),
        ("2022_12_26 2022-12-26 19:55", "2022.12.26"),
        ("2022-12-26 2022-12-26 19:55", "2022.12.26"),
        ("dosbox 2022-12-26 2022-12-26 19:55", "2022.12.26"),
        ("samba-4.19.7", "4.19.7"),
        ("test-190", "190"),
        ("test 190", "190"),
        ("318.1", "318.1"),
        ("1.2.0.4068", "1.2.0.4068"),
        ("v2015-09-29-license-adobe", "2015.9.29"),
        ("dosbox-x-v2025.01.01", "2025.1.1"),
        ("v0.8.9p10", "0.8.9_p10"),
        ("build_420", "420"),
        ("glabels", ""),
        ("NewBuild25rc1", "25_rc1"),
        ("v1.12.post318", "1.12_p318")
    ]
    # fmt: on

    for ver, expected in test_cases:
        assert sanitize_version(ver) == expected
