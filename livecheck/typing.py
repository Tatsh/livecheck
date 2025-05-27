"""Typing helpers."""
from __future__ import annotations

import requests

from .utils import TextDataResponse

__all__ = ('PropTuple', 'Response')

PropTuple = tuple[str, str, str, str, str, str, str]
"""A tuple for properties category, PN, PV, last version, top hash, hash date, and URL."""
Response = TextDataResponse | requests.Response
"""Special response type."""
