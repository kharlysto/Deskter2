# Courses, reviews, and seller sales · test release

Run `python3 start.py` and visit `/app`. Course creators publish a one-time
Course listing, open its detail dialog, and select **Build course**. Add a
module and at least one lesson before checkout becomes available. Text lessons
are stored in SQLite. For video lessons, set `DESKTER_VIDEO_HOSTS` to a
comma-separated list of exact, trusted hostnames; the seller must provide a
direct HTTPS `.mp4` or `.webm` URL on one of those hosts. No upload or private
video streaming is provided. URL holders may be able to view media outside
Deskter. Do not place confidential media on public hosts.

Another signed-in account buys the course through PayMongo **test** checkout.
Only a verified, signed `checkout_session.payment.paid` event creates the
purchase. The buyer opens `/orders`, then **Watch course**, and marks lessons
complete. Access checks and progress are enforced by the server. Sellers can
preview their own course; other accounts receive a permission error.

Paid buyers can select **Leave a verified review** from `/orders` or open a
listing's review link. A buyer may write one review per purchased listing and
revise its text and 1–5 stars later. Reviews and aggregates appear publicly
on published listing details and discovery. No seller-authored review bypass
exists. Refund and dispute revocation has not been added yet.

The **Earnings** header link opens `/earnings`. Only the seller's signed paid
listing test orders count. Commission is snapshotted at checkout, in integer
basis points (`DESKTER_SALES_COMMISSION_BPS`, default 400 = 4%, allowed 300–500),
rounded once per order in PHP centavos. Gross less that commission is displayed
as illustrative *owed*, not transferred funds. Existing paid orders without a
commission snapshot are marked for manual review and excluded from the known
net total. Pro purchases, campaign self-reports, and pending orders never
count as seller sales. This does not reconcile provider fees, taxes, refunds,
chargebacks, or seller payouts. No bank transfer or payout operation exists.

API summary (all authenticated except public review GET):

| Endpoint | Purpose |
| --- | --- |
| `POST /api/course/modules`, `POST /api/course/lessons` | Seller authoring |
| `GET /api/course?listing_id=N` | Seller preview or paid buyer outline |
| `POST /api/course/progress` | Enrolled buyer completion |
| `GET /api/my-purchases` | Buyer paid listing access |
| `GET /api/seller/earnings` | Seller's paid sales and commission |
| `GET /api/reviews?listing_id=N`, `POST /api/reviews` | Public published reviews / verified buyer update |

Run `python3 check.py` for backend and frontend checks. Real provider test
events, browser testing, merchant onboarding, HTTPS, refund accounting, access
revocation, seller identity verification, private video delivery, and payouts
remain release gates before selling courses or collecting real payments.
