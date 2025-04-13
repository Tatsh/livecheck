from livecheck.special.pypi import extract_project
import pytest

test_cases = [
    {
        'url': 'https://pypi.org/project/source/s/someproject/1.0.0/',
        'expected': 'someproject'
    },
    {
        'url': 'https://pypi.org/project/someproject-1.0.0/',
        'expected': ''
    },
    {
        'url':
            'https://files.pythonhosted.org/packages/source/s/someproject/someproject-1.0.0.tar.gz',
        'expected':
            'someproject'
    },
    {
        'url': 'https://pypi.io/packages/source/s/someproject/someproject-1.0.0.tar.gz',
        'expected': 'someproject'
    },
    {
        'url': 'https://example.com/project/someproject-1.0.0/',
        'expected': ''
    },
    {
        'url': 'https://pypi.org/project/someproject/',
        'expected': ''
    },
    {
        'url': 'https://pypi/project/source/s/someproject/1.0.0/',
        'expected': 'someproject'
    },
    {
        'url': 'https://pypi.io/project/source/s/someproject/1.0.0/',
        'expected': 'someproject'
    },
    {
        'url': 'https://1pypi.io/project/source/someproject/1.0.0/',
        'expected': ''
    },
    {
        'url': 'https://www.pythonhosted.org/project/source/someproject/1.0.0/',
        'expected': ''
    },
    {
        'url': 'mirror://pypi/project/source/s/someproject/1.0.0/',
        'expected': 'someproject'
    },
    {
        'url':
            'https://files.pythonhosted.org/packages/15/1f/ca74b65b19798895d63a6e92874162f44233467c9e7c1ed8afd19016ebe9/chevron-0.14.0.tar.gz',
        'expected':
            'chevron'
    },
]


@pytest.mark.parametrize('case', test_cases)
def test_extract_project(case: dict[str, str]) -> None:
    assert extract_project(case['url']) == case['expected']
