# Integrated local release

## Learning, earnings, and reviews revision

See COMMERCE.md. Seller-authored text lessons and approved external direct
video links are accessible to paid course buyers; buyer completion persists.
Verified paid buyers may edit their own reviews, with listing aggregates in
discovery and details. Sellers can inspect paid **test** sales, snapshotted
commission, and illustrative unpaid net amounts. No live seller payouts or
refund accounting is implemented.

## PayMongo test checkout revision

See PAYMENTS.md. `/orders` creates PayMongo v2 test checkout sessions for
eligible one-time Products, Courses and Services or one-time 30-day Pro access.
Webhook signatures and exact server-owned amounts are checked before recording
paid orders. Provider onboarding, real payments, seller payouts, course hosting,
recurring subscriptions, refunds and production hosting are still outstanding.

## Growth revision

See GROWTH.md for the new server-only `/growth` workspace. Campaign creation,
immutable monthly revenue reports, commission receivables, pending boost
requests, operator-authorized sponsored ranking, and server-enforced Pro
analytics/bulk archiving are implemented. These supersede the older "Soon"
status for those specific capabilities. No payment collection, automatic billing,
campaign attribution or ad-event measurement has been added. Operator grants
are not payment confirmation. The configurable default commission is 4%,
snapshotted per campaign, pending final business approval.

## Delivered

The landing page, dedicated login and registration pages, plans information, and product dashboard share Deskter's purple/light identity. Free core functionality remains available. Pro and Boost are explicitly described as planned paid offerings without invented prices, fake checkout, or payment collection.

Backend/database work includes real local account sessions, listing ownership, private drafts, publication, price validation, saves/follows, buyer inquiries, seller replies, profile editing, authenticated password changes, and basic login-attempt throttling. SQLite has foreign-key checks, useful indexes, migration tracking, and a backup/check utility. Password changes revoke the account's other sessions. Secure cookies and an exact public origin can be configured for an HTTPS deployment.

Backend integration tests and five frontend check scripts cover pricing, rendering logic, actual form submit handlers through a minimal DOM adapter, transport errors, and dedicated account-page request/redirect behavior. They are not a native-browser acceptance pass. Browser rendering remains unverified because Chromium cannot start in this execution environment.

## Not approved for a public commercial launch

- The runtime still uses Python's development HTTP server and a single-file SQLite database. Production hosting/runtime, concurrency expectations, backup operations, monitoring, and recovery procedures require a deliberate deployment review.
- Pro and Boost pricing, payment-provider activation, recurring billing, cancellation/refund policies, sponsored placement delivery and trustworthy ad measurement are unresolved or unimplemented.
- Test-mode order checkout, signed payment events, and limited course lesson access are implemented; real fulfillment, refunds, and seller payouts remain unimplemented.
- Email verification, password recovery, stronger distributed abuse protection, protected moderation and reporting, and private uploads are unimplemented.
- Business registration/provider verification, final policy documents, a domain, email sender setup, and deployment credentials are owner-dependent.
- Native-browser tests across desktop/mobile, access-control review in the deployed environment, and payment-provider test-mode acceptance must pass before public launch.

No changes have been committed or pushed to a remote repository. Use a feature branch for review; do not present this build as zero-defect or fully production-ready.
