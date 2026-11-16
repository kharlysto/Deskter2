import hashlib
import hmac
import json
import os
import time
import unittest
from unittest.mock import patch

import payments
import server
import test_workflow as workflow

class Payments(unittest.TestCase):
    setUp=workflow.Workflow.setUp
    tearDown=workflow.Workflow.tearDown
    client=workflow.Workflow.client
    req=workflow.Workflow.req
    register=workflow.Workflow.register

    def config(self):
        return patch.dict(os.environ,{'PAYMONGO_SECRET_KEY':'sk_test_placeholder',
            'PAYMONGO_WEBHOOK_SECRET':'test-hook-secret','DESKTER_PUBLIC_ORIGIN':'http://127.0.0.1:'+str(self.http.server_port),
            'DESKTER_PRO_30D_CENTAVOS':'49900'})

    def users(self):
        seller,buyer,other=self.client(),self.client(),self.client()
        self.register(seller,'seller@example.test');self.register(buyer,'buyer@example.test')
        self.register(other,'other@example.test')
        return seller,buyer,other

    def listing(self, seller, category='Courses', price=20000, pricing='one_time'):
        d={'title':'A creator course','category':category,'description':'A full online learning experience',
           'price':price,'pricing':pricing,'status':'published'}
        self.assertEqual(self.req(seller,'listings',d)[0],200)
        return self.req(seller,'state')[1]['listings'][0]['id']

    def event(self,session,ref,amount,event_id='evt_first',pay='pay_first',live=False,source='gcash'):
        return {'data':{'id':event_id,'type':'event','attributes':{'type':'checkout_session.payment.paid',
            'livemode':live,'data':{'id':session,'type':'checkout_session','attributes':{'reference_number':ref,
            'payments':[{'id':pay,'attributes':{'amount':amount,'currency':'PHP','status':'paid','source':{'type':source}}}]}}}}}

    def webhook(self,payload,secret='test-hook-secret',offset=0,tamper=False):
        body=json.dumps(payload,separators=(',',':')).encode();ts=str(int(time.time())+offset)
        digest=hmac.new(secret.encode(),ts.encode()+b'.'+body,hashlib.sha256).hexdigest()
        if tamper:body+=b' '
        from urllib.request import Request
        from urllib.error import HTTPError
        req=Request(self.base.replace('/api/','')+'/webhooks/paymongo',body,
                    {'Content-Type':'application/json','Paymongo-Signature':f't={ts},te={digest},li='},method='POST')
        try:
            with self.client().open(req) as r:return r.status,json.load(r)
        except HTTPError as e:return e.code,json.load(e)

    def test_checkout_and_course_purchase_signed_webhook_only(self):
        seller,buyer,other=self.users();lid=self.listing(seller)
        with self.config():
            self.assertEqual(self.req(buyer,'checkout',{'kind':'listing','listing_id':lid,'request_key':'course-no-lessons'})[0],400)
        module=self.req(seller,'course/modules',{'listing_id':lid,'title':'Welcome'})[1]['id']
        self.assertEqual(self.req(seller,'course/lessons',{'module_id':module,'title':'Getting started',
            'kind':'text','body':'Welcome to the course'})[0],200)
        with self.config(),patch.object(payments,'create_session',return_value=('cs_course','https://checkout.paymongo.com/cs_course')) as provider:
            data={'kind':'listing','listing_id':lid,'request_key':'course-request-1','amount':1,'buyer':123}
            self.assertEqual(self.req(seller,'checkout',data)[0],404)
            code,order=self.req(buyer,'checkout',data)
            self.assertEqual(code,200)
            self.assertEqual(order['status'],'pending')
            payload=provider.call_args.args[1]
            self.assertEqual(payload['line_items'][0]['amount'],20000)
            self.assertEqual(payload['payment_method_types'],['card','gcash','qrph'])
            self.assertEqual(payload['reference_number'],'DESKTER-'+str(order['order_id']))
            self.assertEqual(self.req(buyer,'checkout',data)[1]['order_id'],order['order_id'])
            self.assertEqual(provider.call_count,1)
            self.assertEqual(self.req(buyer,'checkout',{**data,'kind':'pro'})[0],409)
            self.assertEqual(self.req(other,'orders')[1]['orders'],[])
            self.assertEqual(self.req(buyer,'orders')[1]['orders'][0]['status'],'pending')
            # The checkout snapshots the offering classification before the
            # seller can subsequently change its category or archive it.
            with server.connect() as c:c.execute("UPDATE listings SET category='Services',status='archived' WHERE id=?",(lid,))
            event=self.event('cs_course','DESKTER-'+str(order['order_id']),20000)
            self.assertEqual(self.webhook(event,tamper=True)[0],401)
            self.assertEqual(self.webhook(event,offset=-8*86400)[0],401)
            self.assertEqual(self.webhook({**event,'data':{**event['data'],'attributes':{**event['data']['attributes'],'livemode':True}}})[0],400)
            self.assertEqual(self.webhook(self.event('cs_course','DESKTER-'+str(order['order_id']),19999))[0],409)
            self.assertEqual(self.req(buyer,'orders')[1]['orders'][0]['status'],'pending')
            self.assertEqual(self.webhook(event)[0],200)
            self.assertEqual(self.webhook(event)[1]['duplicate'],True)
            self.assertEqual(self.webhook(self.event('cs_course','DESKTER-'+str(order['order_id']),20000,'evt_retry'))[1]['duplicate'],True)
            self.assertEqual(self.webhook(self.event('cs_course','DESKTER-'+str(order['order_id']),20000,'evt_conflict','pay_other'))[0],409)
            with server.connect() as c:
                purchase=c.execute('SELECT * FROM purchases').fetchone()
                self.assertEqual((purchase['buyer'],purchase['listing_id'],purchase['kind']),
                                 (self.req(buyer,'state')[1]['user']['id'],lid,'course'))
                self.assertEqual(c.execute('SELECT COUNT(*) FROM purchases').fetchone()[0],1)
            self.assertEqual(self.req(buyer,'orders')[1]['orders'][0]['status'],'paid')
            self.assertEqual(self.req(other,'orders')[1]['orders'],[])

    def test_pro_grants_only_after_paid_webhook_and_expires(self):
        _,buyer,_=self.users()
        with self.config(),patch.object(payments,'create_session',return_value=('cs_pro','https://checkout.paymongo.com/cs_pro')):
            result=self.req(buyer,'checkout',{'kind':'pro','request_key':'pro-request-1'})[1]
            self.assertEqual(self.req(buyer,'pro/analytics')[0],403)
            event=self.event('cs_pro','DESKTER-'+str(result['order_id']),49900)
            self.assertEqual(self.webhook(event)[0],200)
            self.assertEqual(self.req(buyer,'pro/analytics')[0],200)
            with server.connect() as c:
                self.assertEqual(c.execute('SELECT COUNT(*) FROM subscriptions').fetchone()[0],1)
                c.execute('UPDATE subscriptions SET starts=?,ends=?',(int(time.time())-100,int(time.time())-1))
            self.assertEqual(self.req(buyer,'pro/analytics')[0],403)

    def test_incomplete_or_unknown_webhooks_cannot_grant(self):
        seller,buyer,_=self.users();lid=self.listing(seller,'Products')
        with self.config(),patch.object(payments,'create_session',return_value=('cs_known','https://checkout.paymongo.com/cs_known')):
            order=self.req(buyer,'checkout',{'kind':'listing','listing_id':lid,'request_key':'product-req'})[1]
            ref='DESKTER-'+str(order['order_id'])
            self.assertEqual(self.webhook(self.event('cs_fake',ref,20000))[0],409)
            self.assertEqual(self.webhook(self.event('cs_known','DESKTER-999',20000))[0],409)
            bad=self.event('cs_known',ref,20000);bad['data']['attributes']['data']['attributes']['payments']=[]
            self.assertEqual(self.webhook(bad)[0],400)
            with server.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM purchases').fetchone()[0],0)

    def test_missing_config_declines_and_recurring_listing_declined(self):
        seller,buyer,_=self.users();lid=self.listing(seller,'Services',20000,'monthly')
        self.assertEqual(self.req(buyer,'checkout',{'kind':'pro','request_key':'good-key-1'})[0],503)
        with self.config():
            self.assertEqual(self.req(buyer,'checkout',{'kind':'listing','listing_id':lid,'request_key':'good-key-2'})[0],400)
            with patch.dict(os.environ,{'PAYMONGO_SECRET_KEY':'sk_live_fake'}):
                self.assertEqual(self.req(buyer,'checkout',{'kind':'pro','request_key':'good-key-3'})[0],503)

    def test_retries_after_provider_uncertainty_use_same_provider_key(self):
        seller,buyer,_=self.users();lid=self.listing(seller,'Products')
        with self.config(),patch.object(payments,'create_session',side_effect=[payments.PaymentError(502,'timeout'),('cs_retry','https://checkout.paymongo.com/cs_retry')]) as provider:
            data={'kind':'listing','listing_id':lid,'request_key':'safe-retry'}
            self.assertEqual(self.req(buyer,'checkout',data)[0],502)
            with server.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM orders').fetchone()[0],1)
            self.assertEqual(self.req(buyer,'checkout',data)[0],200)
            self.assertEqual(provider.call_args_list[0].args[2],provider.call_args_list[1].args[2])
            self.assertEqual(self.req(buyer,'orders')[1]['orders'][0]['status'],'pending')
