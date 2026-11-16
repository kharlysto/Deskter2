-- Checkout sessions and grants are recorded separately from reported campaign receivables.
CREATE TABLE IF NOT EXISTS orders (
 id INTEGER PRIMARY KEY, buyer INTEGER NOT NULL REFERENCES users(id),
 kind TEXT NOT NULL CHECK(kind IN ('listing','pro','boost')),
 target_id INTEGER, listing_kind TEXT CHECK(listing_kind IN ('product','course','service')),
 title TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>0),
 currency TEXT NOT NULL DEFAULT 'PHP' CHECK(currency='PHP'),
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','paid','review')),
 request_key TEXT NOT NULL, session_id TEXT UNIQUE, checkout_url TEXT,
 payment_id TEXT UNIQUE, paid_at INTEGER, created INTEGER NOT NULL,
 UNIQUE(buyer,request_key));
CREATE TABLE IF NOT EXISTS webhook_events (
 event_id TEXT PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id), created INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS purchases (
 order_id INTEGER PRIMARY KEY REFERENCES orders(id), buyer INTEGER NOT NULL REFERENCES users(id),
 listing_id INTEGER NOT NULL REFERENCES listings(id), kind TEXT NOT NULL CHECK(kind IN ('product','course','service')),
 status TEXT NOT NULL DEFAULT 'active' CHECK(status='active'), created INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS orders_buyer ON orders(buyer,id);
CREATE INDEX IF NOT EXISTS purchases_access ON purchases(buyer,listing_id,status);
