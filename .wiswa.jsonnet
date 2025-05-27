local utils = import 'utils.libjsonnet';

(import 'defaults.libjsonnet') + {
  // Project-specific
  description: 'Tool to update ebuilds.',
  keywords: ['command line', 'ebuild', 'gentoo', 'portage'],
  project_name: 'livecheck',
  version: '0.1.0',
  want_main: true,
  citation+: {
    'date-released': '2025-04-13',
  },
  gitignore+: [
    '.history',
    '.idea',
  ],
  pyproject+: {
    tool+: {
      poetry+: {
        dependencies+: {
          beautifulsoup4: '>=4.13.4',
          defusedxml: '^0.7.1',
          keyring: '^25.6.0',
          platformdirs: '^4.3.7',
          requests: '^2.32.3',
        },
        group+: {
          dev+: {
            dependencies+: {
              'portage-stubs': '^0',
              'types-defusedxml': '>=0.7.0.20240218',
              'types-requests': '^2.32.0.20250515',
              'types-beautifulsoup4': '>=4.12.0.20250204',
            },
          },
        },
      },
    },
  },
  security_policy_supported_versions: { '0.1.x': ':white_check_mark:' },
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
