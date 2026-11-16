# Feature status — reliability revision

Payment revision: see PAYMENTS.md. `/orders` now supports PayMongo test-mode
hosted checkout for one-time eligible listings and fixed 30-day Pro access.
Signed paid events mark buyer orders and purchase records paid or grant Pro;
course text lessons and approved external direct videos are available to paid
buyers, and sellers see order-based commissions and amounts owed. There is no
live money movement, private video delivery, seller settlement, recurring
billing, refund flow, or real payment provider acceptance test yet.

Growth revision: `/growth` now provides campaigns, monthly revenue reporting,
boost requests and Pro tools. See GROWTH.md for exact API and release boundaries.

Integrated release adds `/`, `/login`, `/register`, `/plans`, `/app`, a launcher, database backup/integrity tools, authentication throttling, and password changes with session revocation. See RELEASE.md for the current release gate. Backend integration tests and five frontend check scripts run; browser acceptance is still outstanding.

Latest frontend revision: the same `index.html` now runs against either the real backend or a clearly labeled local-preview adapter. Asset-submit, storage, pricing, rendering, and transport-error logic have dedicated automated checks. Native-browser rendering remains blocked in the execution environment; no 100%-functional or production-ready claim is made.

| Area | Current behavior | Verification |
| --- | --- | --- |
| Accounts | Registration, login/logout, profile name editing, session expiry | API integration tests |
| Local preview | Demo account switching, asset saves, browser persistence, inquiries and replies | Adapter and actual form-handler tests; no real authentication |
| Assets | Draft/create/edit/publish/archive/republish | API and UI logic tests |
| Pricing | PHP one-time/month/year/from/free/quote | API and frontend tests |
| Discovery | Search, categories, maximum price, chronological/price sort | UI logic checks; manual browser pass needed |
| Saves and follows | Database-backed per-account relationships | API integration tests |
| Asset details | Full description and price dialog | UI logic test; manual browser pass needed |
| Seller view | Seller's published listing collection | UI logic test; manual browser pass needed |
| Inquiries | Buyer history, seller inbox, status updates, one editable seller response | API integration and UI render tests |
| Analytics | Actual listing and inquiry counts only | UI render check |
| Ads / Campaigns | Campaign tracking/reports and pending boost requests; operator-granted sponsored ranking | Ownership, retry, expiry, tier and visibility tests; no charging or event tracking |
| Pro | Database entitlement checks; per-listing counts and bulk archive | Bypass, expiry, revocation and ownership tests; no subscription billing or AI insights |
| Admin Center | Informational placeholder | No moderation/admin access implemented |
| Checkout and payouts | Test checkout code and signed webhook processing; seller sales estimates at `/earnings`, no actual seller payouts | Mock provider integration tests; actual PayMongo account not connected |
| Courses | Seller creates modules, text lessons or approved direct video links; verified buyers track lesson progress | API integration tests; private media hosting unavailable |
| Reviews | One editable star review per paid buyer per published listing; ratings in discovery and details | Purchase and rating permission tests |
| Uploads and delivery | Unavailable | Listing publication does not upload or deliver a file |
| Production operations | Not ready | Requires HTTPS, abuse/rate controls, account recovery/verification, moderation, backup/monitoring and hosting |

## Manual acceptance pass still required

Run the app, register a seller, create a draft and confirm it is hidden in an independent buyer session. Publish and verify the exact price, detail view and seller collection. Have the buyer save, follow and send an inquiry. Reply as the seller; refresh the buyer's Leads page to read the reply. Edit and archive the asset; confirm public visibility and Saved counts. Repeat at phone width and with keyboard navigation. Confirm data survives a server restart.

No claim of zero bugs or production readiness is made. Do not merge into main or expose this development server publicly on the basis of these automated tests alone.
