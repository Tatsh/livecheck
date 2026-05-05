local utils = import 'utils.libjsonnet';

{
  uses_user_defaults: true,
  // Project-specific
  description: 'Tool to update ebuilds.',
  keywords: ['command line', 'ebuild', 'gentoo', 'portage'],
  project_name: 'livecheck',
  version: '0.2.2',
  want_main: true,
  want_flatpak: false,
  want_snap: false,
  gitignore+: [
    '.history',
    '.idea',
  ],
  supported_platforms: 'linux',
  pyproject+: {
    tool+: {
      pytest+: {
        ini_options+: {
          asyncio_mode: 'auto',
        },
      },
      coverage+: {
        report+: {
          omit+: [
            'tests/special/test_*.py',
            'tests/utils/test_*.py',
            'typing.py',
          ],
        },
        run+: {
          omit+: ['tests/special/test_*.py', 'tests/utils/test_*.py', 'typing.py'],
        },
      },
      poetry+: {
        dependencies+: {
          anyio: utils.latestPypiPackageVersionCaret('anyio'),
          beautifulsoup4: utils.latestPypiPackageVersionCaret('beautifulsoup4'),
          defusedxml: utils.latestPypiPackageVersionCaret('defusedxml'),
          html5lib: utils.latestPypiPackageVersionCaret('html5lib'),
          keyring: utils.latestPypiPackageVersionCaret('keyring'),
          niquests: utils.latestPypiPackageVersionCaret('niquests'),
          'niquests-cache': utils.latestPypiPackageVersionCaret('niquests-cache'),
          platformdirs: utils.latestPypiPackageVersionCaret('platformdirs'),
          portage: utils.latestPypiPackageVersionCaret('portage'),
        },
        group+: {
          dev+: {
            dependencies+: {
              'portage-stubs': utils.latestPypiPackageVersionCaret('portage-stubs'),
              'types-beautifulsoup4': utils.latestPypiPackageVersionCaret('types-beautifulsoup4'),
              'types-defusedxml': utils.latestPypiPackageVersionCaret('types-defusedxml'),
            },
          },
          tests+: {
            dependencies+: {
              'niquests-mock': utils.latestPypiPackageVersionCaret('niquests-mock'),
              'pytest-asyncio': utils.latestPypiPackageVersionCaret('pytest-asyncio'),
            },
          },
        },
      },
      uv+: {
        'exclude-newer-package': {
          'niquests-cache': false,
          'niquests-mock': false,
          'portage-stubs': false,
        },
      },
    },
  },
  security_policy_supported_versions: { '0.2.x': ':white_check_mark:' },
  sphinx_fail_on_warning: false,
  // Common
  authors+: [
    {
      'family-names': 'Javier',
      'given-names': 'Francisco',
      email: 'web@inode64.com',
      name: '%s %s' % [self['given-names'], self['family-names']],
    },
  ],
}
