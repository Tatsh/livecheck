import pytest

from livecheck.utils.portage import remove_leading_zeros, sanitize_version


@pytest.mark.parametrize(("version", "expected"),
                         [(0, "0"), ("", ""), ("v1.2.3", "1.2.3"), ("s1.2.3", "1.2.3"),
                          ("1.2.3", "1.2.3"), ("1.2.3a", "1.2.3a"), ("1.2.3-alpha", "1.2.3_alpha"),
                          ("1.2.3-alpha0", "1.2.3_alpha"), ("1.2.3-beta1", "1.2.3_beta1"),
                          ("1.2.3-beta.1", "1.2.3_beta1"), ("1.2.3-rc2", "1.2.3_rc2"),
                          ("1.2.3_rc2", "1.2.3_rc2"), ("1.2.3 RC 2", "1.2.3_rc2"),
                          ("1.2.3-pre", "1.2.3_pre"), ("1.2.3-dev", "1.2.3_beta"),
                          ("1.2.3-test", "1.2.3_beta"), ("1.2.3_test", "1.2.3_beta"),
                          ("1.2.3_test 1", "1.2.3_beta1"), ("1.2.3p", "1.2.3_p"),
                          ("1.2.3-unknown", "1.2.3"), ("1.2.3-unknown1", "1.2.3"),
                          ("1.2.3-1", "1.2.3.1"), ("1.2.3_1", "1.2.3.1"), ("1.2.3 1", "1.2.3.1"),
                          ("1.2.3-rc", "1.2.3_rc"), ("1.2.3-rc-1", "1.2.3_rc1"),
                          ("2022.12.26 2022-12-26 19:55", "2022.12.26"),
                          ("2022_12_26 2022-12-26 19:55", "2022.12.26"),
                          ("2022-12-26 2022-12-26 19:55", "2022.12.26"),
                          ("dosbox 2022-12-26 2022-12-26 19:55", "2022.12.26"),
                          ("samba-4.19.7", "4.19.7"), ("test-190", "190"), ("test 190", "190"),
                          ("318.1", "318.1"), ("1.2.0.4068", "1.2.0.4068"),
                          ("v2015-09-29-license-adobe", "2015.9.29"),
                          ("dosbox-x-v2025.01.01", "2025.1.1"), ("v0.8.9p10", "0.8.9_p10"),
                          ("build_420", "420"), ("glabels", ""), ("NewBuild25rc1", "25_rc1"),
                          ("v1.12.post318", "1.12_p318"), ("1.002", "1.002"),
                          ("1.3.0-build.4", "1.3.0"), ("0.2.tar.gz", "0.2"),
                          ("0.8.1-pl5", "0.8.1_p5"), ("0.8 patchlevel   6", "0.8_p6"),
                          ("0.0.8b2", "0.0.8_beta2"), ("0.0.8a5", "0.0.8_alpha5"),
                          ("0.1.8b0", "0.1.8_beta")])
def test_sanitize_version(version: str, expected: str) -> None:
    assert sanitize_version(version) == expected


@pytest.mark.parametrize(("version", "expected"), [
    ("2022.01.06", "2022.1.6"),
    ("24.01.12", "24.1.12"),
    ("0.0.3", "0.0.3"),
    ("1.0.3-r1", "1.0.3-r1"),
    ("2022-12-26", "2022-12-26"),
    ("1.0.3", "1.0.3"),
    ("1.2", "1.2"),
    ("1", "1"),
    ("0.1.2", "0.1.2"),
    ("24.01.02", "24.1.2"),
])
def test_remove_leading_zeros(version: str, expected: str) -> None:
    assert remove_leading_zeros(version) == expected
