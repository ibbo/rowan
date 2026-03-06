# ChatSCD Subscription Model

## Goals

- Move from donation-first support to a simple, understandable paid tier without breaking current anonymous access.
- Keep the first rollout operationally safe: define plans, record billing/subscription state, and prepare quota hooks before enforcing limits.
- Preserve a migration path for existing donors and early testers.

## Proposed Plans

### Free

- Price: `$0`
- Audience: casual or first-time users
- Access:
  - Anonymous access stays available behind the existing daily/burst guardrails
  - Signed-in users get the same base product surface
- Proposed soft limits:
  - `150` chat queries per month
  - `12` lesson plans per month
- Notes:
  - Keep current anonymous daily quota in place until plan enforcement is turned on
  - Free remains the default seeded plan in SQLite

### Pro

- Price: `$9/month` to start
- Audience: teachers, class organizers, frequent planners
- Proposed limits:
  - `1500` chat queries per month
  - `80` lesson plans per month
- Proposed benefits:
  - Higher monthly quotas
  - Priority support/contact path
  - Eligible for future team/club billing once validated

## Billing Hooks And Events

These are the minimum events the app should be ready to record before connecting a live billing provider:

- `checkout_started`
- `checkout_completed`
- `checkout_failed`
- `subscription_created`
- `subscription_updated`
- `subscription_canceled`
- `subscription_renewed`
- `invoice_paid`
- `invoice_payment_failed`
- `donation_migrated_to_pro`

Recommended app-side hook points:

- User clicks upgrade CTA
- Billing provider redirect/webhook returns success or failure
- Subscription status changes on webhook replay
- Monthly quota window resets
- Manual admin comp or grandfathering adjustment

## SQLite Placeholder Hooks

Tonight's non-enforcing schema placeholders:

- `subscription_plans`
  - Seeded with proposed `free` and `pro` rows
  - Stores plan metadata and monthly quota targets
- `user_subscriptions`
  - Stores future billing provider identifiers and lifecycle status per user
- `usage_quotas`
  - Stores future quota counters/windows without enforcing them yet

These tables are intentionally additive. No request path should reject or downgrade traffic based on them until a later rollout.

## Migration Path From Donation Mode

1. Keep the existing donation CTA live while paid subscriptions are still inactive.
2. Add a signed-in upgrade CTA that can coexist with donations for one release.
3. Offer current donors a manual or coupon-based Pro migration path.
4. Record migrated users with `migrated_from_donation=1` in `user_subscriptions`.
5. Once paid checkout is stable, reduce donation copy from primary CTA to secondary support messaging.

## Phased Rollout Checklist

- [x] Define Free and Pro plans with initial quota targets
- [x] Add non-breaking SQLite placeholders for plan/subscription/quota state
- [x] Seed default plan rows for `free` and `pro`
- [ ] Add upgrade CTA and authenticated plan selection UI
- [ ] Add billing provider integration and webhook verification
- [ ] Persist billing events for audit/replay
- [ ] Start writing quota usage records from request completions
- [ ] Add admin view for subscription and quota state
- [ ] Enable soft-limit warnings only
- [ ] Enable enforced plan limits after one release of shadow traffic observation

## Open Questions

- Whether lesson plans should consume a separate quota pool or a weighted message budget
- Whether clubs/teachers need annual billing before individual Pro launches
- Whether donation supporters should receive permanent grandfathered pricing or time-boxed credits
