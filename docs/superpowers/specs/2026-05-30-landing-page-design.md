# YatraTrack Landing Page — Design Spec

**Date:** 2026-05-30  
**Status:** Approved  
**Product:** YatraTrack — School Bus / Vehicle Management System  

---

## Overview

Single-page marketing landing page for YatraTrack. Targets both school admins (decision-makers) and parents (end users). Built as a standalone React + Vite + Tailwind CSS app in `landing/`.

---

## Visual Design

| Property | Value |
|---|---|
| Primary color | Indigo `#4f46e5` |
| Background | White `#ffffff` + `#fafafa` |
| Accent light | `#eef2ff` (indigo-50) |
| Border | `#e5e7eb` |
| Text heading | `#1e1b4b` |
| Text body | `#6b7280` |
| WhatsApp green | `#25d366` |
| Font | Inter (system fallback) |
| Top stripe | 3px indigo gradient |

Indian identity kept in **copy only** — Hinglish hero headline, "Made for Indian Schools" badge.

---

## Sections (top to bottom)

### 1. Sticky Nav
- Logo: `🛤 YatraTrack` (indigo)
- Links: Features · Pricing · Contact (anchor scroll)
- CTA buttons: `Contact Us` (outline) + `💬 WhatsApp` (green)

### 2. Hero
- Badge: `🇮🇳 Made for Indian Schools`
- H1: `बच्चों का सफर, Safe & Tracked.`
- Subtitle: Hinglish — real-time GPS, boarding alerts, attendance, one platform
- CTAs: `💬 WhatsApp Us` (primary, green) + `✉️ Contact Us` (secondary, outline)
- Trust badges (4): No app download needed · Browser-based PWA · Real-time GPS · Child safety alerts

### 3. Live Dashboard Preview
- Mockup of real-time map with bus marker + route line + stop dots
- `LIVE` tag on map
- 3 stat cards: Active Buses (12) · Students Safe (348) · Alerts (0)

### 4. Features (`#features`)
- Section label: "Why schools choose YatraTrack"
- 6-card grid:
  1. 📍 Live GPS Tracking
  2. 🔔 Safety Alerts
  3. ✅ Attendance
  4. 🚌 Fleet Management
  5. 📱 No App Needed
  6. 🏫 Multi-School

### 5. How It Works
- 3-step numbered flow:
  1. School Setup — Admin adds vehicles, routes & drivers
  2. Parents Join — See child's assigned bus & stop
  3. Track Live — Driver starts trip → real-time tracking + auto alerts

### 6. Built for Everyone
- 3 role cards: 🏫 School Admin · 👪 Parents · 🚌 Driver

### 7. Pricing (`#pricing`)
- Headline: "Pricing"
- Hinglish copy: हर school की ज़रूरत अलग होती है
- CTAs: `💬 WhatsApp Us` + `✉️ Contact Us`
- Note: "We reply within a few hours · No spam · No sales pressure"

### 8. Footer
- Logo + "Made with ❤️ in India" + © 2026 YatraTrack

---

## CTAs

| CTA | Behaviour |
|---|---|
| 💬 WhatsApp Us | `https://wa.me/91XXXXXXXXXX?text=Hi, I'm interested in YatraTrack for my school` — opens WhatsApp with pre-filled message. Number: placeholder, fill later. |
| ✉️ Contact Us | `mailto:hello@yatratrack.in` — opens user's email app. Email: placeholder, fill later. |

---

## Tech Stack

- React 19 + Vite 6
- Tailwind CSS 4
- No external component libraries (pure Tailwind)
- Single page — `landing/src/App.jsx`
- Deployable to Cloudflare Pages / Netlify / Vercel (static)

---

## Out of Scope

- No waitlist / city chips section (removed)
- No "Book a Demo" / "Free Trial" CTA (not yet applicable)
- No backend / form submission (mailto only)
- No animations beyond CSS transitions
