/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#17202a',
        ocean: '#0f766e',
        coral: '#e05f43',
        gold: '#c99700'
      }
    }
  },
  plugins: []
};
