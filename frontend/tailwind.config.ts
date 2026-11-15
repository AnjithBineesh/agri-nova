import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        forest: { DEFAULT: "#0e2a1f", 900: "#08190f", 800: "#0e2a1f", 700: "#173b2c", 600: "#21503c" },
        leaf: { DEFAULT: "#2f7a45", 600: "#256338", 100: "#e2f0e2", 50: "#f0f7ef" },
        lime: { DEFAULT: "#d4f25e", 600: "#bfe043", 100: "#f2fbd0" },
        paper: "#f2f3ef",
        ink: { DEFAULT: "#14201a", soft: "#55635a", faint: "#87938b" },
        line: "#e2e6df",
        orbit: { DEFAULT: "#2f6fa8", 100: "#e2edf7", 50: "#f0f5fb" },
        warn: { DEFAULT: "#b8620f", 100: "#fbecd9" },
        risk: { DEFAULT: "#b3372f", 100: "#f8e1df" },
      },
      fontFamily: {
        sans: ["Manrope", "system-ui", "sans-serif"],
        display: ["Manrope", "system-ui", "sans-serif"],
        serif: ["'Instrument Serif'", "Georgia", "serif"],
      },
      borderRadius: { panel: "20px", hero: "28px" },
      boxShadow: { soft: "0 1px 2px rgba(14,42,31,0.04), 0 8px 24px -12px rgba(14,42,31,0.12)" },
    },
  },
  plugins: [],
};
export default config;
