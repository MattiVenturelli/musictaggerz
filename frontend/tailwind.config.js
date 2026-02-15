/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        surface: {
          100: '#1e1e2e',
          200: '#181825',
          300: '#11111b',
          400: '#313244',
          500: '#45475a',
          600: '#585b70',
        },
        text: {
          DEFAULT: '#cdd6f4',
          muted: '#a6adc8',
          subtle: '#6c7086',
        },
        accent: {
          blue: '#89b4fa',
          green: '#a6e3a1',
          yellow: '#f9e2af',
          red: '#f38ba8',
          mauve: '#cba6f7',
          peach: '#fab387',
          teal: '#94e2d5',
          pink: '#f5c2e7',
          sky: '#89dcfe',
          lavender: '#b4befe',
        },
        overlay: {
          DEFAULT: '#6c7086',
          light: '#7f849c',
        },
      },
    },
  },
  plugins: [],
}
