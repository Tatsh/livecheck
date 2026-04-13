local utils = import 'utils.libjsonnet';

{
  uses_user_defaults: true,
  // Project-specific
  description: 'Tool to update ebuilds.',
  keywords: ['command line', 'ebuild', 'gentoo', 'portage'],
  project_name: 'livecheck',
  version: '0.1.4',
  want_main: true,
  want_flatpak: true,
  publishing+: { flathub: 'sh.tat.livecheck' },
  gitignore+: [
    '.history',
    '.idea',
  ],
  supported_platforms: 'linux',
  pyproject+: {
    tool+: {
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
          beautifulsoup4: utils.latestPypiPackageVersionCaret('beautifulsoup4'),
          defusedxml: utils.latestPypiPackageVersionCaret('defusedxml'),
          html5lib: utils.latestPypiPackageVersionCaret('html5lib'),
          keyring: utils.latestPypiPackageVersionCaret('keyring'),
          portage: utils.latestPypiPackageVersionCaret('portage'),
          platformdirs: utils.latestPypiPackageVersionCaret('platformdirs'),
          requests: utils.latestPypiPackageVersionCaret('requests'),
        },
        group+: {
          dev+: {
            dependencies+: {
              'portage-stubs': '^0',
              'types-beautifulsoup4': utils.latestPypiPackageVersionCaret('types-beautifulsoup4'),
              'types-defusedxml': utils.latestPypiPackageVersionCaret('types-defusedxml'),
              'types-requests': utils.latestPypiPackageVersionCaret('types-requests'),
            },
          },
        },
      },
    },
  },
  security_policy_supported_versions: { '0.1.x': ':white_check_mark:' },
  readthedocs+: {
    sphinx+: {
      fail_on_warning: false,
    },
  },
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
