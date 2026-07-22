import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Near-black neutral surfaces (Vercel-style), replaces ad-hoc slate usage.
        ink: {
          950: "#0a0a0a",
          900: "#111113",
          850: "#161619",
          800: "#1c1c21",
          700: "#26262c",
          600: "#33333b",
          500: "#4b4b55",
          400: "#71717c",
          300: "#9b9ba4",
          200: "#c6c6cd",
          100: "#ececf1"
        },
        // Single brand accent, pulled from the TestOStErone logo blue.
        brand: {
          300: "#93c5fd",
          400: "#5ea1ff",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8"
        },
        success: {
          300: "#6ee7b7",
          400: "#34d399",
          500: "#10b981",
          600: "#059669"
        },
        danger: {
          300: "#fca5a5",
          400: "#f87171",
          500: "#ef4444",
          600: "#dc2626"
        },
        warn: {
          300: "#fcd34d",
          400: "#fbbf24",
          500: "#f59e0b"
        }
      },
      keyframes: {
        "muscle-flex": {
          "0%, 100%": { transform: "scale(1)" },
          "35%": { transform: "scale(1.12) rotate(-4deg)" },
          "65%": { transform: "scale(1.06) rotate(2deg)" }
        },
        "muscle-droop": {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(3px)" }
        }
      },
      animation: {
        "muscle-flex": "muscle-flex 900ms ease-in-out infinite",
        "muscle-droop": "muscle-droop 1.8s ease-in-out infinite"
      }
    }
  },
  plugins: []
} satisfies Config;
