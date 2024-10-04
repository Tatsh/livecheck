import requests
import re

from loguru import logger

__all__ = ("get_latest_pecl_package",)


def get_last_filename(url: str) -> str:
    try:
        # Send a HEAD request to get the headers without downloading the file
        response = requests.head(url, allow_redirects=True)
        response.raise_for_status()

        # Check for the 'Content-Disposition' header
        content_disposition = response.headers.get('Content-Disposition')
        if content_disposition:
            # Extract the filename from the header using string parsing
            filename_part = [part for part in content_disposition.split(';') if 'filename=' in part]
            if filename_part:
                # Remove any extra characters like quotes
                filename = filename_part[0].split('=')[1].strip(' "')
                return filename
        return ''

    except requests.RequestException as e:
        logger.debug(f"Error accessing the URL: {e}")
        return ''


def get_latest_pecl_package(program_name: str) -> tuple[str, str]:
    # Remove 'pecl-' prefix if present
    if program_name.startswith('pecl-'):
        program_name = program_name.replace('pecl-', '', 1)

    # Construct the download URL for the package
    url = f'https://pecl.php.net/get/{program_name}'

    # Get the filename from the download URL
    filename = get_last_filename(url)
    if not filename:
        logger.debug(f"Could not determine the download filename for {program_name}.")
        return '', ''

    # Extract the version number from the filename using a regex
    match = re.search(rf'{re.escape(program_name)}-(\d+\.\d+(\.\d+)?)+', filename)
    if match:
        latest_version = match.group(1)
        return latest_version, url
    else:
        logger.debug(f"Could not extract version information from filename: {filename}")
        return '', ''
