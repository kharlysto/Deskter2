import http.cookiejar, json, os, tempfile, threading, unittest, urllib.request, urllib.error
from http.server import ThreadingHTTPServer
import server

class Workflow(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();server.DB=os.path.join(self.tmp.name,'test.sqlite3');server.init()
        self.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.base='http://127.0.0.1:'+str(self.http.server_port)+'/api/'
    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.tmp.cleanup()
    def client(self):return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def req(self,client,path,data=None,method=None,origin=None):
        headers={'Content-Type':'application/json'}
        if origin:headers['Origin']=origin
        r=urllib.request.Request(self.base+path,data=None if data is None else json.dumps(data).encode(),headers=headers,method=method)
        try:
            with client.open(r) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as e:return e.code,json.load(e)
    def register(self,c,email):
        self.assertEqual(self.req(c,'register',{'name':'Test Seller','email':email,'password':'secure-example-pass'})[0],200)
    def test_full_workflow_and_authorization(self):
        seller,buyer,anon=self.client(),self.client(),self.client()
        self.register(seller,'seller@example.test');self.register(buyer,'buyer@example.test')
        listing={'title':'Brand design','description':'A complete brand identity package','category':'Services','price':1250000}
        self.assertEqual(self.req(anon,'listings',listing)[0],401)
        self.assertEqual(self.req(seller,'listings',listing,origin='https://evil.test')[0],403)
        self.assertEqual(self.req(seller,'listings',listing)[0],200)
        state=self.req(seller,'state')[1];item=state['listings'][0]
        self.assertEqual(item['price'],1250000)
        self.assertEqual(self.req(buyer,'listings',{**listing,'id':item['id']})[0],403)
        self.assertEqual(self.req(buyer,'save',{'id':item['id']})[0],200)
        self.assertEqual(self.req(buyer,'follow',{'id':item['owner']})[0],200)
        self.assertEqual(self.req(buyer,'leads',{'id':item['id'],'message':'Please send a quote for my new business.'})[0],200)
        lead=self.req(seller,'state')[1]['leads'][0]
        self.assertEqual(self.req(buyer,'leads',{'id':lead['id'],'status':'Closed'},'PATCH')[0],403)
        self.assertEqual(self.req(seller,'leads',{'id':lead['id'],'status':'In progress'},'PATCH')[0],200)
        self.assertEqual(self.req(seller,'state')[1]['leads'][0]['status'],'In progress')
        self.assertEqual(self.req(buyer,'state')[1]['saved'],[item['id']])
        self.assertEqual(self.req(anon,'state')[1]['leads'],[])
        self.req(buyer,'logout',{})
        self.assertIsNone(self.req(buyer,'state')[1]['user'])
        self.assertEqual(self.req(buyer,'login',{'email':'buyer@example.test','password':'secure-example-pass'})[0],200)
        self.assertEqual(self.req(buyer,'state')[1]['following'],[item['owner']])
    def test_input_validation(self):
        c=self.client();self.register(c,'test@example.test')
        for price in [-1,1.25,True]:
            self.assertEqual(self.req(c,'listings',{'title':'Valid name','description':'Long enough description','category':'Services','price':price})[0],400)
        self.assertEqual(self.req(c,'login',{'email':'test@example.test','password':'wrong-password'})[0],401)
        self.assertEqual(self.req(c,'register',{'name':'Short','email':'x@example.test','password':'short'})[0],400)
    def test_draft_publish_archive_and_pricing(self):
        seller,buyer=self.client(),self.client()
        self.register(seller,'seller@example.test');self.register(buyer,'buyer@example.test')
        item={'title':'Precision pricing','description':'Includes a complete project consultation.','category':'Services','price':125050,'pricing':'monthly','status':'draft'}
        self.assertEqual(self.req(seller,'listings',item)[0],200)
        own=self.req(seller,'state')[1]['listings'][0];item['id']=own['id']
        self.assertEqual(own['price'],125050)
        self.assertEqual(own['status'],'draft')
        self.assertEqual(self.req(buyer,'state')[1]['listings'],[])
        self.assertEqual(self.req(buyer,'save',{'id':item['id']})[0],400)
        self.assertEqual(self.req(buyer,'leads',{'id':item['id'],'message':'Please send me a custom quote.'})[0],400)
        item['status']='published';self.assertEqual(self.req(seller,'listings',item)[0],200)
        self.assertEqual(self.req(buyer,'state')[1]['listings'][0]['pricing'],'monthly')
        for mode in ['one_time','monthly','yearly','starting_at','quote','free']:
            item['pricing']=mode
            self.assertEqual(self.req(seller,'listings',item)[0],200)
            result=self.req(buyer,'state')[1]['listings'][0]
            self.assertEqual(result['price'],0 if mode in ['quote','free'] else 125050)
        self.assertEqual(self.req(seller,'listings',{**item,'pricing':'weekly'})[0],400)
        self.assertEqual(self.req(seller,'listings',{**item,'pricing':'one_time','price':0})[0],400)
        self.assertEqual(self.req(buyer,'listings',{**item,'status':'archived'})[0],403)
        item['status']='archived';self.assertEqual(self.req(seller,'listings',item)[0],200)
        self.assertEqual(self.req(buyer,'state')[1]['listings'],[])
        self.assertEqual(self.req(seller,'state')[1]['listings'][0]['status'],'archived')
        self.assertEqual(self.req(seller,'profile',{'name':'Updated Seller'})[0],200)
        self.assertEqual(self.req(seller,'state')[1]['user']['name'],'Updated Seller')
    def test_upgrade_existing_database(self):
        with server.connect() as c:
            c.execute('DROP TABLE leads');c.execute('DROP TABLE saves');c.execute('DROP TABLE listings')
            c.execute('CREATE TABLE listings(id INTEGER PRIMARY KEY,owner INTEGER,title TEXT,category TEXT,description TEXT,price INTEGER,created INTEGER)')
            c.execute("INSERT INTO listings VALUES(1,1,'Legacy listing','Services','Existing description',1500,0)")
        server.init();server.init()
        with server.connect() as c:
            row=c.execute('SELECT * FROM listings WHERE id=1').fetchone()
            self.assertEqual(row['price'],1500);self.assertEqual(row['pricing'],'one_time');self.assertEqual(row['status'],'published')
    def test_replies_visibility_and_malformed_ids(self):
        seller,buyer,stranger=self.client(),self.client(),self.client()
        self.register(seller,'seller@example.test');self.register(buyer,'buyer@example.test');self.register(stranger,'stranger@example.test')
        item={'title':'A useful service','description':'Detailed service description for testing.','category':'Services','price':10000,'status':'published'}
        self.req(seller,'listings',item);item['id']=self.req(buyer,'state')[1]['listings'][0]['id']
        for ident in [True,0,-1,[],{},'1']:
            self.assertEqual(self.req(seller,'listings',{**item,'id':ident})[0],400)
            self.assertEqual(self.req(buyer,'leads',{'id':ident,'message':'A detailed inquiry message.'})[0],400)
        self.req(buyer,'save',{'id':item['id']})
        self.req(buyer,'leads',{'id':item['id'],'message':'Please explain the project deliverables.'})
        sent=self.req(buyer,'state')[1]['sent'][0]
        self.assertEqual(sent['title'],item['title'])
        self.assertEqual(self.req(stranger,'state')[1]['sent'],[])
        self.assertEqual(self.req(buyer,'reply',{'id':sent['id'],'reply':'Forged reply'})[0],403)
        self.assertEqual(self.req(stranger,'reply',{'id':sent['id'],'reply':'Forged reply'})[0],403)
        self.assertEqual(self.req(seller,'reply',{'id':sent['id'],'reply':'We include two revision rounds.'})[0],200)
        self.assertEqual(self.req(buyer,'state')[1]['sent'][0]['reply'],'We include two revision rounds.')
        self.req(seller,'listings',{**item,'status':'archived'})
        self.assertEqual(self.req(buyer,'state')[1]['saved'],[])
        self.assertEqual(len(self.req(buyer,'state')[1]['sent']),1)
        self.req(seller,'listings',item)
        self.assertEqual(self.req(buyer,'state')[1]['saved'],[item['id']])
    def test_password_preservation_and_session_expiry(self):
        c=self.client();pw='  password with spaces  '
        self.assertEqual(self.req(c,'register',{'email':'space@example.test','name':'Spaces','password':pw})[0],200)
        self.req(c,'logout',{})
        self.assertEqual(self.req(c,'login',{'email':'space@example.test','password':pw.strip()})[0],401)
        self.assertEqual(self.req(c,'login',{'email':'space@example.test','password':pw})[0],200)
        with server.connect() as db:db.execute('UPDATE sessions SET expires=0')
        self.assertIsNone(self.req(c,'state')[1]['user'])
        self.assertEqual(self.req(c,'profile',{'name':'Unauthorized'})[0],401)
        for email in ['not-an-email','a@','a@b','a b@example.test']:
            self.assertEqual(self.req(c,'register',{'email':email,'name':'Test','password':pw})[0],400)
    def test_pages_health_and_throttling(self):
        c=self.client()
        for path,marker in [('/','Your work deserves'),('/login','accountForm'),('/register','accountForm'),('/app','Add an asset'),('/plans','Deskter Pro')]:
            with c.open(self.base.replace('/api/','')+path) as response:
                self.assertEqual(response.status,200)
                self.assertIn(marker,response.read().decode())
                self.assertEqual(response.headers['Cache-Control'],'no-store')
        with c.open(self.base.replace('/api/','')+'/health') as response:self.assertEqual(json.load(response)['status'],'ok')
        self.register(c,'limit@example.test');self.req(c,'logout',{})
        for _ in range(10):self.assertEqual(self.req(c,'login',{'email':'limit@example.test','password':'incorrect-password'})[0],401)
        self.assertEqual(self.req(c,'login',{'email':'limit@example.test','password':'secure-example-pass'})[0],429)
        with server.connect() as db:db.execute('UPDATE auth_attempts SET started=0')
        self.assertEqual(self.req(c,'login',{'email':'limit@example.test','password':'secure-example-pass'})[0],200)
    def test_backup_and_integrity(self):
        import manage
        c=self.client();self.register(c,'backup@example.test')
        path=manage.backup(os.path.join(self.tmp.name,'backups'))
        import sqlite3
        with sqlite3.connect(path) as backup:
            self.assertEqual(backup.execute('SELECT email FROM users').fetchone()[0],'backup@example.test')
            self.assertEqual(backup.execute('PRAGMA integrity_check').fetchone()[0],'ok')
    def test_password_change_revokes_other_sessions(self):
        first,second=self.client(),self.client();self.register(first,'change@example.test')
        self.req(second,'login',{'email':'change@example.test','password':'secure-example-pass'})
        self.assertEqual(self.req(first,'password',{'current_password':'wrong-password','new_password':'updated-password'})[0],403)
        self.assertEqual(self.req(first,'password',{'current_password':'secure-example-pass','new_password':'updated-password'})[0],200)
        self.assertIsNone(self.req(second,'state')[1]['user']);self.assertIsNotNone(self.req(first,'state')[1]['user'])
        self.assertEqual(self.req(second,'login',{'email':'change@example.test','password':'secure-example-pass'})[0],401)
        self.assertEqual(self.req(second,'login',{'email':'change@example.test','password':'updated-password'})[0],200)

if __name__=='__main__':unittest.main()
