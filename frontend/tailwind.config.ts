import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        // 9-role typography system — see src/styles/index.css .text-* utilities
        // for the fully-configured role classes (size/line-height/tracking/etc).
        display:          ['"Source Serif 4"', "Georgia", "serif"],            // 1. Display Primary — hero/major headlines
        "display-secondary": ['"Playfair Display"', "Georgia", "serif"],       // 2. Display Secondary — section intros
        ui:               ['"Outfit"', "system-ui", "sans-serif"],             // 3. UI Primary — nav/buttons/body
        "ui-secondary":   ['"Work Sans"', "system-ui", "sans-serif"],          // 4. UI Secondary — descriptions/metadata
        compact:          ['"Barlow Condensed"', "system-ui", "sans-serif"],   // 5. Compact/Condensed — tags/dense UI
        editorial:        ['"Cormorant"', "Georgia", "serif"],                 // 6. Editorial Italic — quotes/emphasis
        "mono-tech":      ['"JetBrains Mono"', "Menlo", "monospace"],          // 7. Technical Monospace — IDs/system metadata
        micro:            ['"IBM Plex Sans"', "system-ui", "sans-serif"],      // 8. Micro/Footnote — fine print
        "data-numeric":   ['"Space Grotesk"', "system-ui", "sans-serif"],      // 9. Data/Numeric — stats/metrics/counters
      },
      colors: {
        // Semantic tokens — driven by CSS custom properties (see styles/index.css).
        // Light values on :root, dark values on .dark.
        surface: {
          bg:          "rgb(var(--surface-bg) / <alpha-value>)",
          raised:      "rgb(var(--surface-raised) / <alpha-value>)",
          "raised-hi": "rgb(var(--surface-raised-hi) / <alpha-value>)",
          border:      "rgb(var(--surface-border) / <alpha-value>)",
          "border-hi": "rgb(var(--surface-border-hi) / <alpha-value>)",
          panel:       "rgb(var(--surface-panel) / <alpha-value>)",
        },
        ink: {
          primary: "rgb(var(--ink-primary) / <alpha-value>)",
          body:    "rgb(var(--ink-body) / <alpha-value>)",
          muted:   "rgb(var(--ink-muted) / <alpha-value>)",
          faint:   "rgb(var(--ink-faint) / <alpha-value>)",
          invert:  "rgb(var(--ink-invert) / <alpha-value>)",
        },
        accent: {
          brand:        "rgb(var(--accent-brand) / <alpha-value>)",
          "brand-soft": "rgb(var(--accent-brand-soft) / <alpha-value>)",
          "brand-glow": "rgb(var(--accent-brand-glow) / <alpha-value>)",
          cyan:         "rgb(var(--accent-cyan) / <alpha-value>)",
          green:        "rgb(var(--accent-green) / <alpha-value>)",
          red:          "rgb(var(--accent-red) / <alpha-value>)",
          amber:        "rgb(var(--accent-amber) / <alpha-value>)",
          blue:         "rgb(var(--accent-blue) / <alpha-value>)",
          violet:       "rgb(var(--accent-violet) / <alpha-value>)",
        },
        verdict: {
          approve: "rgb(var(--accent-green) / <alpha-value>)",
          deny:    "rgb(var(--accent-red) / <alpha-value>)",
          refer:   "rgb(var(--accent-amber) / <alpha-value>)",
        },
        // Brand ramp — clinical-healthcare deep-navy progression
        brand: {
          50:  "rgb(var(--brand-50) / <alpha-value>)",
          100: "rgb(var(--brand-100) / <alpha-value>)",
          200: "rgb(var(--brand-200) / <alpha-value>)",
          300: "rgb(var(--brand-300) / <alpha-value>)",
          400: "rgb(var(--brand-400) / <alpha-value>)",
          500: "rgb(var(--brand-500) / <alpha-value>)",
          600: "rgb(var(--brand-600) / <alpha-value>)",
          700: "rgb(var(--brand-700) / <alpha-value>)",
          800: "rgb(var(--brand-800) / <alpha-value>)",
          900: "rgb(var(--brand-900) / <alpha-value>)",
        },
      },
      keyframes: {
        "pulse-soft":      { "0%,100%": { opacity: "1" }, "50%": { opacity: "0.55" } },
        "slide-in-right":  { "0%": { transform: "translateX(20px)", opacity: "0" }, "100%": { transform: "translateX(0)", opacity: "1" } },
        "slide-in-down":   { "0%": { transform: "translateY(-12px)", opacity: "0" }, "100%": { transform: "translateY(0)", opacity: "1" } },
        "slide-in-up":     { "0%": { opacity: "0", transform: "translateY(8px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
        "fade-in":         { "0%": { opacity: "0", transform: "translateY(4px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
        "decision-reveal": { "0%": { opacity: "0", transform: "scale(0.94)" }, "100%": { opacity: "1", transform: "scale(1)" } },
        "decision-pulse":  { "0%": { opacity: "0", transform: "scale(0.6)" }, "40%": { opacity: "0.55", transform: "scale(1.05)" }, "100%": { opacity: "0", transform: "scale(1.4)" } },
        "shield-spin":     { "0%": { transform: "rotate(0)" }, "100%": { transform: "rotate(360deg)" } },
        "phi-backdrop":    { "0%": { opacity: "0" }, "40%": { opacity: "1" }, "100%": { opacity: "0" } },
        "word-up":         { "0%": { opacity: "0", transform: "translateY(14px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
        "aurora-a":        { "0%,100%": { transform: "translate3d(-10%, -8%, 0) scale(1)" },   "50%": { transform: "translate3d(8%, 6%, 0) scale(1.1)" } },
        "aurora-b":        { "0%,100%": { transform: "translate3d(12%, 4%, 0) scale(1.05)" },  "50%": { transform: "translate3d(-6%, -10%, 0) scale(0.95)" } },
        "aurora-c":        { "0%,100%": { transform: "translate3d(-4%, 14%, 0) scale(1)" },    "50%": { transform: "translate3d(10%, -8%, 0) scale(1.15)" } },
        "aurora-drift":    { "0%, 100%": { transform: "translate3d(0, 0, 0) scale(1)" }, "50%": { transform: "translate3d(40px, -30px, 0) scale(1.05)" } },
        "sweep":           { "0%": { backgroundPosition: "-200% 0" }, "100%": { backgroundPosition: "200% 0" } },
        "logo-spin":       { "0%": { transform: "rotate(0deg) scale(0.92)", opacity: "0" }, "40%": { opacity: "1" }, "100%": { transform: "rotate(360deg) scale(1)", opacity: "1" } },
        "kbd-glow":        { "0%,100%": { boxShadow: "0 0 0 0 rgba(75,85,99,0), 0 0 0 0 rgba(107,114,128,0)" }, "50%": { boxShadow: "0 0 0 1px rgba(75,85,99,0.35), 0 0 14px -2px rgba(75,85,99,0.45)" } },
        "gradient-shift":  { "0%,100%": { backgroundPosition: "0% 50%" }, "50%": { backgroundPosition: "100% 50%" } },
        "edge-flow":       { "0%": { strokeDashoffset: "80" }, "100%": { strokeDashoffset: "0" } },
        "particle-drift":  { "0%": { transform: "translate(0,0)", opacity: "0" }, "20%": { opacity: "0.7" }, "80%": { opacity: "0.7" }, "100%": { transform: "translate(var(--dx,40px),var(--dy,-30px))", opacity: "0" } },
        "ring-burst":      { "0%": { transform: "scale(0.6)", opacity: "0.6" }, "100%": { transform: "scale(2.4)", opacity: "0" } },
        "reveal-up":       { "0%": { opacity: "0", transform: "translateY(18px) scale(0.98)", filter: "blur(6px)" }, "100%": { opacity: "1", transform: "translateY(0) scale(1)", filter: "blur(0)" } },
        "float-y":         { "0%,100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-6px)" } },
        "float-soft":      { "0%,100%": { transform: "translateY(0) rotate(0deg)" }, "50%": { transform: "translateY(-10px) rotate(0.6deg)" } },
        "glow-pulse":      { "0%,100%": { opacity: "0.35" }, "50%": { opacity: "0.85" } },
        "orbit":           { "0%": { transform: "rotate(0) translateX(var(--r,40px)) rotate(0)" }, "100%": { transform: "rotate(360deg) translateX(var(--r,40px)) rotate(-360deg)" } },
        "count-flip":      { "0%": { transform: "translateY(100%)", opacity: "0" }, "100%": { transform: "translateY(0)", opacity: "1" } },
        "verdict-pulse":   { "0%": { opacity: "0.45", transform: "scale(0.96)" }, "60%": { opacity: "0", transform: "scale(1.18)" }, "100%": { opacity: "0", transform: "scale(1.18)" } },
        "stagger-word":    { "0%": { transform: "translateY(8px)" }, "100%": { transform: "translateY(0)" } },
      },
      animation: {
        "pulse-soft":      "pulse-soft 1.6s ease-in-out infinite",
        "slide-in-right":  "slide-in-right 350ms cubic-bezier(0.2,0,0,1)",
        "slide-in-down":   "slide-in-down 250ms cubic-bezier(0.16,1,0.3,1)",
        "slide-in-up":     "slide-in-up 0.30s cubic-bezier(0.2,0,0,1) both",
        "fade-in":         "fade-in 250ms cubic-bezier(0.2,0,0,1)",
        "decision-reveal": "decision-reveal 320ms cubic-bezier(0.16,1,0.3,1)",
        "decision-pulse":  "decision-pulse 600ms cubic-bezier(0.2,0,0,1) forwards",
        "shield-spin":     "shield-spin 600ms cubic-bezier(0.16,1,0.3,1)",
        "phi-backdrop":    "phi-backdrop 400ms ease-out forwards",
        "word-up":         "word-up 480ms cubic-bezier(0.16,1,0.3,1) both",
        "aurora-a":        "aurora-a 35s ease-in-out infinite alternate",
        "aurora-b":        "aurora-b 42s ease-in-out infinite alternate",
        "aurora-c":        "aurora-c 38s ease-in-out infinite alternate",
        "aurora-drift":    "aurora-drift 35s ease-in-out infinite alternate",
        "sweep":           "sweep 1.6s linear infinite",
        "logo-spin":       "logo-spin 720ms cubic-bezier(0.16,1,0.3,1) both",
        "kbd-glow":        "kbd-glow 3.2s ease-in-out infinite",
        "gradient-shift":  "gradient-shift 6s ease-in-out infinite",
        "particle-drift":  "particle-drift 4.2s ease-in-out infinite",
        "ring-burst":      "ring-burst 1100ms cubic-bezier(0.16,1,0.3,1) forwards",
        "reveal-up":       "reveal-up 620ms cubic-bezier(0.16,1,0.3,1) both",
        "float-y":         "float-y 4s ease-in-out infinite",
        "float-soft":      "float-soft 6s ease-in-out infinite",
        "glow-pulse":      "glow-pulse 2.4s ease-in-out infinite",
        "count-flip":      "count-flip 480ms cubic-bezier(0.16,1,0.3,1) both",
        "verdict-pulse":   "verdict-pulse 0.6s cubic-bezier(0.2,0,0,1) both",
        "stagger-word":    "stagger-word 0.45s cubic-bezier(0.2,0,0,1) both",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ['"Geist Mono"', "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
        serif: ['"Crimson Pro"', "Georgia", "serif"],
      },
      borderRadius: {
        sm: "4px",
        DEFAULT: "4px",
        md: "6px",
        lg: "8px",
        xl: "12px",
        "2xl": "12px",
        "3xl": "16px",
      },
      fontFeatureSettings: {
        nums: '"tnum", "ss01"',
      },
    },
  },
  plugins: [],
} satisfies Config;
