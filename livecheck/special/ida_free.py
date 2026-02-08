"""IDA Free functions."""
from __future__ import annotations

from typing import TYPE_CHECKING
import logging
import re

from livecheck.utils import get_content

if TYPE_CHECKING:
    from livecheck.settings import LivecheckSettings

__all__ = ('get_latest_ida_free_package',)

IDA_RELEASE_NOTES_URL = 'https://docs.hex-rays.com/release-notes/'
logger = logging.getLogger(__name__)


def get_latest_ida_free_package(_ebuild: str, _settings: LivecheckSettings) -> str:
    """
    Get the latest version of IDA Free.

    Checks the release notes page for the latest major.minor version.
    """
    if not (r := get_content(IDA_RELEASE_NOTES_URL)):
        logger.debug('Failed to fetch IDA release notes')
        return ''

    # Extract all "IDA X.Y" version mentions from the page
    versions = re.findall(r'IDA (\d+\.\d+)', r.text)
    if not versions:
        logger.debug('No IDA versions found in release notes.')
        return ''

    # Convert to comparable tuples and find the max.
    version_tuples = []
    for v in versions:
        parts = v.split('.')
        if len(parts) == 2:  # noqa: PLR2004
            try:
                major, minor = int(parts[0]), int(parts[1])
                version_tuples.append((major, minor, v))
            except ValueError:
                pass

    if not version_tuples:
        return ''

    # Sort and get the latest
    version_tuples.sort(reverse=True)
    latest_version: str = version_tuples[0][2]

    logger.debug('Latest IDA version found: `%s`.', latest_version)
    return latest_version
