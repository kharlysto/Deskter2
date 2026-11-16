"""Growth domain. Amounts are PHP centavos; rates are integer basis points.

Reported revenue creates a receivable, never proof of payment. Trusted grants
must come from an operator or a future verified payment webhook, not clients.
"""
import calendar
import datetime as dt
import os
import re
import time
from functools import wraps
from pathlib import Path

class Error(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message

def integer(value, name, low=1, high=10**12):
    if type(value) is not int or not low <= value <= high:
        raise Error(400, 'Invalid ' + name)
    return value

def text(value, name, limit=120):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit:
        raise Error(400, 'Invalid ' + name)
    return value.strip()

def commission(amount, bps):
    """Half-up rounding once per monthly report, without floating point."""
    integer(amount, 'revenue', 0)
    integer(bps, 'commission rate', 300, 500)
    return (amount * bps + 5000) // 10000

def migrate(c):
    c.executescript((Path(__file__).parent/'growth.sql').read_text())
    c.execute('INSERT OR IGNORE INTO schema_migrations VALUES(2,?)', (int(time.time()),))

def has_pro(c, uid, now=None):
    now = int(time.time()) if now is None else now
    return bool(c.execute("SELECT 1 FROM subscriptions WHERE user_id=? AND plan='deskter_pro' AND status='active' AND starts<=? AND ends>?", (uid, now, now)).fetchone())

def pro_feature(fn):
    @wraps(fn)
    def wrapped(c, uid, *args, **kwargs):
        if not has_pro(c, uid):
            raise Error(403, 'Deskter Pro is required for this feature.')
        return fn(c, uid, *args, **kwargs)
    return wrapped

def owned_listing(c, uid, ident):
    integer(ident, 'listing id')
    row = c.execute('SELECT * FROM listings WHERE id=? AND owner=?', (ident, uid)).fetchone()
    if not row: raise Error(404, 'Listing not found')
    if row['status'] != 'published': raise Error(400, 'Publish the listing first')
    return row

def discovery(c, uid):
    now = int(time.time())
    return [dict(r) for r in c.execute('''
        SELECT l.*,u.name seller,COALESCE(b.tier,0) boost_tier,
               COALESCE(rv.review_count,0) review_count,rv.rating_average,
               CASE WHEN b.tier IS NULL THEN 0 ELSE 1 END sponsored
        FROM listings l JOIN users u ON u.id=l.owner
        LEFT JOIN (SELECT listing_id,MAX(tier) tier FROM boosts
                   WHERE status='active' AND starts<=? AND ends>?
                   GROUP BY listing_id) b ON b.listing_id=l.id AND l.status='published'
        LEFT JOIN (SELECT listing_id,COUNT(*) review_count,ROUND(AVG(rating),1) rating_average
                   FROM reviews GROUP BY listing_id) rv ON rv.listing_id=l.id
        WHERE l.status='published' OR l.owner=?
        ORDER BY boost_tier DESC,l.created DESC,l.id DESC
    ''', (now, now, uid or -1))]

def report(c, uid, data):
    ident = integer(data.get('campaign_id'), 'campaign id')
    campaign = c.execute('SELECT * FROM campaigns WHERE id=? AND owner=?', (ident, uid)).fetchone()
    if not campaign: raise Error(404, 'Campaign not found')
    month = data.get('month')
    if not isinstance(month, str) or not re.fullmatch(r'\d{4}-\d{2}', month):
        raise Error(400, 'Use a YYYY-MM reporting month')
    try:
        year, m = map(int, month.split('-'))
        start = dt.datetime(year, m, 1, tzinfo=dt.timezone.utc)
        end = start + dt.timedelta(days=calendar.monthrange(year, m)[1])
    except ValueError: raise Error(400, 'Invalid reporting month')
    if end.timestamp() > time.time(): raise Error(400, 'Report a completed UTC calendar month')
    if start.timestamp() >= campaign['ends'] or end.timestamp() <= campaign['starts']:
        raise Error(400, 'Month does not overlap the campaign')
    gross = integer(data.get('gross'), 'gross revenue', 0)
    refunds = integer(data.get('refunds', 0), 'refunds', 0, gross)
    fee = commission(gross-refunds, campaign['commission_bps'])
    old = c.execute('SELECT * FROM transactions WHERE campaign_id=? AND month=?', (ident, month)).fetchone()
    if old:
        if old['gross'] != gross or old['refunds'] != refunds:
            raise Error(409, 'This month was already reported with different amounts. Contact support for a correction.')
        return dict(old)
    tid = c.execute('''INSERT INTO transactions(campaign_id,month,gross,refunds,commission_bps,commission_due,created)
                       VALUES(?,?,?,?,?,?,?)''', (ident, month, gross, refunds, campaign['commission_bps'], fee, int(time.time()))).lastrowid
    return dict(c.execute('SELECT * FROM transactions WHERE id=?', (tid,)).fetchone())

@pro_feature
def analytics(c, uid):
    rows = [dict(r) for r in c.execute('''SELECT l.id,l.title,l.status,
       (SELECT COUNT(*) FROM saves s WHERE s.listing_id=l.id) saves,
       (SELECT COUNT(*) FROM leads a WHERE a.listing_id=l.id) inquiries,
       (SELECT COUNT(*) FROM leads a WHERE a.listing_id=l.id AND a.status='Closed') closed_inquiries
       FROM listings l WHERE l.owner=? ORDER BY l.id DESC''', (uid,))]
    return {'listings': rows, 'note': 'Database counts only; closed inquiries are not verified sales.'}

@pro_feature
def bulk_archive(c, uid, data):
    ids = data.get('ids')
    if not isinstance(ids, list) or not 1 <= len(ids) <= 100:
        raise Error(400, 'Choose between 1 and 100 listing IDs')
    for ident in ids: integer(ident, 'listing id')
    ids = sorted(set(ids))
    slots = ','.join('?' for _ in ids)
    count = c.execute(f'SELECT COUNT(*) FROM listings WHERE owner=? AND id IN ({slots})', (uid,*ids)).fetchone()[0]
    if count != len(ids): raise Error(404, 'One or more listings are not accessible; nothing was changed')
    c.execute(f"UPDATE listings SET status='archived' WHERE owner=? AND id IN ({slots})", (uid,*ids))
    return {'archived': ids}

def dispatch(c, uid, path, method, data):
    """Called only after the server resolves a valid session; no client user IDs."""
    now = int(time.time())
    if path == '/api/growth' and method == 'GET':
        return {'pro': has_pro(c, uid), 'commission_bps': configured_rate(),
                'campaigns': [dict(r) for r in c.execute('SELECT * FROM campaigns WHERE owner=? ORDER BY id DESC',(uid,))],
                'transactions': [dict(r) for r in c.execute('SELECT t.* FROM transactions t JOIN campaigns c ON c.id=t.campaign_id WHERE c.owner=? ORDER BY t.id DESC',(uid,))],
                'boosts': [dict(r) for r in c.execute('SELECT * FROM boosts WHERE owner=? ORDER BY id DESC',(uid,))]}
    if path == '/api/campaigns' and method == 'POST':
        owned_listing(c, uid, data.get('listing_id'))
        title = text(data.get('title'), 'campaign title')
        ends = integer(data.get('ends'), 'campaign end', now+60, now+366*86400)
        key = text(data.get('request_key'), 'request key', 80)
        old = c.execute('SELECT * FROM campaigns WHERE owner=? AND request_key=?', (uid,key)).fetchone()
        if old:
            if (old['listing_id'],old['title'],old['ends']) != (data['listing_id'],title,ends):
                raise Error(409, 'Request key was already used for different campaign details')
            return dict(old)
        ident = c.execute('INSERT INTO campaigns(owner,listing_id,title,starts,ends,commission_bps,request_key) VALUES(?,?,?,?,?,?,?)',
                          (uid,data['listing_id'],title,now,ends,configured_rate(),key)).lastrowid
        return dict(c.execute('SELECT * FROM campaigns WHERE id=?',(ident,)).fetchone())
    if path == '/api/campaign-reports' and method == 'POST': return report(c, uid, data)
    if path == '/api/boosts' and method == 'POST':
        owned_listing(c, uid, data.get('listing_id'))
        tier = integer(data.get('tier'), 'tier', 1, 3)
        days = integer(data.get('days'), 'duration', 1, 30)
        key = text(data.get('request_key'), 'request key', 80)
        old = c.execute('SELECT * FROM boosts WHERE owner=? AND request_key=?', (uid,key)).fetchone()
        if old:
            if (old['listing_id'],old['tier'],old['days']) != (data['listing_id'],tier,days):
                raise Error(409, 'Request key was already used for different boost details')
            return dict(old)
        ident = c.execute('INSERT INTO boosts(owner,listing_id,tier,days,request_key,created) VALUES(?,?,?,?,?,?)',
                          (uid,data['listing_id'],tier,days,key,now)).lastrowid
        return dict(c.execute('SELECT * FROM boosts WHERE id=?',(ident,)).fetchone())
    if path == '/api/pro/analytics' and method == 'GET': return analytics(c, uid)
    if path == '/api/pro/bulk-archive' and method == 'POST': return bulk_archive(c, uid, data)
    raise Error(404, 'Not found')

def configured_rate():
    try: rate = int(os.environ.get('DESKTER_COMMISSION_BPS', '400'))
    except ValueError: raise Error(500, 'Invalid server commission configuration')
    if not 300 <= rate <= 500: raise Error(500, 'Invalid server commission configuration')
    return rate

ROUTES = {'/api/growth','/api/campaigns','/api/campaign-reports','/api/boosts','/api/pro/analytics','/api/pro/bulk-archive'}

def grant(c, kind, target, reference, days, actor):
    """Trusted operator entry point. Call inside an IMMEDIATE transaction.

    References are unique across grants; replay is rejected (never extends time).
    This records operator authorization, not a payment receipt.
    """
    target = integer(target, 'target'); days = integer(days, 'days', 1, 366)
    reference = text(reference, 'reference'); actor = text(actor, 'actor')
    now = int(time.time())
    if kind == 'pro':
        if not c.execute('SELECT 1 FROM users WHERE id=?',(target,)).fetchone(): raise Error(404,'User not found')
        c.execute("INSERT INTO subscriptions(user_id,starts,ends,reference) VALUES(?,?,?,?)",(target,now,now+days*86400,reference))
    elif kind == 'boost':
        b = c.execute('SELECT * FROM boosts WHERE id=?',(target,)).fetchone()
        if not b or b['status'] != 'pending': raise Error(409,'Boost is not pending')
        owned_listing(c,b['owner'],b['listing_id'])
        if days != b['days']: raise Error(400,'Duration must match the requested boost')
        c.execute("UPDATE boosts SET status='active',starts=?,ends=? WHERE id=?",(now,now+days*86400,target))
    else: raise Error(400,'Invalid grant kind')
    c.execute('INSERT INTO growth_audit(kind,target,reference,actor,created) VALUES(?,?,?,?,?)',(kind,target,reference,actor,now))
