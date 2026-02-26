# SyntropyHealth Beta Release - Master PRD

## Vision

Syntropy is the Health OS for diet — the intelligence layer that connects food purchases, supplement protocols, and health metrics into personalized, actionable insight. Every wellness store uses us as their backend for customer retention. Every biohacker uses us as their single source of truth.

## Beta Success Criteria

| Metric | Target | Timeline |
|--------|--------|----------|
| Wellness store sign-ups | 1,000 | 3 months post-launch |
| Store 30-day retention | >30% active | Ongoing |
| End-user weekly active | TBD | Ongoing |
| Daily check-in rate | >60% of users, 5+ days/week | After first week |
| Insight engagement | >50% of users engage with insight cards | After PRD-05/06 ship |

---

## PRD Inventory (12 PRDs)

### Priority Tiers

| Tier | Definition | PRDs |
|------|-----------|------|
| **P0 - Foundation** | Must exist before anything else works | PRD-01, PRD-02, PRD-08 |
| **P1 - Core Value & Distribution** | Delivers the product value prop + enables SMB acquisition | PRD-03, PRD-04, PRD-05, PRD-06, PRD-07 |
| **P2 - Satellite & Agent** | Extends reach to other surfaces + conversational AI | PRD-09, PRD-10, PRD-11 |
| **P3 - Enhancement** | High-value but non-blocking for beta launch | PRD-12 |

### Complete PRD Table

| # | PRD | Component | Priority | Status | Depends On | File |
|---|-----|-----------|----------|--------|------------|------|
| 01 | Open Diet Data - Macro Calculation | `research/open-diet-data/` | P0 | complete | - | [01-open-diet-data-macro-calculation.prd.md](./01-open-diet-data-macro-calculation.prd.md) |
| 02 | DIET Service - API Stabilization & Rename | `apps/diet/` (submodule → [Syntropy-Health/diet](https://github.com/Syntropy-Health/diet)) | P0 | complete | - | [02-diet-service-api-stabilization.prd.md](./02-diet-service-api-stabilization.prd.md) |
| 03 | Journal - Branding & UX Overhaul | `apps/Syntropy-Journals/` | P1 | pending | - | [03-journal-branding-ux-overhaul.prd.md](./03-journal-branding-ux-overhaul.prd.md) |
| 04 | User Profile System (Public/Private/Shareable) | `apps/Syntropy-Journals/` | P1 | pending | - | [04-user-profile-system.prd.md](./04-user-profile-system.prd.md) |
| 05 | Journal ↔ DIET Integration | `apps/Syntropy-Journals/` + `apps/diet/` | P1 | pending | 02 | [05-journal-diet-integration.prd.md](./05-journal-diet-integration.prd.md) |
| 06 | Actionable Insights & Notifications | `apps/Syntropy-Journals/` + `apps/diet/` | P1 | pending | 05 | [06-actionable-insights-notifications.prd.md](./06-actionable-insights-notifications.prd.md) |
| 07 | SMB Onboarding & Affiliate Program | `apps/Syntropy-Journals/` | P1 | pending | 03, 04, 08 | [07-smb-onboarding-affiliate.prd.md](./07-smb-onboarding-affiliate.prd.md) |
| 08 | Referral System & PostHog Analytics | `apps/Syntropy-Journals/` (cross-cutting) | P0 | complete | - | [08-referral-system-analytics.prd.md](./08-referral-system-analytics.prd.md) |
| 09 | Chrome Shrine ↔ DIET Integration | `apps/chrome-shrine/` | P2 | pending | 01, 02 | [09-chrome-shrine-diet-integration.prd.md](./09-chrome-shrine-diet-integration.prd.md) |
| 10 | Syntropy Mobile - Check-in Polish | `apps/syntropymobile/` | P2 | pending | - | [10-syntropy-mobile-checkin.prd.md](./10-syntropy-mobile-checkin.prd.md) |
| 11 | OpenClaw Agent Integration | `apps/Syntropy-Journals/` + Mobile | P2 (Critical) | pending | 02, 04 | [11-openclaw-agent-integration.prd.md](./11-openclaw-agent-integration.prd.md) |
| 12 | Oura Ring & Wearable Integration | `apps/Syntropy-Journals/` | P3 | pending | 02, 04, 05 | [12-oura-wearable-integration.prd.md](./12-oura-wearable-integration.prd.md) |

---

## Dependency Graph

```
                    ┌─────────────────┐
                    │   PRD-08        │
                    │ PostHog/Referral│  (P0 - no deps, enables everything)
                    │   Analytics     │
                    └────────┬────────┘
                             │
    ┌────────────────────────┼──────────────────────┐
    │                        │                      │
    v                        v                      v
┌──────────┐          ┌──────────┐           ┌──────────┐
│ PRD-01   │          │ PRD-02   │           │ PRD-03   │
│ Open Diet│          │ DIET API │           │ Branding │
│ Macros   │          │ Stabilize│           │ UX       │
│ (P0)     │          │ (P0)     │           │ (P1)     │
└────┬─────┘          └──┬───┬───┘           └────┬─────┘
     │                   │   │                    │
     │                   │   │   ┌────────────────┤
     │                   │   │   │                │
     │                   v   │   v                v
     │             ┌──────────┐  ┌──────────┐  ┌──────────┐
     │             │ PRD-05   │  │ PRD-04   │  │ PRD-07   │
     │             │ Journal- │  │ User     │  │ SMB      │
     │             │ DIET     │  │ Profiles │  │ Onboard  │
     │             │ Integr.  │  │ (P1)     │  │ (P1)     │
     │             │ (P1)     │  └──┬───┬───┘  └──────────┘
     │             └────┬─────┘     │   │
     │                  │           │   │
     │                  v           │   │
     │             ┌──────────┐     │   │
     │             │ PRD-06   │     │   │
     │             │ Insights │     │   │
     │             │ Notifs   │     │   │
     │             │ (P1)     │     │   │
     │             └──────────┘     │   │
     │                              │   │
     │    ┌─────────────────────────┘   │
     │    │                             │
     v    v                             v
┌──────────┐    ┌──────────┐     ┌──────────┐
│ PRD-09   │    │ PRD-11   │     │ PRD-12   │
│ Chrome   │    │ OpenClaw │     │ Oura     │
│ Shrine   │    │ Agent    │     │ Wearable │
│ (P2)     │    │ (P2-Crit)│     │ (P3)     │
└──────────┘    └──────────┘     └──────────┘

    ┌──────────┐
    │ PRD-10   │  (P2 - independent, can start anytime)
    │ Mobile   │
    │ Check-in │
    └──────────┘
```

---

## Recommended Implementation Sequence

### Wave 1: Foundation (Weeks 1-3)
> Goal: Stable data layer and measurement infrastructure

| PRD | Work | Can Parallel | Team/Focus |
|-----|------|-------------|------------|
| **PRD-08** | PostHog setup, event taxonomy, referral attribution | Yes (all 3 parallel) | Cross-cutting |
| **PRD-01** | Open Diet Data macro calculation tools | Yes | Data/Backend |
| **PRD-02** | DIET service fix imports, rename, API contract | Yes | Backend |

**Why these first**: PRD-08 enables measurement for everything. PRD-01 and PRD-02 are blocking foundations — every downstream PRD needs them. All three have zero dependencies and can run in parallel.

**Wave 1 exit criteria**: PostHog capturing events, DIET API stable with OpenAPI spec, Open Diet Data returning structured macros.

---

### Wave 2: Core Product (Weeks 3-7)
> Goal: Syntropy-Journal delivers its core value proposition

| PRD | Work | Can Parallel | Team/Focus |
|-----|------|-------------|------------|
| **PRD-03** | Branding & UX overhaul, landing pages | Yes (with 04, 05) | Frontend/Design |
| **PRD-04** | User profile system (public/private/shareable) | Yes (with 03, 05) | Full-stack |
| **PRD-05** | Journal ↔ DIET integration (auto-analysis) | Yes (with 03, 04) | Backend + Frontend |

**Why these next**: PRD-05 delivers the "log → insight" loop that IS the core product. PRD-03 and PRD-04 make the product presentable and shareable. All three can run in parallel since they touch different domains (branding vs profiles vs analysis pipeline).

**Wave 2 exit criteria**: Users can log food → see personalized insight. Brand says "Health OS." Profiles are shareable.

---

### Wave 3: Distribution + Retention (Weeks 5-9)
> Goal: SMB acquisition engine and user retention mechanisms

| PRD | Work | Can Parallel | Team/Focus |
|-----|------|-------------|------------|
| **PRD-07** | SMB onboarding & affiliate program | Yes (with 06) | Full-stack |
| **PRD-06** | Actionable insights & notifications (in-app) | Yes (with 07) | Backend + Frontend |

**Why these next**: PRD-07 directly serves the 1,000-store goal. PRD-06 keeps users coming back. Both depend on Wave 2 outputs but can run in parallel with each other (different domains: SMB flows vs notification system).

**Wave 3 exit criteria**: Wellness stores can self-serve sign up. Users receive proactive insight notifications.

---

### Wave 4: Extend Reach (Weeks 7-11)
> Goal: Multi-surface presence and conversational agent

| PRD | Work | Can Parallel | Team/Focus |
|-----|------|-------------|------------|
| **PRD-11** Phase 1 | OpenClaw technical discovery spike | Yes (start early, even in Wave 2) | Backend/AI |
| **PRD-11** Phases 2-5 | OpenClaw full integration | Yes (with 09, 10) | Backend/AI |
| **PRD-09** | Chrome Shrine ↔ DIET integration | Yes (with 10, 11) | Extension |
| **PRD-10** | Mobile check-in polish | Yes (with 09, 11) | Mobile |

**Why these next**: OpenClaw is critical/core — its discovery spike should start in Wave 2, with full integration in Wave 4. Chrome Shrine and Mobile extend the product to other surfaces. All three can run in parallel since they're different codebases (extension, mobile, agent).

**Wave 4 exit criteria**: Users can chat with health copilot in Journal + Mobile. Chrome Shrine shows personalized food scores. Mobile check-in is under 30 seconds.

---

### Wave 5: Enhancement (Weeks 9-12+)
> Goal: Close the feedback loop with wearable data

| PRD | Work | Can Parallel | Team/Focus |
|-----|------|-------------|------------|
| **PRD-12** | Oura Ring integration | Independent | Backend + Frontend |

**Why last**: High value but not blocking for beta distribution. Competes with OpenClaw for resources. If resources allow, Phase 1 (OAuth connection) can start in Wave 4.

**Wave 5 exit criteria**: Users with Oura see diet ↔ sleep/HRV correlation on dashboard.

---

## Resource Trade-off: OpenClaw vs More Integrations

| Factor | OpenClaw (PRD-11) | Oura + Wearables (PRD-12) |
|--------|-------------------|---------------------------|
| Impact on core experience | HIGH — conversational health copilot | MEDIUM — closes feedback loop |
| Impact on distribution | MEDIUM — differentiator, not direct acquisition | LOW — nice-to-have for biohackers |
| Technical risk | HIGH — depends on external service maturity | LOW — Oura API is well-documented |
| Resource cost | MEDIUM — integration, not building from scratch | MEDIUM — OAuth, sync, DIET updates |
| **Recommendation** | **Prioritize for beta** | **Fast-follow or parallel if resources allow** |

---

## Deferred / Out of Scope for Beta

| Feature | Reason | When to Revisit |
|---------|--------|-----------------|
| Protocol Copying | Non-priority per decision; social features after core value proven | Post-beta, after user profile adoption measured |
| Shopify Store Integration | Need to prove SMB model first with manual onboarding | After 100+ stores active |
| E-commerce / Checkout | We're intelligence layer, not a store | Only if SMBs demand it |
| HIPAA Compliance | Beta is consumer wellness, not clinical | If practitioner segment grows |
| Multi-wearable Support | Oura first; add Whoop/Apple Health based on demand | After PRD-12 proves value |
| Marketing Website | App IS the marketing for beta | If conversion requires separate landing |

---

## Cross-cutting Concerns

### Authentication (Clerk)
- **Current roles**: Admin, User, Guest
- **Beta additions**: Store (PRD-07), profile data separation (PRD-04)
- **Boundary**: Clerk owns identity + auth. App owns profile data, health data, permissions.

### Analytics (PostHog - PRD-08)
- All PRDs reference PostHog for metrics
- PRD-08 must ship first or in parallel with everything
- Event taxonomy defined once, used everywhere

### API Contracts
- DIET OpenAPI spec (PRD-02) is the contract all consumers code against
- Open Diet Data MCP tools (PRD-01) are the data contract
- Changes require versioning after beta launch

### Privacy
- Health data never on public profiles without explicit opt-in (PRD-04)
- PostHog events must not contain PII/PHI (PRD-08)
- OpenClaw data minimization — least PII possible (PRD-11)
- Oura OAuth scopes: request minimum necessary (PRD-12)

---

## Timeline Overview

```
Week:  1    2    3    4    5    6    7    8    9    10   11   12
       ├────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┤
Wave 1 ████████████                                           Foundation
       PRD-08 PostHog ██████
       PRD-01 Macros  ██████
       PRD-02 DIET    ██████
Wave 2            ████████████████                            Core Product
              PRD-03 Branding ████████████
              PRD-04 Profiles ████████████
              PRD-05 J↔DIET   ████████████
Wave 3                        ████████████████                Distribution
                    PRD-07 SMB ████████████
                    PRD-06 Notifs ██████████
Wave 4                              ██████████████████        Extend
                         PRD-11 OpenClaw ████████████████
                              PRD-09 Chrome ████████████
                              PRD-10 Mobile ████████████
Wave 5                                          ████████████  Enhancement
                                        PRD-12 Oura ████████
```

---

## How to Use This Document

### Starting implementation on a PRD:
```
/prp-plan .claude/PRPs/prds/{prd-filename}.prd.md
```
This will create an implementation plan for the next pending phase.

### Updating PRD status:
Edit the PRD table above, changing `pending` → `in-progress` → `complete`.

### Adding new PRDs:
Number sequentially (13, 14, ...), add to the table, update the dependency graph.

---

*Generated: 2026-02-25*
*Status: DRAFT - needs stakeholder review*
*Next action: Validate foundation assumptions, then start Wave 1 (PRD-01, PRD-02, PRD-08 in parallel)*
