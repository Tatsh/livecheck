"""Github Gist functions."""
from __future__ import annotations

from datetime import datetime
import re

from livecheck.utils import get_content

__all__ = ('get_latest_gist_package', 'is_gist')

GIST_COMMIT_URL = 'https://api.github.com/gists/%s'


def extract_id(url: str) -> str:
    m = re.search(r'https?://gist\.github\.com/(?:[^/]+/)?([a-f0-9]+)', url)
    if not m:
        m = re.search(r'https?://gist\.githubusercontent\.com/[^/]+/([a-f0-9]+)/', url)
    return m.group(1) if m else ''


def get_latest_gist_package(url: str) -> tuple[str, str]:
    """Get the latest version of a Gist."""
    if not (gist_id := extract_id(url)):
        return '', ''

    url = GIST_COMMIT_URL % (gist_id)
    if not (r := get_content(url)):
        return '', ''

    history = r.json().get('history', [])
    if not history:
        return '', ''
    latest = max(history, key=lambda x: x.get('committed_at', ''))

    d = latest.get('committed_at')
    try:
        dt = datetime.fromisoformat(d.replace('Z', '+00:00'))
        formatted_date = dt.strftime('%Y%m%d')
    except ValueError:
        formatted_date = d[:10]

    return latest.get('version'), formatted_date


def is_gist(url: str) -> bool:
    """Check if the URL is to a Gist."""
    return bool(extract_id(url))
