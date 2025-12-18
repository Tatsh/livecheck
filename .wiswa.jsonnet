local utils = import 'utils.libjsonnet';

{
  // Project-specific
  description: 'Tool to update ebuilds.',
  keywords: ['command line', 'ebuild', 'gentoo', 'portage'],
  project_name: 'livecheck',
  version: '0.1.4',
  want_main: true,
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
  copilot: {
    intro: 'Livecheck is a tool to update Portage ebuilds using upstream information.',
  },
  readthedocs+: {
    build+: {
      jobs+: {
        post_install+: [
          'VIRTUAL_ENV="$READTHEDOCS_VIRTUALENV_PATH" poetry run pip install git+https://github.com/gentoo/portage.git',
        ],
      },
    },
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
