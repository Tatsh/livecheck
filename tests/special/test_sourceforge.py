from livecheck.special.sourceforge import extract_repository


def test_extract_repository_with_downloads_sourceforge_net() -> None:
    url = "https://downloads.sourceforge.net/project/sample_project"
    assert extract_repository(url) == "sample_project"


def test_extract_repository_with_download_sourceforge_net() -> None:
    url = "https://download.sourceforge.net/project/sample_project"
    assert extract_repository(url) == "sample_project"


def test_extract_repository_with_sf_net() -> None:
    url = "https://sf.net/projects/sample_project"
    assert extract_repository(url) == "sample_project"


def test_extract_repository_with_sourceforge_net() -> None:
    url = "https://sample_project.sourceforge.net"
    assert extract_repository(url) == "sample_project"


def test_extract_repository_with_sourceforge_io() -> None:
    url = "https://sample_project.sourceforge.io"
    assert extract_repository(url) == "sample_project"


def test_extract_repository_with_sourceforge_jp() -> None:
    url = "https://sample_project.sourceforge.jp"
    assert extract_repository(url) == "sample_project"


def test_extract_repository_with_invalid_url() -> None:
    url = "https://example.com/sample_project"
    assert extract_repository(url) == ""


def test_extract_repository_with_empty_url() -> None:
    url = ""
    assert extract_repository(url) == ""


def test_extract_repository_with_sf_net2() -> None:
    url = "https://sf.net/projectss/sample_project"
    assert extract_repository(url) == "sample_project"


def test_extract_repository_with_download_sourceforge_net2() -> None:
    url = "https://ssourceforge.net/project/sample_project"
    assert extract_repository(url) == ""
