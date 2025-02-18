import pytest

from livecheck.special.gitlab import extract_domain_and_namespace


@pytest.mark.parametrize(
    ("url", "expected"),
    [("https://gitlab.com/group/project", ("gitlab.com", "group/project", "project")),
     ("https://notgitlab.com/group/project", ("", "", "")),
     ("https://gitlab.es/group/project", ("", "", "")),
     ("https://example.gitlab.com/group/project", ("", "", "")),
     ("https://gitlab.example.com/group/project",
      ("gitlab.example.com", "group/project", "project")),
     ("https://example.com/group/project", ("", "", "")),
     ("https://gitlab.com/group/project/-/merge_requests",
      ("gitlab.com", "group/project", "project")),
     ("https://gitlab.com/group/subgroup/project",
      ("gitlab.com", "group/subgroup/project", "project"))])
def test_extract_domain_and_namespace(url: str, expected: tuple[str, str, str]) -> None:
    assert extract_domain_and_namespace(url) == expected
