# School Bus Management System - Revision 3: Chat Removal + Driver Phone Display

> ⚠️ **SUPERSEDED — kept for history only.** Folded into [`YATRATRACK-BUILD-SPEC.md`](./YATRATRACK-BUILD-SPEC.md) (v1.0, 2026-05-30). Build from that.

**Date:** 2026-05-27
**Author:** Planner Agent (RALPLAN Consensus - Iteration 3)
**Status:** DRAFT - Pending User Confirmation
**Scope:** Remove chat feature entirely, replace with driver phone display, simplify broadcasts

---

## 1. RALPLAN-DR Summary (Revision 3)

### Principles (3, scoped to this change)

1. **Real-world communication patterns win** -- Parents call the driver or school directly. Chat is overhead nobody uses. Replace with the simplest possible bridge: show a phone number.
2. **No new tables when existing columns suffice** -- `users.phone` already exists for all users including drivers. No new infrastructure needed for driver phone display.
3. **Privacy by default, admin-controlled disclosure** -- Driver's personal phone number is sensitive. Admin controls visibility via school settings. Masking in UI display.

### Decision Drivers (Top 3)

| # | Driver | Weight | Rationale |
|---|--------|--------|-----------|
| 1 | **Simplicity** | Critical | Chat (Socket.IO rooms, conversations table, messages table, typing indicators) is significant complexity for a feature nobody will use when a phone call solves the problem. |
| 2 | **Privacy** | High | Drivers may not want personal numbers exposed. Must be opt-in at school level with masked display. |
| 3 | **Keep broadcasts** | Medium | Admin broadcast announcements (V9) are one-way, no-reply, and serve a real purpose (route changes, delays, holiday notices). Must survive the chat removal. |

### Viable Options: Driver Contact

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **Option A: Direct phone display (chosen)** | Show driver's phone number to parent during active trip only, controlled by school setting | Zero new tables, zero new infrastructure, standard UX (tel: link), works offline | Exposes real phone number (mitigated by admin toggle + masked display) |
| **Option B: In-app call relay / masked number** | Use a telephony service (Twilio/Exotel) to create a masked forwarding number | Full privacy, driver's real number never exposed | New dependency, recurring cost (~$1/number/month), India-specific compliance (TRAI DND rules), over-engineered for MVP |

**Decision: Option A -- Direct phone display with privacy controls**
**Rationale:** A `tel:` link is the simplest possible solution. India context: tap-to-call is standard mobile UX. Privacy is handled via admin school setting toggle + masked display in UI (show last 4 digits visually, full number only in the tel: href). No new dependencies, no new tables, no recurring cost.
**Invalidation of Option B:** Telephony relay adds a paid dependency (Twilio/Exotel), requires TRAI compliance for Indian numbers, and is architecturally complex for a feature that amounts to "parent calls driver." If privacy becomes a real concern post-launch, Option B can be added later as a school setting upgrade.

### ADR (Revision 3)

| Field | Value |
|-------|-------|
| **Decision** | Remove V8 (parent-to-admin chat) entirely. Keep V9 (broadcast announcements) with simplified model. Add driver phone display to parent view during active trips, controlled by school setting. |
| **Drivers** | Real-world usage pattern (people call), simplicity (remove 3 tables + 5 endpoints + 4 Socket.IO event types), privacy (admin-controlled disclosure) |
| **Alternatives Considered** | Keep chat but simplify (rejected: still maintains tables and Socket.IO events for near-zero usage). Telephony relay via Twilio (rejected: paid dependency, over-engineered). |
| **Why Chosen** | Removes significant complexity (conversations + messages + conversation_participants = 3 tables, 5 API endpoints, 4 Socket.IO event types, chat UI components). Replaces with ~20 lines of backend code (one conditional API field + one school setting) and one small frontend component. |
| **Consequences** | No in-app messaging capability. Parents who want to discuss issues asynchronously must use complaints system (V2) or external channels (WhatsApp, phone). Drivers' phone numbers are exposed to parents during active trips (mitigated by admin toggle + masked display). |
| **Follow-ups** | Monitor if schools request async messaging post-launch. If demand exists, evaluate lightweight alternatives (complaint thread replies) before re-introducing full chat. |

---

## 2. Specific Plan Changes

### REMOVE

#### DB Tables (3 tables eliminated)

From Section 6, "COMMUNICATION (V2)" block:

```
REMOVE: conversations               -- entire table
REMOVE: conversation_participants    -- entire table
REMOVE: messages                     -- entire table
```

#### DB Indexes (3 indexes eliminated)

From Section 6.2:

```
REMOVE: CREATE INDEX idx_messages_conversation ON messages (conversation_id, created_at DESC);
REMOVE: CREATE UNIQUE INDEX idx_conv_participants_unique ON conversation_participants (conversation_id, user_id);
REMOVE: CREATE INDEX idx_conv_participants_user ON conversation_participants (user_id);
```

#### API Endpoints (5 endpoints eliminated)

From Section 7.11 "Communication (V2)":

```
REMOVE: POST   /api/v1/conversations                    -- Start new conversation
REMOVE: GET    /api/v1/conversations                    -- List user's conversations
REMOVE: GET    /api/v1/conversations/{id}               -- Get conversation with messages
REMOVE: POST   /api/v1/conversations/{id}/messages      -- Send message
REMOVE: PUT    /api/v1/messages/{id}/read               -- Mark message as read
```

#### Socket.IO Events (4 event types eliminated)

From Section 7.15:

```
REMOVE: "chat_message"   (client -> server)   {conversation_id, content}
REMOVE: "typing"         (client -> server)   {conversation_id}
REMOVE: "chat_message"   (server -> client)   {conversation_id, message}
REMOVE: "typing"         (server -> client)   {conversation_id, user_id}
```

#### Feature List Entries

From Section 5, V2 Feature List:

```
REMOVE: V8 | Parent-to-admin messaging (simple threaded chat via Socket.IO) | P2
```

#### Modular Monolith Structure References

From Section 3.4 (directory layout):

```
REMOVE: app/chat/ directory reference
```

From Section 3.1 (Application Layer diagram):

```
REMOVE: "Chat messages," from Socket.IO description line
```

#### School Settings Feature Flags

From Section 8, Phase 1, Step 3 (school settings JSONB):

```
REMOVE: "chat_enabled" feature flag
REMOVE: "driver_direct_chat" feature flag
```

#### Guardrails

From "Must NOT Have" section:

```
REMOVE: "No direct phone number exposure between parent and driver"
        (replaced by controlled, admin-toggled phone display -- see ADD section)
```

#### Revision 2 Step 10 Reference

From Revision 2, CHANGE 3, Step 10 description:

```
REMOVE: "Parent-to-admin chat (threaded) via Socket.IO" sub-task
```

---

### KEEP (unchanged)

#### V9 Broadcast Announcements -- KEEP but decouple from conversations table

Broadcasts were previously modeled as `conversation.type = 'broadcast'`. With the conversations table removed, broadcasts get their own lightweight table.

**Broadcasts remain in V2** with this simplified standalone model (replaces the conversation-based approach):

```
broadcasts
----------
id (PK, UUID)
school_id (FK -> schools)
sender_id (FK -> users)               -- admin who sent it
route_id (FK -> routes, nullable)     -- null = all parents in school
                                      -- non-null = parents on specific route only
title (VARCHAR 200)
body (TEXT, max 2000 chars)
created_at (TIMESTAMPTZ)

INDEX: (school_id, created_at DESC)
INDEX: (route_id)
```

**Broadcast API (unchanged endpoints, same behavior):**

```
KEEP: POST   /api/v1/broadcasts      # Admin sends broadcast to route or all parents
KEEP: GET    /api/v1/broadcasts      # List broadcasts (admin: sent; parent: received for their routes)
```

**Broadcast delivery mechanism:**
- Socket.IO event `"broadcast"` emitted to route room (if route_id specified) or school-wide room (if null)
- Also creates `notification_log` entries per recipient parent for persistence in the in-app notification center
- One-way only: no replies, no threads, no conversations

**Broadcast Socket.IO event (new, replaces chat_message for broadcast use case):**

```
# Server -> Client (NEW)
"broadcast"    {broadcast_id, title, body, route_id, sender_name, created_at}
```

#### Complaints System (V2) -- KEEP as-is

CHANGE 7 from Revision 2 (complaints table, 5 endpoints, status tracking) remains completely unchanged. Complaints serve the "I need to report a formal issue" use case. They are form-based, not chat-based.

#### Alerts System -- KEEP as-is

Safety alerts (child_not_boarded, child_not_dropped) and operational alerts (route_deviation, SOS, incident) are unaffected by this change.

---

### ADD

#### 1. School setting: driver phone visibility

Add key to `schools.settings` JSONB (replaces removed chat flags):

```
schools.settings JSONB -- add key:
  "driver_phone_visible": true | false   (default: false)
```

- `false` (default): parent cannot see driver's phone number at all
- `true`: parent sees driver's phone number during active trips only

#### 2. API change: extend trip response with driver phone

Modify the response of existing endpoints to conditionally include driver phone. No new endpoints needed.

**`GET /api/v1/trips/{id}` (existing endpoint, extended response):**

When requester role = parent AND trip.status = 'in_progress' AND school.settings.driver_phone_visible = true:

```json
{
  "...existing trip fields...",
  "driver": {
    "name": "Ramesh Kumar",
    "phone": "+919876543210"
  }
}
```

When any condition is false, `driver.phone` is `null`.

**`GET /api/v1/parents/dashboard` (V2 multi-child endpoint, same logic):**

```json
{
  "children": [
    {
      "...existing fields...",
      "active_trip": {
        "...existing fields...",
        "driver": {
          "name": "Ramesh Kumar",
          "phone": "+919876543210"
        }
      }
    }
  ]
}
```

Note: both endpoints use `driver: { name, phone }` nested object — consistent convention.

**Conditional logic (service layer, ~15 lines in `app/tracking/services.py`):**

```
def get_driver_phone_for_parent(trip, school, requesting_user, db) -> str | None:
    """Return driver phone only during active trip with school permission."""
    if trip.status != 'in_progress':
        return None
    if not school.settings.get('driver_phone_visible', False):
        return None
    phone = trip.driver.phone   # from users.phone column (already exists)
    if phone:
        # Audit log: every phone disclosure recorded
        db.add(AuditLog(
            school_id=school.id,
            user_id=requesting_user.id,
            action="driver_phone_viewed",
            entity_type="trip",
            entity_id=trip.id,
        ))
    return phone
```

Audit log uses existing `audit_logs` table — no new table needed.

#### 3. Frontend: driver phone card on parent tracking view

On the existing parent live tracking map screen:

```
When active trip has driver_phone != null:
  - Show card below/above map: "Driver: Ramesh Kumar" with phone icon button
  - Phone number display: "98765 ***10" (masked -- show first 5 + last 2 digits)
  - Tap phone icon -> native tel: link (tel:+919876543210) -> opens phone dialer
  - Card only visible during active trip (disappears when trip ends/not started)

When driver_phone is null (school disabled OR trip not active):
  - Show nothing -- no empty card, no "phone hidden" message
```

#### 4. Admin settings UI addition

On the existing Admin -> School Settings page:

```
Toggle: "Show driver phone to parents during active trips"  [ON/OFF]
Helper text: "When enabled, parents can see the assigned driver's phone number
              and tap to call while the trip is in progress."
Default: OFF
```

---

## 3. Impact on Revision 2 Changes

| Revision 2 Change | Impact |
|--------------------|--------|
| CHANGE 1 (Logging) | No impact |
| CHANGE 2 (Child not-boarded) | No impact |
| CHANGE 3 (Task breakdown for safety) | Remove chat sub-task from Step 10 |
| CHANGE 4 (Substitute driver) | No impact |
| CHANGE 5 (Multi-child dashboard) | Add driver_phone field to response |
| CHANGE 6 (Feedback & rating) | No impact |
| CHANGE 7 (Complaints) | No impact -- complaints REPLACE chat for async issues |
| CHANGE 8 (Compliance reports) | No impact |
| CHANGE 9 (Feature list consolidation) | Remove V8 from V2 list |
| CHANGE 10 (Monitoring) | No impact |
| CHANGE 11 (Edge cases) | No impact |
| CHANGE 12 (Guardrails) | Update phone exposure guardrail |

---

## 4. Files Affected Summary

| Area | Removed | Added/Modified |
|------|---------|----------------|
| **DB tables** | conversations, conversation_participants, messages (3 removed) | broadcasts (1 new lightweight table, V2) |
| **DB indexes** | 3 indexes removed | 2 indexes added (broadcasts) |
| **API endpoints** | 5 chat endpoints removed | 0 new endpoints (trip response extended, broadcasts already planned) |
| **Socket.IO events** | chat_message (x2), typing (x2) = 4 types removed | broadcast (1 new) |
| **Code directories** | app/chat/ eliminated | No new directories |
| **School settings** | chat_enabled, driver_direct_chat removed | driver_phone_visible added |
| **Service layer** | Chat service eliminated | ~10 lines: get_driver_phone_for_parent() |
| **Frontend components** | Chat UI (inbox, thread, typing indicator) eliminated | Driver phone card (1 small component), admin settings toggle |
| **Guardrails** | "No direct phone exposure" removed | "Phone visible only during active trip with admin opt-in" added |

**Net complexity change: significant reduction.**
- Removed: 3 tables, 3 indexes, 5 endpoints, 4 Socket.IO event types, entire chat UI
- Added: 1 lightweight table (broadcasts), 2 indexes, 1 Socket.IO event, 1 school setting, ~10 lines backend logic, 1 small frontend component

---

## 5. Updated Guardrails (delta only)

### Must Have (add)

```
- Driver phone number visible to parents ONLY during active trips AND only if school.settings.driver_phone_visible = true
- Phone number masked in UI display (show partial digits), full number only in tel: href for dialer
- Broadcasts are one-way (admin -> parents), no reply capability
```

### Must NOT Have (update)

```
REMOVE: "No direct phone number exposure between parent and driver"
ADD:    "No driver phone exposure outside of active trips or without admin opt-in"
ADD:    "No two-way in-app messaging (chat removed; use complaints for async, phone for urgent)"
```

---

## 6. Updated Edge Cases (delta only)

| Edge Case | Mitigation |
|-----------|------------|
| **Driver doesn't want phone shared** | School setting defaults to OFF. Admin must explicitly enable. If individual driver opt-out is needed (future), add `users.phone_visible` boolean -- but not for MVP. |
| **Parent calls driver during non-trip hours** | Phone number only shown during active trip. Once trip ends, number disappears from UI. Parent already has it in call history -- this is acceptable (same as receiving a delivery driver's number). |
| **Driver has no phone number on file** | `users.phone` is nullable. If null, driver_phone returns null, card not shown. Admin should ensure drivers have phone numbers entered. |
| **School disables phone mid-trip** | Setting change takes effect on next API call. Parent's currently displayed number remains until page refresh. Acceptable edge case -- no real-time revocation needed. |

---

## 7. Open Questions (Revision 3)

- [ ] **Individual driver phone opt-out?** -- Current design is school-level toggle only. Should drivers be able to individually opt out? Adds a `phone_visible` column to users table. Recommend: defer to post-launch if drivers actually complain. School-level toggle is sufficient for MVP.
- [ ] **Should broadcasts be MVP or V2?** -- Broadcasts are low-effort (1 lightweight table, 1 Socket.IO event). Could be promoted to MVP Phase 2 alongside safety features. Current plan keeps them in V2.
