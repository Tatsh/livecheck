from livecheck.main import replace_date_in_ebuild

CP = "sys-devel/gcc"


def test_replace_date_in_ebuild_full_date() -> None:
    ebuild = "20230101"
    new_date = "20240101"
    result = replace_date_in_ebuild(ebuild, new_date, CP)
    assert result == "20240101"


def test_replace_date_in_ebuild_short_date() -> None:
    ebuild = "1.2.2_p230101-r1"
    new_date = "20240101"
    result = replace_date_in_ebuild(ebuild, new_date, CP)
    assert result == "1.2.2_p240101"


def test_replace_date_in_ebuild_no_change() -> None:
    ebuild = "20230101-r1"
    new_date = "20230101"
    result = replace_date_in_ebuild(ebuild, new_date, CP)
    assert result == "20230101-r1"


def test_replace_date_in_ebuild_invalid_date() -> None:
    ebuild = "2023"
    new_date = "20240101"
    result = replace_date_in_ebuild(ebuild, new_date, CP)
    assert result == "2023"


def test_replace_date_in_ebuild_invalid_date2() -> None:
    ebuild = "12.0.1_p231124"
    new_date = "20240102"
    result = replace_date_in_ebuild(ebuild, new_date, CP)
    assert result == "12.0.1_p240102"


def test_replace_date_in_ebuild_invalid_date3() -> None:
    ebuild = "231124"
    new_date = "20240102"
    result = replace_date_in_ebuild(ebuild, new_date, CP)
    assert result == "240102"


def test_replace_date_in_ebuild_version_change() -> None:
    ebuild = "1.0.0_p20230101"
    new_date = "20240101"
    result = replace_date_in_ebuild(ebuild, new_date, CP)
    assert result == "1.0.0_p20240101"
