# Deskter — working local foundation

Read START-HERE.md for the launchers. Alternatively run `python3 server.py` with Python 3.12+ and open http://127.0.0.1:8000 for the landing page; the dashboard is at `/app`.
No installation or external dependencies are required. SQLite is created automatically.
Set DESKTER_DB to choose another database location. Do not commit the database.

## One frontend, two explicit modes

- **Server mode:** run the command above. Real local accounts, permissions, and SQLite persistence are used.
- **Local preview:** open `index.html` directly, or visit `http://127.0.0.1:8000/app?preview=1`. The same frontend uses demo accounts and a browser-local data store. A banner identifies this mode. No real authentication, payments, or backend writes occur. If storage is blocked, changes last only for the current page session and the banner says so. Use Switch account to test both seller and buyer workflows. Browser-local preview data does not migrate into the server database.

To create an asset, choose **Add an asset**, complete the title/description/category and pricing fields, then choose **Save draft** or **Publish asset**. Edit existing assets with **Save changes** and the Visibility selector. Price input accepts plain amounts, properly grouped commas, and optional PHP/₱ prefixes. Validation errors keep the form and entered values available for correction.

Additional frontend checks: `node tests/forms.cjs` and `node tests/network.cjs`. Form tests execute the actual submit handler through a minimal DOM adapter. They verify draft/publication/archival, free and formatted prices, invalid-input recovery, persistence, duplicate-submit guards, and storage-blocked behavior. They do not replace native-browser acceptance testing.

This implements the screenshot's light/purple dashboard direction, reconstructed geometric logo, original navigation sections, responsive layout, account registration/sign-in/sign-out, seller-owned listing creation/editing, discovery/search/category/price sorting, persistent saves/follows, customer inquiries, seller lead status updates, and database-backed activity counts.

The original uploaded Ethos source remains separate and unchanged. This is a new app, not a recovered version of the missing launchpad prototype. The logo is recreated from the screenshot; replace it with the original SVG when available.

## Verify

`python3 -m unittest discover -s tests -v`

Create a seller account, publish a listing, then use a separate browser profile to create a buyer. Send an inquiry, save the listing, and follow the seller. Return to the seller's Leads screen to respond by changing status. Reload to verify persistence.

## Current boundaries

This is a local development foundation, not a production-ready marketplace. It listens only on 127.0.0.1. It uses scrypt password hashing, opaque expiring HTTP-only sessions, SameSite cookies, origin checks, parameterized queries, escaped display content, and ownership checks. No real payment or email is sent. Account email is not verified; password reset, login throttling, abuse controls, production HTTPS/Secure cookies, moderation, backup operations and monitoring must precede public deployment. Profile editing, uploads, digital fulfillment, subscription billing, ads, payouts, verified reviews and messaging replies remain unimplemented. Admin Center is an informational placeholder, not an administrative permission.

Discover shows real published database records; an empty database has an actionable empty state. New assets default to private drafts. Set Visibility to Published in the asset editor to show them in Discover. Owners can edit, archive, or republish assets. Publishing means creating a marketplace listing; it does not deploy a hosted application or upload downloadable files. Production still needs a moderation policy.

Pricing supports one-time, monthly, yearly, starting-at, free, and request-a-quote displays in PHP. Amounts are stored as integer centavos. Recurring rates are labels only; billing is not connected. Quote-based listings are excluded from numeric maximum-price filters and placed last in low-price sorting. Authentication resumes interrupted creation, contact, save, and follow actions. Editing the profile updates the public seller display name.

Additional pricing checks: `node tests/pricing.cjs` (Node.js required for this optional test only).

UI logic checks: `node tests/ui.cjs`. This executes the frontend render functions with a minimal DOM adapter; it does not check browser layout, native dialogs, or click behavior.

Click an asset title to read its full description. Click its seller name to view that seller's published assets. Leads contains both received and sent inquiries. A seller can save or edit a response; the buyer can read it in Sent inquiries after refreshing. This is one editable response per inquiry, not a multi-message chat or email notification system.

For an existing installation, stop the app and back up your SQLite file before upgrading. Copy updated source files without replacing the database, then restart `python3 server.py`. Startup adds missing pricing/status/reply columns without deleting existing records.

## Before committing

Copy this folder's contents into a feature branch of the correct repository. Review and run the tests; do not overwrite unrelated repository work. Commit only source, documentation, and tests. No remote repository was connected or changed by this delivery.

## Next decisions

Choose launch categories and whether the first release is quote-first or checkout-first. This build implements quote-first. Decide seller review/verification rules, launch geography, payment provider eligibility, refund policy, and platform fees before commerce. Advertising needs a pricing and measurement contract; Pro needs a defined entitlement list. The older illustrative 8% and 20% rates are not implemented pricing.
# Growth workspace update

After starting the app, open `/growth` (or use Campaigns / Deskter Ads in the
dashboard). See [GROWTH.md](GROWTH.md) for campaign reporting, commission tracking,
boost requests, trusted operator grants, Pro access and implementation limits.
The standalone preview does not include these server-backed features.

# Payments update

`/orders` offers PayMongo test-mode checkout for eligible one-time Products,
Courses, Services and 30-day Deskter Pro. Read [PAYMENTS.md](PAYMENTS.md) for
configuration, webhook setup, what purchase records mean, and release limits.

# Learning, earnings, and reviews update

Course sellers build modules and text or approved externally hosted video
lessons at `/course`. Paid buyers reach their lessons and progress from
`/orders`. Verified buyers can review their purchased listings; published
listing ratings appear in discovery and the detail dialog. Sellers can inspect
illustrative test-mode sales and commission at `/earnings`. See
[COMMERCE.md](COMMERCE.md) for the exact permission rules and limitations.

