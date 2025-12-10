/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'sma-dark': '#223540',
        'sma-primary': '#00a99d',
        'sma-darkest': '#171a22',
        'sma-light': '#fafafa',
        'sma-white': '#ffffff',
        'sma-lime': '#aae437',
        'sma-teal': '#53ddcf',
        'sma-yellow': '#b9ff57',
      },
    },
  },
  plugins: [],
}

