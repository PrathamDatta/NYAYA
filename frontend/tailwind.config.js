/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        paper: "rgb(var(--paper) / <alpha-value>)", surface: "rgb(var(--surface) / <alpha-value>)",
        sunken: "rgb(var(--sunken) / <alpha-value>)", ink: "rgb(var(--ink) / <alpha-value>)",
        muted: "rgb(var(--muted) / <alpha-value>)", line: "rgb(var(--line) / <alpha-value>)",
        brand: { DEFAULT: "rgb(var(--brand) / <alpha-value>)", strong: "rgb(var(--brand-strong) / <alpha-value>)", soft: "rgb(var(--brand-soft) / <alpha-value>)" },
        brass: { DEFAULT: "rgb(var(--brass) / <alpha-value>)", soft: "rgb(var(--brass-soft) / <alpha-value>)" },
        ok: { DEFAULT: "rgb(var(--ok) / <alpha-value>)", soft: "rgb(var(--ok-soft) / <alpha-value>)" },
        warn: { DEFAULT: "rgb(var(--warn) / <alpha-value>)", soft: "rgb(var(--warn-soft) / <alpha-value>)" },
        bad: { DEFAULT: "rgb(var(--bad) / <alpha-value>)", soft: "rgb(var(--bad-soft) / <alpha-value>)" },
      },
      fontFamily: {
        display: ['"Fraunces Variable"', "Georgia", "serif"],
        sans: ['"Inter Variable"', "system-ui", '"Segoe UI"', '"Nirmala UI"', "sans-serif"],
        indic: ['"Nirmala UI"', '"Noto Sans Devanagari"', '"Noto Sans Bengali"', '"Noto Sans Tamil"', "system-ui", "sans-serif"],
      },
      boxShadow: { card: "0 1px 0 rgb(var(--line)), 0 8px 24px -16px rgb(var(--ink) / 0.25)" },
    },
  },
  plugins: [],
};
