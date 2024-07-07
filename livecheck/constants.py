from collections.abc import Callable, Mapping
from typing import Final

from .utils import prefix_v

__all__ = ('GIST_HOSTNAMES', 'GITLAB_HOSTNAMES', 'PREFIX_RE', 'RSS_NS', 'SEMVER_RE', 'SUBMODULES',
           'TAG_NAME_FUNCTIONS')

GIST_HOSTNAMES = {'gist.github.com', 'gist.githubusercontent.com'}
GITLAB_HOSTNAMES = {'gitlab.com', 'gitlab.freedesktop.org', 'gitlab.gentoo.org'}
PREFIX_RE: Final[str] = r'(^[^0-9]+)[0-9]'
RSS_NS = {'': 'http://www.w3.org/2005/Atom'}
SEMVER_RE: Final[str] = (r'^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.'
                         r'(?P<patch>0|[1-9]\d*)(?:-(?P<prerelease>(?:0|[1-9]'
                         r'\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|'
                         r'\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+'
                         r'(?P<buildmetadata>[0-9a-zA-Z-]+'
                         r'(?:\.[0-9a-zA-Z-]+)*))?$')

SUBMODULES: Final[Mapping[str, set[str | tuple[str, str]]]] = {
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
    'games-emulation/xemu': {
        'genconfig',
        'hw/xbox/nv2a/thirdparty/nv2a_vsh_cpu',
        'tomlplusplus',
        'ui/thirdparty/httplib',
        'ui/thirdparty/imgui',
        'ui/thirdparty/implot',
        'ui/keycodemapdb',
        ('tests/fp/berkeley-softfloat-3', 'SOFTFLOAT_SHA'),
        ('tests/fp/berkeley-testfloat-3', 'TESTFLOAT_SHA'),
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
        # TODO Handle other externals in psvpfstools https://github.com/Vita3K/psvpfstools
    },
    'games-emulation/yuzu': {
        'externals/SDL',
        'externals/cpp-jwt',
        'externals/dynarmic',
        'externals/mbedtls',
        'externals/sirit',
        ('externals/cpp-httplib', 'HTTPLIB_SHA'),
    },
    'media-sound/sony-headphones-client': {'Client/imgui'},
}
TAG_NAME_FUNCTIONS: Final[Mapping[str, Callable[[str], str]]] = {
    'app-misc/tasksh': prefix_v,
    'games-emulation/rpcs3': prefix_v,
    'games-emulation/xemu': prefix_v,
    'games-emulation/yuzu': lambda x: f'mainline-{x.replace(".", "-")}',
    'media-sound/sony-headphones-client': prefix_v,
}
