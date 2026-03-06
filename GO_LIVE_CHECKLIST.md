# ChatSCD Go-Live Checklist

Status legend:
- [ ] Not started
- [~] In progress
- [x] Done

## 1) Observability & Session Tracking (P0)
- [x] Add request-level tracing table and logging for `/api/query` + `/api/lesson-plan`
- [x] Capture status, latency, model/provider, session/user/anon identifiers
- [x] Capture token + cost metrics accurately (provider-native where available, estimated fallback retained)
- [x] Add basic admin dashboard stats (24h totals, success/error rate, p95 latency)
- [x] Add error breakdown + top failure reasons

## 2) Abuse & Operational Safeguards (P0)
- [x] Anonymous gating with daily quota + burst limits
- [x] Add optional challenge flow (Turnstile/hCaptcha) for suspicious traffic
- [x] Add alerting for spike conditions (error burst / traffic burst / cost surge)
- [x] Document emergency runbook + kill switches

## 3) Product Trust Surface (P0)
- [x] Privacy policy page
- [x] Terms page
- [x] Data retention + deletion policy note in app
- [x] Clear contact/support path

## 4) Feedback Loop (P1)
- [x] Add thumbs up / thumbs down per assistant response
- [x] Store feedback with session + model metadata
- [x] Add optional reason tags for thumbs down
- [x] Add admin review view for feedback trends

## 5) Monetization Starter (P1)
- [x] Add donation/support link in UI
- [x] Track donation link click-throughs
- [x] Add lightweight copy explaining cost support

## 6) Growth & Reliability (P1/P2)
- [x] Uptime checks + alerting
- [x] Release checklist for deploy/rollback
- [x] Changelog + status updates flow
- [x] Subscription model design (plans, quotas, billing hooks)
