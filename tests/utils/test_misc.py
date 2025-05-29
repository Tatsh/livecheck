from __future__ import annotations

from typing import TYPE_CHECKING
import subprocess

from livecheck.utils.misc import check_program

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_check_program_success_no_version(mocker: MockerFixture) -> None:
    mock_run = mocker.patch('livecheck.utils.misc.sp.run')
    mock_run.return_value = mocker.Mock(stdout='Python 3.10.0\n')
    assert check_program('python', args=['--version']) is True
    mock_run.assert_called_once()


def test_check_program_success_with_version(mocker: MockerFixture) -> None:
    mock_run = mocker.patch('livecheck.utils.misc.sp.run')
    mock_run.return_value = mocker.Mock(stdout='Python 3.10.0\n')
    assert check_program('python', args=['--version'], min_version='3.9.0') is True


def test_check_program_version_too_low(mocker: MockerFixture) -> None:
    mock_run = mocker.patch('livecheck.utils.misc.sp.run')
    mock_run.return_value = mocker.Mock(stdout='Python 2.7.0\n')
    assert check_program('python', args=['--version'], min_version='3.0.0') is False


def test_check_program_version_not_found(mocker: MockerFixture) -> None:
    mock_run = mocker.patch('livecheck.utils.misc.sp.run')
    mock_run.return_value = mocker.Mock(stdout='no version info here\n')
    assert check_program('python', args=['--version'], min_version='3.0.0') is False


def test_check_program_run_raises_file_not_found(mocker: MockerFixture) -> None:
    mocker.patch('subprocess.run', side_effect=FileNotFoundError)
    assert check_program('not-real-cmd') is False


def test_check_program_run_raises_called_process_error(mocker: MockerFixture) -> None:
    mocker.patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'cmd'))
    assert check_program('failing-cmd') is False


def test_check_program_version_value_error(mocker: MockerFixture) -> None:
    mock_run = mocker.patch('livecheck.utils.misc.sp.run')
    mocker.patch('livecheck.utils.misc.re.search', side_effect=ValueError)
    mock_run.return_value = mocker.Mock(stdout='Python version: unknown\n')
    assert check_program('python', args=['--version'], min_version='3.0.0') is False


def test_check_program_args_none(mocker: MockerFixture) -> None:
    mock_run = mocker.patch('livecheck.utils.misc.sp.run')
    mock_run.return_value = mocker.Mock(stdout='Python 3.10.0\n')
    assert check_program('python', args=None) is True
