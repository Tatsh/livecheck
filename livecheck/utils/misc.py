"""Miscellaneous utility functions."""
from __future__ import annotations

from typing import TYPE_CHECKING
import re
import subprocess as sp

from packaging.version import Version

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ('check_program',)


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
