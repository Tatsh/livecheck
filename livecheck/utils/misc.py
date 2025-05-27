from collections.abc import Iterable
import logging
import logging.config
import re
import subprocess as sp

from packaging.version import Version


def check_program(cmd: str,
                  args: Iterable[str] | None = None,
                  min_version: str | None = None) -> bool:
    """
    Check if a program is installed.

    Optionally check if the installed version is at least the specified minimum version.

    Parameters
    ----------
    cmd : str
        The command to check.
    args : str
        The arguments to pass to the command.
    min_version : str | None
        The minimum version required. If ``None``, only checks if the program is installed.

    Returns
    -------
    bool
        ``True`` if the program is installed and the version is at least the minimum version.
    """
    try:
        result = sp.run((cmd, *(args or [])), capture_output=True, text=True, check=True)
    except (sp.CalledProcessError, FileNotFoundError):
        return False
    try:
        if min_version:
            v = re.search(r'\d+(\.\d+)+', result.stdout.strip())
            if not v:
                return False
            if Version(v.group(0)) < Version(min_version):
                return False
    except ValueError:
        return False

    return True


def setup_logging(*,
                  debug: bool = False,
                  force_color: bool = False,
                  no_color: bool = False) -> None:  # pragma: no cover
    """Set up logging configuration."""
    logging.config.dictConfig({
        'disable_existing_loggers': True,
        'root': {
            'level': 'DEBUG' if debug else 'INFO',
            'handlers': ['console'],
        },
        'formatters': {
            'default': {
                '()': 'colorlog.ColoredFormatter',
                'force_color': force_color,
                'format': (
                    '%(light_cyan)s%(asctime)s%(reset)s | %(log_color)s%(levelname)-8s%(reset)s | '
                    '%(light_green)s%(name)s%(reset)s:%(light_red)s%(funcName)s%(reset)s:'
                    '%(blue)s%(lineno)d%(reset)s - %(message)s'),
                'no_color': no_color,
            },
            'simple': {
                'format': '%(message)s',
            }
        },
        'handlers': {
            'console': {
                'class': 'colorlog.StreamHandler',
                'formatter': 'default' if debug else 'simple',
            }
        },
        'loggers': {
            'livecheck': {
                'level': 'INFO' if not debug else 'DEBUG',
                'handlers': ('console',),
                'propagate': False,
            },
            'urllib3': {
                'level': 'ERROR' if not debug else 'DEBUG',
                'handlers': ('console',),
                'propagate': False,
            },
        },
        'version': 1
    })
