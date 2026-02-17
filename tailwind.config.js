// agora_voting/tailwind.config.js
module.exports = {
  content: [
    './templates/**/*.html',
    './static/js/**/*.js',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          dark: '#0B0B0C',
          DEFAULT: '#111213',
          light: '#1A1B1E',
        },
        secondary: {
          DEFAULT: '#FFFFFF',
          muted: '#E5E7EB',
        },
        gray: {
          50: '#F9FAFB',
          100: '#F3F4F6',
          200: '#E5E7EB',
          300: '#D1D5DB',
          400: '#9CA3AF',
          500: '#6B7280',
          600: '#4B5563',
          700: '#374151',
          800: '#1F2937',
          900: '#111827',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      fontSize: {
        'h1': ['3.25rem', { lineHeight: '1.1', fontWeight: '600' }],
        'h2': ['2.25rem', { lineHeight: '1.2', fontWeight: '600' }],
        'h3': ['1.5rem', { lineHeight: '1.3', fontWeight: '500' }],
        'body': ['1rem', { lineHeight: '1.5', fontWeight: '400' }],
        'caption': ['0.875rem', { lineHeight: '1.4', fontWeight: '400' }],
      },
      borderRadius: {
        'card': '12px',
        'pill': '9999px',
      },
    },
  },
  plugins: [],
}