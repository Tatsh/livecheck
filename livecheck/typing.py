"""Typing helpers."""
import requests

from .utils import TextDataResponse

__all__ = ('PropTuple', 'Response')

PropTuple = tuple[str, str, str, str, str, str]
Response = TextDataResponse | requests.Response
