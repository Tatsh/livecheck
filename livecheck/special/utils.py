from pathlib import Path

from xdg.BaseDirectory import save_cache_path

__all__ = ("get_project_path",)


def get_project_path(package_name: str) -> Path:
    return Path(save_cache_path(f"livecheck/{package_name}"))
