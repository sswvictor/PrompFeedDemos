/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Brand neutrals for utility classes like text-white/bg-black
        white: '#F3EFE6',
        black: '#121110',
        fixme: {
          bg: '#0A0A0A',
          'bg-soft': '#111111',
          card: '#161616',
          'card-hover': '#1E1E1E',
          border: '#242424',
          'border-soft': '#1C1C1C',
          accent: '#F5F5F0',
          'accent-light': '#E8E8E3',
          'text-primary': '#F0EDE8',
          'text-secondary': '#9A9692',
          'text-muted': '#65625E',
          success: '#34D399',
          error: '#EF4444',
        },
      },
      fontFamily: {
        sans: ['Poppins', 'Open Sans', 'system-ui', '-apple-system', 'sans-serif'],
      },
      borderRadius: {
        'xl': '16px',
        '2xl': '20px',
        '3xl': '28px',
      },
      transitionTimingFunction: {
        'spring': 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
      animationDelay: {
        '75': '75ms',
        '150': '150ms',
        '225': '225ms',
        '300': '300ms',
      },
    },
  },
  plugins: [],
}
