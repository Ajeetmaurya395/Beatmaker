---
version: 1.0.0
name: Beatmaker Studio Design System

colors:
  # Core palette — deep dark with neon accents
  bg-primary: "#0A0A0F"
  bg-secondary: "#12121A"
  bg-tertiary: "#1A1A28"
  bg-card: "rgba(20, 20, 35, 0.85)"
  bg-glass: "rgba(255, 255, 255, 0.04)"

  # Neon accent gradient
  accent-cyan: "#00F0FF"
  accent-purple: "#A855F7"
  accent-pink: "#F472B6"
  accent-gradient: "linear-gradient(135deg, #00F0FF 0%, #A855F7 50%, #F472B6 100%)"
  accent-gradient-horizontal: "linear-gradient(90deg, #00F0FF, #A855F7)"

  # Text
  text-primary: "#F0F0F5"
  text-secondary: "#8888A0"
  text-muted: "#555570"
  text-accent: "#00F0FF"

  # Semantic
  success: "#34D399"
  warning: "#FBBF24"
  error: "#EF4444"
  info: "#60A5FA"

  # Stem colors (each stem gets its own identity)
  stem-kick: "#FF6B6B"
  stem-snare: "#FECA57"
  stem-hats: "#48DBFB"
  stem-perc: "#FF9FF3"
  stem-bass: "#F368E0"
  stem-chords: "#54A0FF"
  stem-lead: "#00D2D3"

  # Borders & overlays
  border-subtle: "rgba(255, 255, 255, 0.06)"
  border-accent: "rgba(0, 240, 255, 0.25)"
  overlay-dark: "rgba(0, 0, 0, 0.6)"

typography:
  fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
  fontFamilyMono: "'JetBrains Mono', 'SF Mono', 'Fira Code', monospace"

  display:
    fontSize: "48px"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "-0.03em"

  h1:
    fontSize: "32px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.02em"

  h2:
    fontSize: "24px"
    fontWeight: 600
    lineHeight: 1.3

  h3:
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.4

  body:
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6

  caption:
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.02em"

  label:
    fontSize: "11px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.08em"
    textTransform: "uppercase"

spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  2xl: "48px"
  3xl: "64px"

borderRadius:
  sm: "6px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  full: "9999px"

shadows:
  card: "0 4px 24px rgba(0, 0, 0, 0.4)"
  glow-cyan: "0 0 20px rgba(0, 240, 255, 0.15)"
  glow-purple: "0 0 20px rgba(168, 85, 247, 0.15)"
  glow-strong: "0 0 40px rgba(0, 240, 255, 0.25)"
  inset: "inset 0 1px 0 rgba(255, 255, 255, 0.05)"

motion:
  duration-fast: "120ms"
  duration-normal: "250ms"
  duration-slow: "400ms"
  duration-dramatic: "800ms"
  easing-default: "cubic-bezier(0.4, 0, 0.2, 1)"
  easing-spring: "cubic-bezier(0.34, 1.56, 0.64, 1)"
  easing-out: "cubic-bezier(0, 0, 0.2, 1)"

components:
  button-primary:
    background: "{colors.accent-gradient}"
    color: "{colors.bg-primary}"
    padding: "{spacing.sm} {spacing.lg}"
    borderRadius: "{borderRadius.full}"
    fontWeight: 700
    fontSize: "{typography.body.fontSize}"
    transition: "all {motion.duration-normal} {motion.easing-default}"
    hover:
      boxShadow: "{shadows.glow-strong}"
      transform: "translateY(-1px)"

  button-secondary:
    background: "{colors.bg-glass}"
    color: "{colors.text-primary}"
    border: "1px solid {colors.border-subtle}"
    padding: "{spacing.sm} {spacing.lg}"
    borderRadius: "{borderRadius.full}"
    backdropFilter: "blur(12px)"

  card:
    background: "{colors.bg-card}"
    borderRadius: "{borderRadius.lg}"
    border: "1px solid {colors.border-subtle}"
    backdropFilter: "blur(16px)"
    boxShadow: "{shadows.card}"
    padding: "{spacing.lg}"

  genre-chip:
    background: "{colors.bg-glass}"
    borderRadius: "{borderRadius.full}"
    padding: "{spacing.xs} {spacing.md}"
    border: "1px solid {colors.border-subtle}"
    fontSize: "{typography.caption.fontSize}"
    fontWeight: 600
    active:
      background: "rgba(0, 240, 255, 0.12)"
      border: "1px solid {colors.accent-cyan}"
      color: "{colors.accent-cyan}"
      boxShadow: "{shadows.glow-cyan}"

  stem-track:
    height: "52px"
    borderRadius: "{borderRadius.md}"
    background: "{colors.bg-glass}"
    border: "1px solid {colors.border-subtle}"
    padding: "0 {spacing.md}"

  waveform-display:
    height: "120px"
    background: "{colors.bg-secondary}"
    borderRadius: "{borderRadius.lg}"
    border: "1px solid {colors.border-accent}"

  slider:
    trackHeight: "4px"
    trackBackground: "{colors.bg-tertiary}"
    thumbSize: "14px"
    thumbBackground: "{colors.accent-cyan}"
    activeTrack: "{colors.accent-gradient-horizontal}"
---

# Beatmaker Studio — Design Guidelines

## Philosophy
A professional music production interface that feels like a premium DAW plugin.
Dark-first, neon-accented, with glassmorphism depth. The UI should feel alive
with subtle micro-animations — pulsing play buttons, waveform shimmer, smooth
stem transitions.

## Colors
- **Always dark backgrounds** — the neon accents pop against deep blacks
- Each stem type has a unique color identity for instant visual recognition
- Use gradients sparingly — primarily on CTAs and the active waveform

## Typography
- Inter for all UI text (clean, modern, great number rendering for BPM/bars)
- Monospace (JetBrains Mono) for timestamps, BPM values, seed numbers

## Motion
- Buttons: subtle lift + glow on hover
- Cards: fade-in with slight upward translation on mount
- Waveform: continuous subtle gradient animation during playback
- Stems: slide in sequentially with stagger delay
- Loading: skeleton shimmer with gradient sweep

## Component Patterns
- **Genre Chips**: Pill-shaped, glow border on active state
- **Stem Tracks**: Horizontal bars with colored indicator, mute/solo toggles
- **Waveform**: Canvas-rendered, gradient-filled peaks
- **Sliders**: Thin track with glowing thumb
