# Open Questions

## School Bus Management System - 2026-05-26 (Initial)

- [ ] **Target geography (India vs Global)?** — Determines default payment gateway (Razorpay for India, Stripe for global), currency, SMS provider (MSG91 vs Twilio), and compliance requirements (GDPR vs India DPDP Act).
- [x] **Single school pilot or multi-school from day 1?** — RESOLVED in Iteration 1: Single school for MVP. Multi-tenancy (RLS, super admin) deferred to V2 (Weeks 7-14).
- [ ] **Who is the first pilot school?** — Real route data and user count estimates would validate capacity planning and hosting tier selection.
- [x] **SMS notifications needed in MVP?** — RESOLVED in Iteration 1: No SMS or push notifications in MVP. In-app only via Socket.IO. Web Push deferred to V2.
- [ ] **Driver device minimum spec?** — Older Android phones may have unreliable GPS or browsers that don't support Service Workers well. Need to define minimum Android/iOS version. More important now that V2 includes Capacitor.js driver app.
- [ ] **Branding / domain name decided?** — Affects PWA manifest, email templates, SSL certificate setup. Needed before deployment.
- [ ] **Parent self-registration or admin-only registration?** — Self-registration is more scalable but needs invitation codes or school-code verification to prevent unauthorized signups.
- [ ] **Language / localization requirements?** — If Hindi or regional language support is needed, i18n must be baked into the frontend from Phase 1 (retrofitting is expensive).
- [ ] **Existing data to migrate?** — If the school currently uses spreadsheets for routes/students, a data import tool may be needed in Phase 1.
- [x] **Team size and availability?** — RESOLVED in Iteration 1: Plan assumes solo developer. MVP scoped to 6 weeks demoable. V2 extends to Week 14.

## School Bus Management System - 2026-05-26 (Revision 1 - Architect + Critic Feedback)

- [ ] **Capacitor.js build signing for driver app (V2)?** — Android APK needs signing key. iOS IPA needs Apple Developer account ($99/yr). Decide if driver app targets Android-only for V2 to reduce cost.
- [ ] **MapTiler vs Stadia Maps for production tiles?** — Both have free tiers. MapTiler: 100k tiles/mo. Stadia: 200k tiles/mo. Choose one before production deployment. Stadia has higher free limit.
- [ ] **Nominatim self-hosted vs MapTiler geocoding for production?** — Public Nominatim has rate limits (1 req/sec). MapTiler geocoding: free 100k/mo. Self-hosted Nominatim requires ~2GB RAM dedicated server. Decision depends on expected geocoding volume.
- [ ] **Redis persistence strategy?** — Redis is used for GPS buffer, route corridor cache, account lockout, and Socket.IO pub/sub. If Redis restarts, GPS buffer and corridor cache are lost (rebuilt on next trip start). Decide if Redis AOF persistence is needed or if volatile cache is acceptable.
- [ ] **Refresh token expiry duration?** — Original plan said 7 days. With rotation + family tracking, should this be longer (30 days) for better UX, or shorter (7 days) for tighter security? Depends on risk tolerance for a child-tracking system.
- [ ] **"Keep screen on" workaround for MVP driver app?** — Browser cannot prevent screen lock. Options: (a) use Wake Lock API (experimental, Chrome-only), (b) instruct driver to change phone settings manually, (c) accept GPS pauses and show "tracking paused" to parents. Decide which workaround to document.

## School Bus Management System - 2026-05-27 (Revision 2 - Logging, Safety, Operational Additions)

- [ ] **Should trip end be BLOCKED until all boarded students are dropped, or just warn?** — Current plan moves trip to "pending_safeguard_check" status. Alternative: allow trip end but fire CRITICAL alert only. Blocking is safer but could frustrate drivers if a student was dropped and they forgot to mark it. Decide strictness level.
- [ ] **Attendance marking UX: stop-by-stop enforced or flexible?** — Option A: driver must mark attendance at each stop sequentially (enforced order). Option B: driver can mark any student at any time (flexible but error-prone). Option A prevents skipped stops but adds friction.
- [ ] **Parent absent marking deadline: how close to trip start?** — Current plan allows absent marking only before trip.status = in_progress. Should there be an earlier cutoff (e.g., 30 min before scheduled departure) to give the driver time to see updated list?
- [ ] **Feedback rating visibility to drivers?** — Should drivers see their own ratings/average? Transparency motivates improvement but could cause conflict if a driver disputes a low rating. Options: (a) drivers see aggregate only, (b) drivers see individual ratings anonymized, (c) drivers see nothing (admin-only).
- [ ] **Compliance report regulatory requirements?** — Different transport authorities may require specific data fields or formats. Need input from a real school/transport authority on what fields are mandatory before building the report template.
- [x] **PDF generation library: reportlab vs weasyprint?** — RESOLVED in Revision 2: reportlab chosen. Pure Python, zero system dependencies. weasyprint rejected — requires Cairo/Pango system packages, violates "no new infrastructure deps" principle.
- [ ] **Log retention for audit_logs table vs application logs?** — Log retention (LOG_RETENTION_DAYS) covers application stdout/file logs. The audit_logs DB table has different retention needs (potentially years for compliance). Clarify if audit_logs should have a separate retention policy.

## School Bus Management System - 2026-05-27 (Revision 3 - Chat Removal + Driver Phone Display)

- [ ] **Individual driver phone opt-out?** — Current design is school-level toggle only (`driver_phone_visible` in school settings). Should drivers be able to individually opt out? Would add a `phone_visible` column to users table. Recommend deferring to post-launch unless drivers actually complain. School-level toggle is sufficient for MVP.
- [ ] **Should broadcasts be promoted from V2 to MVP?** — Broadcasts are low-effort (1 lightweight table, 1 Socket.IO event, 2 API endpoints). Could be promoted to MVP Phase 2 alongside safety features since the complexity cost is minimal. Current plan keeps them in V2.
