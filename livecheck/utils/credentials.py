from functools import cache
import logging

import keyring

log = logging.getLogger(__name__)


@cache
def get_api_credentials(repo: str) -> str | None:
    if not (token := keyring.get_password(repo, 'livecheck')):
        log.warning('No %s API token found in your secret store.')
    return token
