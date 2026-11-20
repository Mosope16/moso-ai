/** @type {import('tailwindcss').Config} */
// Colors are CSS variables (see src/index.css) so the same classes work in light and dark.
const rgb = (name) => `rgb(var(--${name}) / <alpha-value>)`;
const scale = (prefix, steps) => Object.fromEntries(steps.map((s) => [s, rgb(`${prefix}-${s}`)]));

export default {
  darkMode: ['class'],
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // `text-white` means "strongest text": near-white in dark mode, near-black in light mode.
        white: rgb('strong'),
        moso: {
          ...scale('moso', [950, 900, 850, 800, 750, 700, 600, 500, 400, 300, 200, 100, 50]),
          side: rgb('moso-side'),
          accent: {
            DEFAULT: rgb('accent-500'),
            hover: rgb('accent-600'),
            subtle: 'rgb(var(--accent-500) / 0.12)',
            glow: 'rgb(var(--accent-500) / 0.25)',
          },
          cyan: {
            DEFAULT: '#06b6d4',
            subtle: 'rgba(6, 182, 212, 0.12)',
          },
        },
        // Moso's bamboo green. Replaces the old neon emerald.
        accent: scale('accent', [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950]),
      },
      fontFamily: {
        // System fonts only: nothing is downloaded, so no request ever leaves the machine.
        sans: [
          'ui-sans-serif',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'Helvetica Neue',
          'Noto Sans',
          'sans-serif',
        ],
        serif: [
          'ui-serif',
          'Iowan Old Style',
          'Palatino Linotype',
          'Georgia',
          'Cambria',
          'Noto Serif',
          'Times New Roman',
          'serif',
        ],
        mono: [
          'ui-monospace',
          'SFMono-Regular',
          'JetBrains Mono',
          'Fira Code',
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
        'slide-right': 'slideRight 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards',
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
        slideRight: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(0)' },
        },
      },
    },
  },
  plugins: [],
}
