# Growth layers — implementation and integration

Run `python3 start.py`, register, publish a listing, then open `/growth`.
The dashboard's Campaigns and Deskter Ads sections link to this workspace.
These layers use the existing session cookie and SQLite connection lifecycle.
`growth.sql` is an additive, repeatable migration recorded as schema version 2.

## Campaigns and commissions

- POST `/api/campaigns`: `listing_id`, `title`, `ends` (UTC epoch seconds),
  `request_key`. Starts immediately; ends within 366 days. Only a published,
  owned listing is eligible. The campaign tracks marketing activity; creating
  one does not launch external ads or reserve sponsored inventory.
- GET `/api/growth`: the signed-in user's campaigns, reports, boost requests,
  and current Pro entitlement. No other seller's private records are returned.
- POST `/api/campaign-reports`: `campaign_id`, `month` (`YYYY-MM`), `gross`,
  `refunds`. Money is integer PHP centavos. Only completed UTC months that
  overlap the campaign are accepted. Revenue must be attributable to that
  campaign, not the seller's entire business. Each sale should be reported once.
- Commission = round-half-up((gross - refunds) * basis_points / 10000).
  `DESKTER_COMMISSION_BPS` defaults to 400 (4%); valid range is 300–500.
  This is a configurable implementation default, not a finalized public rate.
  The rate is snapshotted at campaign launch. Later configuration changes do
  not change existing campaigns or reports.
- One immutable report per campaign/month. Exact retries return the existing
  record; changed amounts return 409. A receivable is marked `reported_unpaid`.
  No money is deducted, no payment is claimed, and no payout is calculated.
- Reporting is self-declared: verification, cross-campaign attribution,
  correction/adjustment ledgers, late refunds, tax treatment, invoicing,
  settlement, and disputes still require implementation before real billing.

## Boosts and discovery

- POST `/api/boosts`: `listing_id`, `tier` (1–3), `days` (1–30), `request_key`.
  Creates a **pending** request only. Client status/payment flags are ignored.
- Trusted activation uses the operator command below, never a public route.
- `/api/state` ranks eligible active boosts by maximum tier per listing, then
  listing creation time and ID. Overlapping boosts do not multiply exposure.
  Eligibility is recalculated at request time: start inclusive, expiry exclusive.
  Archived/private listings cannot enter the public feed. The UI labels active
  boosted listings **SPONSORED**. Search and category filters still apply;
  explicit newest/price sorts take precedence over promotion ranking.
- No checkout, ad auction, budget pacing, impression/click billing, guaranteed
  delivery, tracking, refund logic, or external ad-network integration exists.
  A current page must refresh to see expiry/ranking changes.

## Pro access

- `pro_feature` checks database subscription plan, status, start, and end on
  every protected request, after session authentication. No client account
  flags or browser storage can grant access.
- GET `/api/pro/analytics`: owned-listing saves/inquiries/closed-inquiry counts.
  These are not conversion, impression, attribution, or sales metrics.
- POST `/api/pro/bulk-archive`: `ids` (1–100). Entire request fails if any ID is
  inaccessible. Archiving is reversible through normal listing editing.
- Free users retain normal listing management and basic dashboard counts.
- Expired or revoked subscriptions fail closed. Subscription checkout,
  renewals, cancellations through customer UI, and grace-period policy remain
  unimplemented. There is no promise of unlimited API/resource usage.

## Operator workflows — development and reviewed grants

Run only with trusted local database access. Never expose this tool over HTTP.
Examples (substitute real IDs; references must be unique):

```sh
python3 growth_admin.py grant pro 1 --days 30 --reference test-pro-001 --actor operator
python3 growth_admin.py grant boost 1 --days 7 --reference test-boost-001 --actor operator
python3 growth_admin.py revoke boost 1 --reference revoke-boost-001 --actor operator
python3 growth_admin.py revoke pro 1 --reference revoke-pro-001 --actor operator
```

Pro grants target a **user ID**; Pro revocation targets a **subscription ID**.
Boost grants/revocation target a **boost ID**. Boost duration must match the
request. A unique reference prevents replayed approvals. Failed operations roll
back, including audit insertion failures. Grants are operator authorizations,
not payment receipts. Future signed, verified payment webhooks must validate
provider event identity, amount, currency, product and refund/revocation state
before invoking an entitlement service. Do not trust payment success redirects.

## Validation and release limits

Run `python3 check.py`. Growth tests cover rate rounding/snapshots, owner
isolation, duplicate reports, invalid periods, pending boosts, expiry/ranking,
archived visibility, Pro bypass attempts, bulk atomicity and grant rollback.
The growth workspace is server-only, not part of the standalone local demo.
Browser acceptance, accessible interaction review, deployment hardening and
provider test-mode payment acceptance remain release gates. Python's development
HTTP server is unchanged. This release is not certified production-ready.
