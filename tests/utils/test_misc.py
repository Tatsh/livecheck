from __future__ import annotations

from typing import Any

from livecheck.utils.misc import check_program
import pytest

test_cases: dict[str, dict[str, Any]] = {
    'check_python': {
        'cmd': 'python',
        'args': ['--version'],
        'min_version': None,
        'expected': True,
    },
    'python_version': {
        'cmd': 'python',
        'args': ['--version'],
        'min_version': '1.0.0',
        'expected': True,
    },
    'python_version_max': {
        'cmd': 'python',
        'args': ['--version'],
        'min_version': '99999',
        'expected': False,
    },
    'check_poetry': {
        'cmd': 'poetry',
        'args': [''],
        'min_version': None,
        'expected': True,
    },
    'non_exist_program': {
        'cmd': 'non_exist_program',
        'args': [''],
        'min_version': None,
        'expected': False,
    },
    'non_exist_program_with_args': {
        'cmd': 'non_exist_program',
        'args': ['--version'],
        'min_version': None,
        'expected': False,
    },
    'false': {
        'cmd': 'false',
        'args': [''],
        'min_version': None,
        'expected': False,
    },
}


@pytest.mark.parametrize('test_case', test_cases.values(), ids=test_cases.keys())
def test_check_program(test_case: dict[str, Any]) -> None:
    assert check_program(cmd=test_case['cmd'],
                         args=test_case['args'],
                         min_version=test_case['min_version']) == test_case['expected']
