import datetime as dt
import os
import time
import unittest
from unittest.mock import patch
import growth
import server
import test_workflow as workflow

class Growth(unittest.TestCase):
    setUp=workflow.Workflow.setUp
    tearDown=workflow.Workflow.tearDown
    client=workflow.Workflow.client
    req=workflow.Workflow.req
    register=workflow.Workflow.register

    def seller(self,email='seller@example.test'):
        c=self.client();self.register(c,email)
        self.req(c,'listings',{'title':'Growth service','description':'A complete business consultation','category':'Services','price':10000})
        s=self.req(c,'state')[1]
        return c,s['user']['id'],next(l['id'] for l in s['listings'] if l['owner']==s['user']['id'])

    def campaign(self,c,lid):
        d={'listing_id':lid,'title':'Launch','ends':int(time.time())+86400,'request_key':'launch-1'}
        status,r=self.req(c,'campaigns',d);self.assertEqual(status,200)
        return d,r

    def test_commission_boundaries(self):
        self.assertEqual(growth.commission(100000,300),3000)
        self.assertEqual(growth.commission(100000,500),5000)
        self.assertEqual(growth.commission(10,500),1)
        self.assertEqual(growth.commission(0,400),0)
        for amount,rate in [(True,400),(1.5,400),(-1,400),(100,299),(100,501)]:
            with self.assertRaises(growth.Error):growth.commission(amount,rate)

    def test_campaign_owner_rate_and_retries(self):
        seller,uid,lid=self.seller();other=self.client();self.register(other,'other@example.test')
        d,c=self.campaign(seller,lid)
        self.assertEqual(self.req(seller,'campaigns',d)[1]['id'],c['id'])
        self.assertEqual(self.req(seller,'campaigns',{**d,'title':'Changed'})[0],409)
        self.assertEqual(self.req(other,'campaigns',{**d,'request_key':'other'})[0],404)
        self.assertEqual(self.req(self.client(),'growth')[0],401)
        self.assertEqual(self.req(other,'growth')[1]['campaigns'],[])
        with patch.dict(os.environ,{'DESKTER_COMMISSION_BPS':'500'}):
            r=self.req(seller,'campaigns',{**d,'request_key':'new','commission_bps':0})[1]
            self.assertEqual(r['commission_bps'],500)
        self.assertEqual(self.req(seller,'growth')[1]['campaigns'][-1]['commission_bps'],400)

    def test_monthly_reports_idempotency_and_privacy(self):
        seller,uid,lid=self.seller();_,campaign=self.campaign(seller,lid)
        this=dt.datetime.now(dt.timezone.utc).replace(day=1,hour=0,minute=0,second=0,microsecond=0)
        last=(this-dt.timedelta(days=1)).replace(day=1)
        with server.connect() as c:c.execute('UPDATE campaigns SET starts=?,ends=? WHERE id=?',(int(last.timestamp()),int(this.timestamp()),campaign['id']))
        d={'campaign_id':campaign['id'],'month':last.strftime('%Y-%m'),'gross':100000,'refunds':20000}
        status,r=self.req(seller,'campaign-reports',d);self.assertEqual(status,200);self.assertEqual(r['commission_due'],3200)
        self.assertEqual(r['status'],'reported_unpaid')
        self.assertEqual(self.req(seller,'campaign-reports',d)[1]['id'],r['id'])
        self.assertEqual(self.req(seller,'campaign-reports',{**d,'gross':99999})[0],409)
        self.assertEqual(self.req(seller,'campaign-reports',{**d,'refunds':100001})[0],400)
        self.assertEqual(self.req(seller,'campaign-reports',{**d,'month':this.strftime('%Y-%m')})[0],400)
        self.assertEqual(self.req(seller,'campaign-reports',{**d,'month':'2026-13'})[0],400)
        self.assertEqual(self.req(seller,'campaign-reports',{**d,'month':'2001-01'})[0],400)
        other=self.client();self.register(other,'other@example.test')
        self.assertEqual(self.req(other,'campaign-reports',d)[0],404)
        self.assertEqual(self.req(other,'growth')[1]['transactions'],[])

    def test_boost_pending_activation_expiry_and_ranking(self):
        a,uid,lid=self.seller();b,uid2,lid2=self.seller('second@example.test')
        payload={'listing_id':lid,'tier':3,'days':7,'request_key':'boost1','status':'active','starts':0}
        status,boost=self.req(a,'boosts',payload);self.assertEqual(status,200);self.assertEqual(boost['status'],'pending')
        self.assertEqual(self.req(a,'boosts',payload)[1]['id'],boost['id'])
        self.assertEqual(self.req(a,'boosts',{**payload,'tier':2})[0],409)
        self.assertEqual(self.req(b,'boosts',payload)[0],404)
        self.assertEqual(self.req(self.client(),'state')[1]['listings'][0]['id'],lid2)
        with server.connect() as c:
            c.execute('BEGIN IMMEDIATE');growth.grant(c,'boost',boost['id'],'approval1',7,'tester')
        rows=self.req(self.client(),'state')[1]['listings'];self.assertEqual(rows[0]['id'],lid);self.assertEqual(rows[0]['sponsored'],1)
        # Archiving never exposes a sponsored private listing.
        with server.connect() as c:c.execute("UPDATE listings SET status='archived' WHERE id=?",(lid,))
        self.assertNotIn(lid,[r['id'] for r in self.req(self.client(),'state')[1]['listings']])
        with server.connect() as c:
            c.execute("UPDATE listings SET status='published' WHERE id=?",(lid,))
            c.execute('UPDATE boosts SET starts=?,ends=? WHERE id=?',(int(time.time())-100,int(time.time())-1,boost['id']))
        rows=self.req(self.client(),'state')[1]['listings'];self.assertEqual(rows[0]['id'],lid2);self.assertTrue(all(not l['sponsored'] for l in rows))

    def test_pro_server_gates_bulk_atomicity_and_expiry(self):
        a,uid,lid=self.seller();b,uid2,lid2=self.seller('second@example.test')
        self.assertEqual(self.req(a,'pro/analytics')[0],403)
        self.assertEqual(self.req(a,'pro/bulk-archive',{'ids':[lid],'deskter_pro':True})[0],403)
        self.assertEqual(self.req(a,'subscriptions',{'plan':'deskter_pro','status':'active'})[0],404)
        with server.connect() as c:
            c.execute('BEGIN IMMEDIATE');growth.grant(c,'pro',uid,'pro-test',30,'tester')
        self.assertEqual(self.req(a,'pro/analytics')[0],200)
        self.assertEqual(self.req(b,'pro/analytics')[0],403)
        self.assertEqual(self.req(a,'pro/bulk-archive',{'ids':[lid,lid2]})[0],404)
        self.assertEqual(next(l['status'] for l in self.req(a,'state')[1]['listings'] if l['id']==lid),'published')
        self.assertEqual(self.req(a,'pro/bulk-archive',{'ids':[lid]})[0],200)
        with server.connect() as c:c.execute('UPDATE subscriptions SET starts=?,ends=?',(int(time.time())-100,int(time.time())))
        self.assertEqual(self.req(a,'pro/analytics')[0],403)

    def test_grants_duplicate_reference_rolls_back(self):
        a,uid,lid=self.seller()
        with server.connect() as c:
            c.execute('BEGIN IMMEDIATE');growth.grant(c,'pro',uid,'same-ref',1,'tester')
        boost=self.req(a,'boosts',{'listing_id':lid,'tier':1,'days':1,'request_key':'b'})[1]
        with self.assertRaises(server.sqlite3.IntegrityError):
            with server.connect() as c:
                c.execute('BEGIN IMMEDIATE');growth.grant(c,'boost',boost['id'],'same-ref',1,'tester')
        self.assertEqual(self.req(a,'growth')[1]['boosts'][0]['status'],'pending')
        server.init();server.init()
        with server.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM subscriptions').fetchone()[0],1)
            self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_boost_tier_ties_future_activation_and_revocation(self):
        a,uid,lid=self.seller();b,uid2,lid2=self.seller('second@example.test')
        one=self.req(a,'boosts',{'listing_id':lid,'tier':1,'days':1,'request_key':'a'})[1]
        two=self.req(b,'boosts',{'listing_id':lid2,'tier':3,'days':1,'request_key':'b'})[1]
        with server.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            growth.grant(c,'boost',one['id'],'a',1,'tester')
            growth.grant(c,'boost',two['id'],'b',1,'tester')
        self.assertEqual(self.req(a,'state')[1]['listings'][0]['id'],lid2)
        with server.connect() as c:c.execute('UPDATE boosts SET starts=starts+100,ends=ends+100 WHERE id=?',(two['id'],))
        self.assertEqual(self.req(a,'state')[1]['listings'][0]['id'],lid)
        with server.connect() as c:c.execute("UPDATE boosts SET status='revoked' WHERE id=?",(one['id'],))
        self.assertTrue(all(not l['sponsored'] for l in self.req(a,'state')[1]['listings']))

    def test_growth_validation_and_pro_revocation(self):
        a,uid,lid=self.seller()
        payload={'listing_id':lid,'tier':1,'days':1,'request_key':'a'}
        for bad in [True,0,4,'1']:
            self.assertEqual(self.req(a,'boosts',{**payload,'tier':bad})[0],400)
        self.assertEqual(self.req(a,'boosts',payload,origin='https://evil.test')[0],403)
        self.assertEqual(self.req(a,'boosts')[0],404)
        with server.connect() as c:
            c.execute('BEGIN IMMEDIATE');growth.grant(c,'pro',uid,'pro-grant',1,'tester')
        self.assertEqual(self.req(a,'growth')[1]['pro'],True)
        with server.connect() as c:c.execute("UPDATE subscriptions SET status='revoked' WHERE user_id=?",(uid,))
        self.assertEqual(self.req(a,'pro/analytics')[0],403)
        self.assertEqual(self.req(a,'pro/bulk-archive',{'ids':[lid]})[0],403)
