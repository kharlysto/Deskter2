-- Additive migration. Revenue is self-reported, not a payment ledger.
CREATE TABLE IF NOT EXISTS campaigns(
 id INTEGER PRIMARY KEY, owner INTEGER NOT NULL REFERENCES users(id),
 listing_id INTEGER NOT NULL REFERENCES listings(id), title TEXT NOT NULL,
 starts INTEGER NOT NULL, ends INTEGER NOT NULL CHECK(ends>starts),
 commission_bps INTEGER NOT NULL CHECK(commission_bps BETWEEN 300 AND 500),
 request_key TEXT NOT NULL, UNIQUE(owner,request_key));
CREATE TABLE IF NOT EXISTS transactions(
 id INTEGER PRIMARY KEY, campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
 month TEXT NOT NULL, gross INTEGER NOT NULL CHECK(gross>=0),
 refunds INTEGER NOT NULL CHECK(refunds>=0 AND refunds<=gross),
 commission_bps INTEGER NOT NULL CHECK(commission_bps BETWEEN 300 AND 500),
 commission_due INTEGER NOT NULL CHECK(commission_due>=0),
 status TEXT NOT NULL DEFAULT 'reported_unpaid' CHECK(status='reported_unpaid'),
 created INTEGER NOT NULL, UNIQUE(campaign_id,month));
CREATE TABLE IF NOT EXISTS boosts(
 id INTEGER PRIMARY KEY, owner INTEGER NOT NULL REFERENCES users(id),
 listing_id INTEGER NOT NULL REFERENCES listings(id),
 tier INTEGER NOT NULL CHECK(tier BETWEEN 1 AND 3), days INTEGER NOT NULL CHECK(days BETWEEN 1 AND 30),
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','active','revoked')),
 starts INTEGER, ends INTEGER, request_key TEXT NOT NULL, created INTEGER NOT NULL,
 CHECK(status!='active' OR (starts IS NOT NULL AND ends IS NOT NULL AND ends>starts)), UNIQUE(owner,request_key));
CREATE TABLE IF NOT EXISTS subscriptions(
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 plan TEXT NOT NULL DEFAULT 'deskter_pro' CHECK(plan='deskter_pro'),
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','revoked')),
 starts INTEGER NOT NULL, ends INTEGER NOT NULL CHECK(ends>starts), reference TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS growth_audit(
 id INTEGER PRIMARY KEY, kind TEXT NOT NULL, target INTEGER NOT NULL,
 reference TEXT UNIQUE NOT NULL, actor TEXT NOT NULL, created INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS campaign_owner ON campaigns(owner,id);
CREATE INDEX IF NOT EXISTS boosts_delivery ON boosts(status,starts,ends,listing_id);
CREATE INDEX IF NOT EXISTS boosts_owner ON boosts(owner,id);
CREATE INDEX IF NOT EXISTS subscriptions_access ON subscriptions(user_id,status,starts,ends);
