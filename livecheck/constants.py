"""Constants."""
from __future__ import annotations

from typing import TYPE_CHECKING

from .utils import prefix_v

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

__all__ = ('RSS_NS', 'SUBMODULES', 'TAG_NAME_FUNCTIONS')

RSS_NS = {'': 'http://www.w3.org/2005/Atom'}
"""
Namespace for RSS feeds.

:meta hide-value:
"""
SUBMODULES: Mapping[str, set[str | tuple[str, str]]] = {
    'app-misc/tasksh': {'src/libshared'},
    'app-pda/tsschecker': {'external/jssy'},
    'games-emulation/citra': {
        'externals/dynarmic',
        'externals/fmt',
        'externals/lodepng/lodepng',
        'externals/sirit',
        'externals/soundtouch',
        'externals/xbyak',
    },
    'games-emulation/play': {
        'deps/CodeGen',
        'deps/Dependencies',
        'deps/Framework',
        'deps/Nuanceur',
        'deps/libchdr',
    },
    'games-emulation/rpcs3': {
        '3rdparty/asmjit/asmjit',
        '3rdparty/hidapi/hidapi',
        '3rdparty/yaml-cpp/yaml-cpp',
        '3rdparty/SoundTouch/soundtouch',
        '3rdparty/llvm/llvm',
    },
    'games-emulation/sudachi': {
        'externals/SDL',
        'externals/cpp-httplib',
        'externals/cpp-jwt',
        'externals/dynarmic',
        'externals/ffmpeg/ffmpeg',
        'externals/mbedtls',
        'externals/simpleini',
        'externals/sirit',
        'externals/xbyak',
    },
    'games-emulation/vita3k': {
        'external/LibAtrac9',
        'external/SPIRV-Cross',
        'external/VulkanMemoryAllocator-Hpp',
        'external/better-enums',
        'external/crypto-algorithms',
        'external/dlmalloc',
        'external/dynarmic',
        'external/fmt',
        'external/imgui',
        'external/imgui_club',
        'external/libfat16',
        'external/printf',
        'external/spdlog',
        'external/stb',
        'external/unicorn',
        'external/vita-toolchain',
    },
    'games-emulation/yuzu': {
        'externals/SDL',
        'externals/cpp-jwt',
        'externals/dynarmic',
        'externals/mbedtls',
        'externals/sirit',
        ('externals/cpp-httplib', 'HTTPLIB_SHA'),
    },
    'media-sound/sony-headphones-client': {'Client/imgui'}
}
"""
Currently, submodule handling is hard-coded for specific packages.

:meta hide-value:
"""
TAG_NAME_FUNCTIONS: Mapping[str, Callable[[str], str]] = {
    'app-misc/tasksh': prefix_v,
    'games-emulation/rpcs3': prefix_v,
    'games-emulation/xemu': prefix_v,
    'games-emulation/yuzu': lambda x: f'mainline-{x.replace(".", "-")}',
    'media-sound/sony-headphones-client': prefix_v,
}
"""
Functions to prefix tag names for specific packages.

:meta hide-value:
"""
