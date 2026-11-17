/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        moso: {
          950: '#08090d',
          900: '#0d0f14',
          850: '#12141c',
          800: '#171a24',
          750: '#1e2230',
          700: '#272c3d',
          600: '#383e54',
          500: '#525b78',
          400: '#7e88a6',
          300: '#a5adc4',
          200: '#cfd4e3',
          100: '#ebeef5',
          50: '#f7f8fb',
          accent: {
            DEFAULT: '#10b981', // Bamboo emerald green
            hover: '#059669',
            subtle: 'rgba(16, 185, 129, 0.12)',
            glow: 'rgba(16, 185, 129, 0.25)',
          },
          cyan: {
            DEFAULT: '#06b6d4',
            subtle: 'rgba(6, 182, 212, 0.12)',
          }
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'Helvetica Neue',
          'sans-serif',
        ],
        mono: [
          'JetBrains Mono',
          'Fira Code',
          'SFMono-Regular',
          'Menlo',
          'Monaco',
          'Consolas',
          'monospace',
        ],
      },
      animation: {
        'pulse-subtle': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.2s ease-out forwards',
        'slide-up': 'slideUp 0.25s ease-out forwards',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
