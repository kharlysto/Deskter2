"""PayMongo v2 hosted checkout; test-mode-only until marketplace launch approval."""
import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.request
import commerce
from pathlib import Path
from urllib.parse import urlparse

class PaymentError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message

def migrate(c):
    c.executescript((Path(__file__).parent/'payments.sql').read_text())
    c.execute('INSERT OR IGNORE INTO schema_migrations VALUES(3,?)', (int(time.time()),))

def configured():
    key=os.environ.get('PAYMONGO_SECRET_KEY','')
    secret=os.environ.get('PAYMONGO_WEBHOOK_SECRET','')
    origin=os.environ.get('DESKTER_PUBLIC_ORIGIN','').rstrip('/')
    if not key or not secret or not origin:
        raise PaymentError(503,'Test checkout is not configured.')
    # Payment flows stay in test mode until the owner has a merchant account,
    # provider approval, and a separate production review.
    if not key.startswith('sk_test_'):
        raise PaymentError(503,'This build accepts PayMongo test credentials only.')
    u=urlparse(origin)
    if u.scheme!='https' and not (u.scheme=='http' and u.hostname in ('localhost','127.0.0.1')):
        raise PaymentError(503,'Configure an HTTPS public origin for checkout.')
    return key, secret, origin

def integer(value, field):
    if type(value) is not int or value < 1:
        raise PaymentError(400,'Invalid '+field)
    return value

def plan_price():
    try: amount=int(os.environ.get('DESKTER_PRO_30D_CENTAVOS','0'))
    except ValueError: amount=0
    if amount < 2000 or amount > 100000000:
        raise PaymentError(503,'Deskter Pro test price is not configured.')
    return amount

def methods():
    requested=os.environ.get('PAYMONGO_METHODS','card,gcash,qrph').split(',')
    values=[m.strip() for m in requested]
    if not values or len(values)!=len(set(values)) or any(m not in {'card','gcash','qrph'} for m in values):
        raise PaymentError(503,'Invalid payment method configuration.')
    return values

def create_session(key, attrs, idem_key):
    payload=json.dumps({'data':{'attributes':attrs}}).encode()
    request=urllib.request.Request('https://api.paymongo.com/v2/checkout_sessions',payload,{
        'Authorization':'Basic '+base64.b64encode((key+':').encode()).decode(),
        'Content-Type':'application/json', 'Idempotency-Key':idem_key,
        'Accept':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(request,timeout=12) as response:
            obj=json.load(response)
    except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as exc:
        raise PaymentError(502,'Checkout provider unavailable. Retry with the same request.') from exc
    record=obj.get('data') if isinstance(obj,dict) else None
    sid=record.get('id') if isinstance(record,dict) else None
    url=record.get('attributes',{}).get('checkout_url') if isinstance(record,dict) else None
    if not isinstance(sid,str) or not sid.startswith('cs_') or not isinstance(url,str) or urlparse(url).scheme!='https' or urlparse(url).hostname!='checkout.paymongo.com':
        raise PaymentError(502,'Provider response incomplete. Retry with the same request.')
    return sid,url

def checkout(c, uid, data):
    key,_,origin=configured()
    kind=data.get('kind'); ident=data.get('listing_id') if kind=='listing' else None
    if kind not in ('listing','pro'):raise PaymentError(400,'Choose a listing or Deskter Pro.')
    if kind=='listing':integer(ident,'listing id')
    request_key=data.get('request_key')
    if not isinstance(request_key,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,80}',request_key):raise PaymentError(400,'Invalid request key')
    # BEGIN IMMEDIATE is held through the bounded provider call. This is safe
    # for local test traffic, but needs a durable worker/lease at scale.
    c.execute('BEGIN IMMEDIATE')
    old=c.execute('SELECT * FROM orders WHERE buyer=? AND request_key=?',(uid,request_key)).fetchone()
    if old:
        if (old['kind'],old['target_id'])!=(kind,ident):raise PaymentError(409,'Request key belongs to another checkout.')
        if old['checkout_url']:return {'order_id':old['id'],'checkout_url':old['checkout_url'],'status':old['status']}
        order_id=old['id'];amount=old['amount'];title=old['title']
    else:
        if kind=='listing':
            item=c.execute("SELECT * FROM listings WHERE id=? AND status='published'",(ident,)).fetchone()
            if not item or item['owner']==uid:raise PaymentError(404,'Listing unavailable')
            if item['pricing']!='one_time' or item['category'] not in ('Products','Courses','Services'):
                raise PaymentError(400,'This listing requires an inquiry or a different billing flow.')
            if item['category']=='Courses' and not c.execute('''SELECT 1 FROM course_lessons lesson
                  JOIN course_modules module ON module.id=lesson.module_id WHERE module.listing_id=? LIMIT 1''',(ident,)).fetchone():
                raise PaymentError(400,'This course needs a lesson before checkout is available.')
            amount=item['price'];title=item['title']
            listing_kind={'Products':'product','Courses':'course','Services':'service'}[item['category']]
            rate=commerce.sales_rate()
            fee=(amount*rate+5000)//10000
        else:
            amount=plan_price();title='Deskter Pro · 30 days';listing_kind=None;rate=None;fee=None
        if not 2000<=amount<=100000000:raise PaymentError(400,'Listing amount is outside the checkout range.')
        order_id=c.execute('''INSERT INTO orders(buyer,kind,target_id,listing_kind,title,amount,
          commission_bps,platform_fee,request_key,created) VALUES(?,?,?,?,?,?,?,?,?,?)''',
            (uid,kind,ident,listing_kind,title,amount,rate,fee,request_key,int(time.time()))).lastrowid
    # Persist the order and its stable provider idempotency key before calling
    # an external network service. A crashed process can retry this same order.
    c.commit()
    c.execute('BEGIN IMMEDIATE')
    existing=c.execute('SELECT session_id,checkout_url,status FROM orders WHERE id=?',(order_id,)).fetchone()
    if existing['checkout_url']:
        return {'order_id':order_id,'checkout_url':existing['checkout_url'],'status':existing['status']}
    attrs={'line_items':[{'name':title,'amount':amount,'currency':'PHP','quantity':1}],
           'payment_method_types':methods(),
           'success_url':origin+'/orders?order='+str(order_id),
           'cancel_url':origin+'/orders?order='+str(order_id),
           'reference_number':'DESKTER-'+str(order_id),
           'send_email_receipt':False}
    sid,url=create_session(key,attrs,'deskter-checkout-'+str(order_id))
    c.execute('UPDATE orders SET session_id=?,checkout_url=? WHERE id=? AND session_id IS NULL',(sid,url,order_id))
    return {'order_id':order_id,'checkout_url':url,'status':'pending'}

def owned_orders(c, uid):
    return [dict(r) for r in c.execute('SELECT id,kind,target_id,title,amount,currency,status,created,paid_at FROM orders WHERE buyer=? ORDER BY id DESC',(uid,))]

def verify(raw,header):
    _,secret,_=configured()
    if len(header)>300 or not raw or len(raw)>65536:raise PaymentError(401,'Invalid webhook signature')
    parts={}
    for piece in header.split(','):
        if '=' not in piece:continue
        k,v=piece.strip().split('=',1)
        if k in parts:raise PaymentError(401,'Invalid webhook signature')
        parts[k]=v
    t=parts.get('t','');sig=parts.get('te','')
    if not t.isdigit() or len(t)>12 or not re.fullmatch(r'[0-9a-fA-F]{64}',sig):raise PaymentError(401,'Invalid webhook signature')
    if abs(time.time()-int(t))>7*86400:raise PaymentError(401,'Expired webhook signature')
    expected=hmac.new(secret.encode(),t.encode()+b'.'+raw,hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,sig.lower()):raise PaymentError(401,'Invalid webhook signature')

def handle_webhook(c, raw, header):
    verify(raw,header)  # raw bytes must be authenticated before JSON parsing
    try:
        envelope=json.loads(raw)
        event=envelope['data'];event_id=event['id'];attributes=event['attributes']
        typ=attributes['type'];live=attributes['livemode']
    except (KeyError,TypeError,ValueError):raise PaymentError(400,'Invalid webhook payload')
    if not isinstance(event_id,str) or not 1<=len(event_id)<=100 or type(live) is not bool or live:
        raise PaymentError(400,'Unexpected webhook mode or ID')
    if typ!='checkout_session.payment.paid':return {'ok':True,'ignored':True}
    try:
        session=attributes['data'];sid=session['id'];sa=session['attributes']
        reference=sa['reference_number'];payments=sa['payments']
        paid=[p for p in payments if p['attributes']['status']=='paid']
        if len(paid)!=1:raise ValueError()
        payment=paid[0];payid=payment['id'];pa=payment['attributes']
        amount=pa['amount'];currency=pa['currency']
    except (KeyError,TypeError,ValueError):raise PaymentError(400,'Incomplete paid session event')
    if not isinstance(sid,str) or not isinstance(payid,str) or type(amount) is not int or currency!='PHP':
        raise PaymentError(400,'Invalid payment details')
    # Session identity and our immutable server-side amount are authoritative.
    # reference_number is an additional cross-check, never the sole lookup.
    c.execute('BEGIN IMMEDIATE')
    order=c.execute('SELECT * FROM orders WHERE session_id=?',(sid,)).fetchone()
    if not order:raise PaymentError(409,'Unknown checkout session; reconcile before acknowledging')
    if reference!='DESKTER-'+str(order['id']) or amount!=order['amount']:
        raise PaymentError(409,'Payment mismatch; reconciliation required')
    previous=c.execute('SELECT 1 FROM webhook_events WHERE event_id=?',(event_id,)).fetchone()
    if previous:return {'ok':True,'duplicate':True}
    if order['status']=='paid':
        if order['payment_id']!=payid:raise PaymentError(409,'Conflicting payment; reconciliation required')
        c.execute('INSERT INTO webhook_events(event_id,order_id,created) VALUES(?,?,?)',(event_id,order['id'],int(time.time())))
        return {'ok':True,'duplicate':True}
    if order['status']!='pending':raise PaymentError(409,'Order requires reconciliation')
    now=int(time.time())
    if order['kind']=='listing':
        listing=c.execute('SELECT id FROM listings WHERE id=?',(order['target_id'],)).fetchone()
        if not listing or order['listing_kind'] not in ('product','course','service'):
            raise PaymentError(409,'Listing unavailable; reconciliation required')
        c.execute('INSERT INTO purchases(order_id,buyer,listing_id,kind,created) VALUES(?,?,?,?,?)',
                  (order['id'],order['buyer'],order['target_id'],order['listing_kind'],now))
    else:
        c.execute("INSERT INTO subscriptions(user_id,starts,ends,reference) VALUES(?,?,?,?)",
                  (order['buyer'],now,now+30*86400,'paymongo-order-'+str(order['id'])))
    c.execute("UPDATE orders SET status='paid',payment_id=?,paid_at=? WHERE id=?",(payid,now,order['id']))
    c.execute('INSERT INTO webhook_events(event_id,order_id,created) VALUES(?,?,?)',(event_id,order['id'],now))
    return {'ok':True}
