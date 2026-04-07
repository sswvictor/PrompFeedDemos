/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,jsx,ts,tsx}',
    './src/**/*.{js,jsx,ts,tsx}',
  ],
  presets: [require('nativewind/preset')],
  theme: {
    extend: {
      colors: {
        // Higher-contrast, easier-to-read mobile palette
        'fixme-bg': '#131312',
        'fixme-card': '#262624',
        'fixme-border': '#3A3A37',
        'fixme-accent': '#C4B8A8',
        'fixme-text-primary': '#F5F5F5',
        'fixme-text-secondary': '#D0CFCF',
        'fixme-text-muted': '#8A8A8A',
        'fixme-error': '#E53935',
        'fixme-success': '#4CAF50',
      },
      fontSize: {
        // Global readability bump without touching every screen
        xs: ['0.8125rem', { lineHeight: '1.2rem' }],
        sm: ['0.9375rem', { lineHeight: '1.35rem' }],
        base: ['1.0625rem', { lineHeight: '1.6rem' }],
        lg: ['1.1875rem', { lineHeight: '1.75rem' }],
      },
      fontFamily: {
        sans: ['-apple-system', 'SF Pro Display', 'Helvetica Neue', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
