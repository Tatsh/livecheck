local utils = import 'utils.libjsonnet';

(import 'defaults.libjsonnet') + {
  // Project-specific
  description: 'Tool to update ebuilds.',
  keywords: ['command line', 'ebuild', 'gentoo', 'portage'],
  project_name: 'livecheck',
  version: '0.0.13',
  want_main: true,
  citation+: {
    'date-released': '2025-04-13',
  },
  codeowners: {
    '*.lock': '@Tatsh',
    '*.md': '@Tatsh',
    '.*': '@Tatsh',
    'LICENSE.txt': '@Tatsh',
    '_config.yml': '@Tatsh',
    'docs/*': '@Tatsh',
    'livecheck/__init__.py': '@Tatsh @inode64',
    'livecheck/__main__.py': '@Tatsh',
    'livecheck/constants.py': '@Tatsh @inode64',
    'livecheck/settings.py': '@Tatsh @inode64',
    'livecheck/special/bitbucket.py': '@inode64',
    'livecheck/special/checksum.py': '@Tatsh',
    'livecheck/special/composer.py': '@inode64',
    'livecheck/special/davinci.py': '@inode64',
    'livecheck/special/directory.py': '@inode64',
    'livecheck/special/dotnet.py': '@Tatsh',
    'livecheck/special/github.py': '@Tatsh @inode64',
    'livecheck/special/gitlab.py': '@Tatsh @inode64',
    'livecheck/special/golang.py': '@Tatsh',
    'livecheck/special/gomodule.py': '@inode64',
    'livecheck/special/handlers.py': '@Tatsh @inode64',
    'livecheck/special/jetbrains.py': '@inode64',
    'livecheck/special/metacpan.py': '@inode64',
    'livecheck/special/nodejs.py': '@inode64',
    'livecheck/special/package.py': '@inode64',
    'livecheck/special/pecl.py': '@inode64',
    'livecheck/special/pypi.py': '@inode64',
    'livecheck/special/repology.py': '@inode64',
    'livecheck/special/rubygems.py': '@inode64',
    'livecheck/special/sourceforge.py': '@inode64',
    'livecheck/special/sourcehut.py': '@inode64',
    'livecheck/special/yarn.py': '@Tatsh',
    'livecheck/typing.py': '@Tatsh',
    'livecheck/utils/': '@Tatsh @inode64',
    'man/': '@Tatsh',
    'package.json': '@Tatsh',
    'py.typed': '@Tatsh',
  },
  pyproject+: {
    tool+: {
      mypy+: {
        mypy_path: './.stubs',
      },
      poetry+: {
        dependencies+: {
          beautifulsoup4: '>=4.13.4',
          click: '^8.1.8',
          keyring: '^25.6.0',
          loguru: '^0.7.3',
          portage: { git: 'https://github.com/gentoo/portage.git' },
          pyxdg: '^0.28',
          requests: '^2.32.3',
        },
        group+: {
          dev+: {
            dependencies+: {
              'portage-stubs': '^0',
              'types-requests': '^2.32.0.20250328',
              'types-beautifulsoup4': '>=4.12.0.20250204',
            },
          },
        },
      },
    },
  },
  skip+: ['tests/test_utils.py', 'livecheck/utils.py'],
  // Common
  authors: [
    {
      'family-names': 'Udvare',
      'given-names': 'Andrew',
      email: 'audvare@gmail.com',
      name: '%s %s' % [self['given-names'], self['family-names']],
    },
    {
      'family-names': 'Javier',
      'given-names': 'Francisco',
      email: 'web@inode64.com',
      name: '%s %s' % [self['given-names'], self['family-names']],
    },
  ],
  local funding_name = '%s2' % std.asciiLower(self.github_username),
  github_username: 'Tatsh',
  github+: {
    funding+: {
      ko_fi: funding_name,
      liberapay: funding_name,
      patreon: funding_name,
    },
  },
}
