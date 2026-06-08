# YatraTrack — Landing Page

A self-contained static marketing site for **YatraTrack**, the browser-based school-bus
tracking platform for Indian schools (live GPS tracking, attendance, child-safety alerts).

This is **not** part of the React SPA — it is a single, dependency-free `index.html` that
loads Tailwind via the Play CDN (`https://cdn.tailwindcss.com`). There is **no build step**.

## Preview

Either open the file directly in a browser:

```bash
open index.html          # macOS
# or just double-click index.html in your file manager
```

…or serve the folder over HTTP (recommended, mirrors production):

```bash
npx serve landing
# then visit the printed URL, e.g. http://localhost:3000
```

(Run the `npx serve` command from the repository root, or `npx serve .` from inside this
`landing/` directory.)

## What's inside

A single, fully responsive, accessible page (`index.html`) with:

- **Sticky top nav** — `YatraTrack` wordmark, anchor links (Features / How it works /
  Pricing / Contact), a `Contact Us` outline button, and a green (`#25d366`) **WhatsApp** CTA.
- **Hero** — "Made for Indian Schools 🇮🇳" badge, the tagline
  **बच्चों का सफर, Safe & Tracked.** with the English subtext "Children's journey,
  Safe & Tracked.", a primary WhatsApp CTA, a secondary `hello@yatratrack.in` link, four
  trust badges, and a subtle radial indigo hero glow.
- **Dashboard preview** — a pure CSS/HTML mock "live map" with a pulsing bus dot that
  travels along a dashed route toward the school, a blinking **LIVE** badge, an ETA chip,
  three stat cards, and a floating "child boarded" safety toast. No JS map library.
- **Features grid (6)** — Live GPS tracking · Attendance · Child-safety alerts ·
  No app install needed · Works on any phone browser · Affordable for Indian schools.
  Each uses an inline (lucide-style) SVG icon.
- **How it works (3 steps)** — School sets up routes → Parents join with a code →
  Track the bus live.
- **Built for** — Parents / Drivers / Schools.
- **Pricing teaser** — Hinglish copy with WhatsApp + email CTAs and a
  "No spam · No sales pressure" reassurance line.
- **Footer** — contact (WhatsApp, `hello@yatratrack.in`, `yatratrack.in`),
  "Made with ❤️ in India", and copyright.

## Design system

- **Palette:** Indigo `#4f46e5` + white/`#fafafa` only. Accent `#eef2ff`, headings `#1e1b4b`,
  body `#6b7280`, border `#e5e7eb`, WhatsApp green `#25d366`. **No saffron / warm colors** —
  Indian identity is conveyed through copy (Hinglish + the 🇮🇳 badge), not color.
- 3px indigo top stripe; radial indigo hero glow; CSS keyframes for the pulse / blink /
  bus-travel animations (all disabled under `prefers-reduced-motion`).
- Mobile-first and responsive; semantic landmarks (`header`, `nav`, `main`, `section`,
  `footer`), a skip-to-content link, accessible labels and `role="img"` alt text on the
  map mockup, and visible focus rings.

## ⚠️ Launch-blocking placeholders to replace

Before going live, search-and-replace these placeholders in `index.html`:

- `+91XXXXXXXXXX` — the real WhatsApp number (appears in every `wa.me/91XXXXXXXXXX...`
  link and in the footer contact line).
- Confirm `hello@yatratrack.in` and `yatratrack.in` are the final contact email and domain.

## Deployment

Designed for static hosting (e.g. **Cloudflare Pages**). Deploy the contents of this
`landing/` directory as-is — no build command, output directory is the folder itself.
