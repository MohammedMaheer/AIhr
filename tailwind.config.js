/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#3B82F6',
        'primary-dark': '#1E40AF',
        secondary: '#8B5CF6',
        accent: '#10B981',
      },
    },
  },
  // Ensure dynamically composed classes still appear in the bundle.
  // The app builds class names from data at runtime in some places.
  safelist: [
    { pattern: /^(bg|text|border|ring|from|to|via)-(red|green|blue|yellow|orange|purple|pink|gray|emerald|sky|indigo|amber|rose|cyan|teal|lime|violet|fuchsia|slate|zinc|neutral|stone)-(50|100|200|300|400|500|600|700|800|900)$/ },
    { pattern: /^(grid-cols|col-span|row-span|gap|p|m|w|h|rounded|shadow|opacity)-/ },
    'animate-spin', 'animate-pulse', 'animate-bounce',
    'hidden', 'block', 'inline-block', 'flex', 'grid',
  ],
}
