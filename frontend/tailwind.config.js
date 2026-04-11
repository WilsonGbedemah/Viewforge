/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Syne', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        forge: {
          bg:      '#090909',
          surface: '#111111',
          border:  '#1e1e1e',
          muted:   '#2a2a2a',
          text:    '#e8e4dc',
          dim:     '#888880',
          red:     '#e63528',
          amber:   '#f59b00',
          green:   '#22c55e',
          blue:    '#3b82f6',
        },
      },
      animation: {
        'pulse-dot': 'pulse 1.8s cubic-bezier(0.4,0,0.6,1) infinite',
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.25s ease-out',
      },
      keyframes: {
        fadeIn:  { from: { opacity: 0 }, to: { opacity: 1 } },
        slideUp: { from: { opacity: 0, transform: 'translateY(8px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
      },
    },
  },
  plugins: [],
}
