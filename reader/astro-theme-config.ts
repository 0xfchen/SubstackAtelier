type NavItem = {
  label: string;
  href: string;
};

/**
 * astro-theme-config.ts
 *
 * Central configuration for the Substack Archive Reader.
 */

const config = {
  site: {
    url: 'https://example.com',
    base: '',
    lang: 'en',
    locale: 'en_US',
    dateLocale: 'en-US',
    title: 'Substack Atelier',
    logoLabel: 'Substack Atelier',
    description: 'Personal local archive of Substack essays and newsletters.',
    author: 'Substack Atelier',
    defaultOgImage: '/og.png',
  },

  // Header navigation links
  nav: [
    { label: 'Library', href: '/' },
    { label: 'Graph', href: '/graph' },
    { label: 'Search', href: '/search' },
  ] as NavItem[],

  // Footer navigation links (primary links are in header)
  footerNav: [] as NavItem[],

  content: {
    categoryOrder: [
      'Design',
      'Getting Started',
      'Markdown',
      'Open Source',
      'Systems',
      'Notes',
      'Research',
      'Performance',
      'MDX',
    ],
  },

  behavior: {
    smoothScroll: true,
  },

  comments: {
    mode: 'off',
  },

  social: {
    github: 'https://github.com/0xfchen',
  },
};

export default config;
