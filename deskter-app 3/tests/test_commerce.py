"""HTTP integration tests for paid enrollment, seller accounting, and reviews."""
import os
import unittest
from unittest.mock import patch

import payments
import server
import test_payments as payment_tests


class Commerce(unittest.TestCase):
    setUp = payment_tests.Payments.setUp
    tearDown = payment_tests.Payments.tearDown
    client = payment_tests.Payments.client
    req = payment_tests.Payments.req
    register = payment_tests.Payments.register
    config = payment_tests.Payments.config
    users = payment_tests.Payments.users
    listing = payment_tests.Payments.listing
    event = payment_tests.Payments.event
    webhook = payment_tests.Payments.webhook

    def pay(self, buyer, listing_id, session='cs_commerce', key='commerce-checkout'):
        with self.config(), patch.object(payments, 'create_session', return_value=(session, 'https://checkout.paymongo.com/'+session)):
            status, order = self.req(buyer, 'checkout', {'kind':'listing', 'listing_id':listing_id, 'request_key':key})
            self.assertEqual(status, 200)
            self.assertEqual(self.webhook(self.event(session, 'DESKTER-'+str(order['order_id']), 20000, 'evt_'+session, 'pay_'+session))[0], 200)
        return order['order_id']

    def test_course_purchase_progress_and_permissions(self):
        seller,buyer,stranger = self.users()
        lid = self.listing(seller)
        q='course?listing_id='+str(lid)
        self.assertEqual(self.req(buyer,q)[0],403)
        self.assertEqual(self.req(stranger,q)[0],403)
        self.assertEqual(self.req(seller,'course/modules',{'listing_id':lid,'title':'Introduction'})[0],200)
        module=self.req(seller,q)[1]['modules'][0]['id']
        self.assertEqual(self.req(stranger,'course/lessons',{'module_id':module,'title':'Stolen','kind':'text','body':'No'})[0],404)
        self.assertEqual(self.req(seller,'course/lessons',{'module_id':module,'title':'First lesson','kind':'text','body':'Welcome to class'})[0],200)
        lesson=self.req(seller,q)[1]['modules'][0]['lessons'][0]['id']
        self.assertEqual(self.req(buyer,'course/progress',{'lesson_id':lesson,'completed':True})[0],403)
        self.assertEqual(self.req(seller,'course/progress',{'lesson_id':lesson,'completed':True})[0],403)
        self.pay(buyer,lid)
        self.assertEqual(self.req(buyer,q)[1]['modules'][0]['lessons'][0]['body'],'Welcome to class')
        self.assertEqual(self.req(stranger,q)[0],403)
        for _ in range(2):self.assertEqual(self.req(buyer,'course/progress',{'lesson_id':lesson,'completed':True})[0],200)
        self.assertEqual(self.req(buyer,q)[1]['completed'],1)
        self.assertEqual(self.req(buyer,'course/progress',{'lesson_id':lesson,'completed':'true'})[0],400)
        self.assertEqual(self.req(buyer,'course/progress',{'lesson_id':lesson,'completed':False})[0],200)
        self.assertEqual(self.req(buyer,q)[1]['completed'],0)
        self.assertEqual(self.req(buyer,'my-purchases')[1]['purchases'][0]['kind'],'course')
        with server.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM lesson_progress').fetchone()[0],0)

    def test_video_allowlist_and_course_ownership(self):
        seller,buyer,_=self.users(); lid=self.listing(seller)
        mid=self.req(seller,'course/modules',{'listing_id':lid,'title':'Videos'})[1]['id']
        video={'module_id':mid,'title':'Demo video','kind':'video','video_url':'https://media.example.test/intro.mp4'}
        self.assertEqual(self.req(seller,'course/lessons',video)[0],400)
        with patch.dict(os.environ,{'DESKTER_VIDEO_HOSTS':'media.example.test'}):
            for url in ('http://media.example.test/intro.mp4','https://media.example.test.evil.test/intro.mp4',
                        'https://media.example.test/intro.mp4#fragment','https://media.example.test/intro.txt'):
                self.assertEqual(self.req(seller,'course/lessons',{**video,'video_url':url})[0],400)
            self.assertEqual(self.req(seller,'course/lessons',video)[0],200)
            self.assertEqual(self.req(buyer,'course/lessons',video)[0],404)
        self.assertEqual(self.req(seller,'course?listing_id='+str(lid))[1]['modules'][0]['lessons'][0]['video_url'],video['video_url'])

    def test_verified_review_ratings_and_private_seller_earnings(self):
        seller,buyer,stranger=self.users();lid=self.listing(seller,'Products')
        q='reviews?listing_id='+str(lid)
        review={'listing_id':lid,'rating':5,'body':'Carefully made and very useful.'}
        self.assertEqual(self.req(buyer,'reviews',review)[0],403)
        self.assertEqual(self.req(stranger,'seller/earnings')[1]['gross_sales'],0)
        self.assertEqual(self.req(seller,'seller/earnings')[1]['gross_sales'],0)
        self.assertEqual(self.req(buyer,q)[1]['count'],0)
        with self.config(),patch.object(payments,'create_session',return_value=('cs_pending','https://checkout.paymongo.com/cs_pending')):
            self.assertEqual(self.req(buyer,'checkout',{'kind':'listing','listing_id':lid,'request_key':'pending-only'})[0],200)
        self.assertEqual(self.req(buyer,'reviews',review)[0],403)
        self.assertEqual(self.req(seller,'seller/earnings')[1]['gross_sales'],0)
        with patch.dict(os.environ,{'DESKTER_SALES_COMMISSION_BPS':'500'}):self.pay(buyer,lid,'cs_product','paid-product')
        with patch.dict(os.environ,{'DESKTER_SALES_COMMISSION_BPS':'300'}):
            e=self.req(seller,'seller/earnings')[1]
        self.assertEqual((e['gross_sales'],e['platform_fees'],e['net_owed'],e['payouts_sent']),(20000,1000,19000,0))
        self.assertEqual(e['orders'][0]['commission_bps'],500)
        self.assertEqual(self.req(buyer,'seller/earnings')[1]['gross_sales'],0)
        self.assertEqual(self.req(stranger,'reviews',review)[0],403)
        self.assertEqual(self.req(buyer,'reviews',{**review,'rating':True})[0],400)
        self.assertEqual(self.req(buyer,'reviews',review)[0],200)
        self.assertEqual(self.req(buyer,'reviews',{**review,'rating':2})[0],200)
        self.assertEqual(self.req(stranger,q)[1]['reviews'][0]['rating'],2)
        self.assertEqual(self.req(stranger,q)[1]['count'],1)
        self.assertEqual(self.req(stranger,'state')[1]['listings'][0]['rating_average'],2)
        self.assertEqual(self.req(buyer,'my-purchases')[1]['purchases'][0]['reviewed'],1)
        with server.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM reviews').fetchone()[0],1)

    def test_course_and_earnings_pages(self):
        client=self.client()
        for page,marker in (('/course','Course outline'),('/earnings','Seller earnings'),('/reviews','Verified buyer reviews')):
            with client.open(self.base.replace('/api/','')+page) as r:
                self.assertEqual(r.status,200)
                self.assertIn(marker,r.read().decode())
