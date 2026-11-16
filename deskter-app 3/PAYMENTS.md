# PayMongo test checkout integration

This integration uses PayMongo **v2 Hosted Checkout** (`POST /v2/checkout_sessions`).
The server sets PHP prices in centavos from its own listing or configured Pro
price. It offers `card,gcash,qrph` by default, configurable with
`PAYMONGO_METHODS`; the provider shows only methods enabled for the merchant.

**Current build only accepts `sk_test_` keys. No live money is processed.**
The merchant account, domain/HTTPS, business approval, payouts, refund rules,
and provider test event acceptance are not yet set up.

## Test setup

Set these environment variables in the server environment (not in browser
code, documentation commits, messages, or client requests):

```text
PAYMONGO_SECRET_KEY=sk_test_<your-secret>
PAYMONGO_WEBHOOK_SECRET=<endpoint-signing-secret>
DESKTER_PUBLIC_ORIGIN=https://<your-public-test-origin>
DESKTER_PRO_30D_CENTAVOS=<an-approved-PHP-price-in-centavos>
PAYMONGO_METHODS=card,gcash,qrph
```

Values above are placeholders, not credentials or a proposed rate card. The
app does not read `.env` automatically. The Pro price must be set explicitly,
and must be at least 2000 centavos. A localhost origin is allowed for local
mock tests but is **not reachable by PayMongo** for webhook deliveries.
Register `https://<origin>/webhooks/paymongo` on the PayMongo **test**
dashboard for `checkout_session.payment.paid` and use that endpoint's signing
secret (different from the API key). Use an HTTPS tunnel or test deployment
for a real provider test. No webhook should be configured on a static host.

1. Start Deskter with the existing launcher; sign in, publish a one-time
   Product, Course, or Service. Another account can open that listing's details
   and select Test checkout, or visit `/orders` and enter its listing ID.
2. POST `/api/checkout` with `{"kind":"listing","listing_id":123,
   "request_key":"unique-client-request-id"}`. For Pro use `{"kind":"pro",
   "request_key":"unique-client-request-id"}`. The response has `order_id`,
   `checkout_url`, and `status`; redirect the browser to the provider URL.
3. PayMongo redirects to `/orders?order=<id>` after checkout or cancellation.
   This page only displays the database order state. **Redirect is never proof
   of payment**. An order stays pending until the signed provider event arrives.
4. After an authenticated `checkout_session.payment.paid` event, the server
   checks session ID, reference, exact PHP amount, event mode, paid payment ID,
   and event signature. The order and one purchase or Pro grant are recorded in
   one transaction. Webhook replay and duplicate provider requests are deduped.

`GET /api/orders` returns only the signed-in buyer's order history. `purchases`
records a paid Product, Course, or Service. A course purchase marks an
enrollment record active and unlocks seller-authored text lessons or approved
externally hosted direct videos. Video hosting and private delivery are not
included; no download is granted by the app.
Service delivery still needs seller fulfillment. A Pro purchase grants 30
days of access and expires; **it is not an automatically renewing subscription**.
One-time listing checkout does not support monthly/yearly listing pricing.
Boost purchases, seller settlement,
refunds, disputes, cancellation, and taxes are not implemented here.

The checkout uses an `Idempotency-Key` derived from a committed order ID and
reuses it on provider retries; the buyer request key also prevents duplicate
orders. Orders and webhook event IDs are unique in SQLite. Failed webhook
processing rolls back, allowing retry. Genuine unknown/mismatched events
return a non-2xx response for reconciliation rather than falsely activating
an order. Set up webhook monitoring and reconciliation before live use.

Run `python3 check.py` for mock provider and signed webhook integration tests.
Real PayMongo test dashboard validation, HTTPS, production hosting/security,
merchant onboarding, access-control review, browser tests, settlement and
refund handling remain required before permitting `sk_live_` keys.
