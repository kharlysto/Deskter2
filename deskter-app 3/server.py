"""Deskter local development server. Python 3.12+, no dependencies."""
import hashlib, hmac, json, os, secrets, sqlite3, time, re
import growth
import payments
import commerce
from contextlib import contextmanager
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent
DB = os.environ.get('DESKTER_DB', str(ROOT / 'deskter.sqlite3'))
SECURE_COOKIES = os.environ.get('DESKTER_SECURE_COOKIES') == '1'
PUBLIC_ORIGIN = os.environ.get('DESKTER_PUBLIC_ORIGIN','').rstrip('/')
@contextmanager
def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA busy_timeout=5000')
    try:
        with c:yield c
    finally:c.close()
def init():
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER REFERENCES users(id),expires INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS listings(id INTEGER PRIMARY KEY,owner INTEGER REFERENCES users(id),title TEXT NOT NULL,category TEXT NOT NULL,description TEXT NOT NULL,price INTEGER NOT NULL CHECK(price>=0),created INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS saves(user_id INTEGER REFERENCES users(id),listing_id INTEGER REFERENCES listings(id) ON DELETE CASCADE,PRIMARY KEY(user_id,listing_id));
        CREATE TABLE IF NOT EXISTS follows(user_id INTEGER REFERENCES users(id),seller_id INTEGER REFERENCES users(id),PRIMARY KEY(user_id,seller_id));
        CREATE TABLE IF NOT EXISTS leads(id INTEGER PRIMARY KEY,buyer INTEGER REFERENCES users(id),listing_id INTEGER REFERENCES listings(id),message TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'New',created INTEGER NOT NULL);
        ''')
        columns={r['name'] for r in c.execute('PRAGMA table_info(listings)')}
        for name,definition in [('pricing','TEXT NOT NULL DEFAULT \'one_time\''),('status','TEXT NOT NULL DEFAULT \'published\'')]:
            if name not in columns:c.execute(f'ALTER TABLE listings ADD COLUMN {name} {definition}')
        if 'reply' not in {r['name'] for r in c.execute('PRAGMA table_info(leads)')}:
            c.execute("ALTER TABLE leads ADD COLUMN reply TEXT NOT NULL DEFAULT ''")
        c.executescript('''
        CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY,applied INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS auth_attempts(key TEXT PRIMARY KEY,count INTEGER NOT NULL,started INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
        CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires);
        CREATE INDEX IF NOT EXISTS listings_owner ON listings(owner);
        CREATE INDEX IF NOT EXISTS listings_visibility ON listings(status,created);
        CREATE INDEX IF NOT EXISTS leads_listing ON leads(listing_id,created);
        CREATE INDEX IF NOT EXISTS leads_buyer ON leads(buyer,created);
        ''')
        c.execute('INSERT OR IGNORE INTO schema_migrations VALUES(1,?)',(int(time.time()),))
        growth.migrate(c)
        payments.migrate(c)
        commerce.migrate(c)
def password(value,salt=None):
    salt=salt or secrets.token_hex(16)
    return salt+':'+hashlib.scrypt(value.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def send(self,status,data):
        body=json.dumps(data).encode();self.send_response(status)
        self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        if hasattr(self,'cookie'):self.send_header('Set-Cookie',self.cookie)
        self.end_headers();self.wfile.write(body)
    def do_GET(self):self.route()
    def do_POST(self):self.route()
    def do_PATCH(self):self.route()
    def serve_page(self,name):
        self.send_response(200)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','SAMEORIGIN')
        self.send_header('Referrer-Policy','strict-origin-when-cross-origin')
        self.end_headers();self.wfile.write((ROOT/name).read_bytes())
    def route(self):
        try:self.handle_request()
        except growth.Error as e:self.send(e.status,{'error':e.message})
        except payments.PaymentError as e:self.send(e.status,{'error':e.message})
        except commerce.Error as e:self.send(e.status,{'error':e.message})
        except ValueError as e:self.send(400,{'error':str(e)})
        except sqlite3.IntegrityError:self.send(409,{'error':'This account or record already exists.'})
        except Exception:self.send(500,{'error':'Server error. Please retry.'})
    def handle_request(self):
        path=urlparse(self.path).path
        pages={'/':'landing.html','/plans':'landing.html','/app':'index.html','/login':'account.html','/register':'account.html','/growth':'growth.html','/orders':'orders.html','/course':'course.html','/earnings':'earnings.html','/reviews':'reviews.html'}
        if self.command=='GET' and path in pages:
            self.serve_page(pages[path]);return
        if self.command=='GET' and path=='/health':
            with connect() as c:c.execute('SELECT 1').fetchone()
            self.send(200,{'status':'ok'});return
        if path=='/webhooks/paymongo' and self.command=='POST':
            if self.headers.get('Content-Type','').split(';')[0].strip().lower()!='application/json':raise payments.PaymentError(415,'Expected JSON webhook')
            try:size=int(self.headers.get('Content-Length','0'))
            except ValueError:raise payments.PaymentError(400,'Invalid length')
            if not 0<size<=65536:raise payments.PaymentError(413,'Webhook too large')
            raw=self.rfile.read(size)
            with connect() as c:
                result=payments.handle_webhook(c,raw,self.headers.get('Paymongo-Signature',''))
                c.commit()
            self.send(200,result);return
        if not path.startswith('/api/'):self.send(404,{'error':'Not found'});return
        if self.command!='GET':
            origin=self.headers.get('Origin')
            if origin and not (origin==PUBLIC_ORIGIN or (not PUBLIC_ORIGIN and urlparse(origin).netloc==self.headers.get('Host'))):self.send(403,{'error':'Origin denied'});return
        data={}
        if self.command!='GET':
            size=int(self.headers.get('Content-Length','0'))
            if not 0<=size<=20000:raise ValueError('Request too large')
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('Expected application/json')
            try:data=json.loads(self.rfile.read(size) or '{}')
            except Exception:raise ValueError('Invalid JSON')
            if not isinstance(data,dict):raise ValueError('Expected an object')
        def text(key,minimum=1,maximum=500):
            v=data.get(key,'')
            if not isinstance(v,str) or not minimum<=len(v.strip())<=maximum:raise ValueError('Invalid '+key)
            return v.strip()
        def identifier(key='id'):
            v=data.get(key)
            if type(v)!=int or v<=0:raise ValueError('Invalid '+key)
            return v
        cookies=SimpleCookie();cookies.load(self.headers.get('Cookie',''))
        token=cookies['session'].value if 'session' in cookies else ''
        with connect() as c:
            user=c.execute('SELECT u.id,u.name,u.email FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
            if path in ['/api/register','/api/login'] and self.command=='POST':
                email=text('email',3,254).lower();pw=data.get('password')
                if not isinstance(pw,str) or not 10<=len(pw)<=128:raise ValueError('Password must have 10–128 characters')
                if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise ValueError('Enter a valid email')
                now=int(time.time());key=hashlib.sha256((self.client_address[0]+':'+email).encode()).hexdigest()
                c.execute('DELETE FROM auth_attempts WHERE started<?',(now-900,))
                c.execute('INSERT INTO auth_attempts VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1',(key,now))
                attempt=c.execute('SELECT count FROM auth_attempts WHERE key=?',(key,)).fetchone()['count']
                c.commit()
                if attempt>10:self.send(429,{'error':'Too many authentication attempts. Try again in 15 minutes.'});return
                if path.endswith('register'):
                    name=text('name',2,80);uid=c.execute('INSERT INTO users(name,email,password) VALUES(?,?,?)',(name,email,password(pw))).lastrowid
                else:
                    found=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
                    if not found or not hmac.compare_digest(password(pw,found['password'].split(':')[0]),found['password']):self.send(401,{'error':'Incorrect email or password'});return
                    uid=found['id']
                c.execute('DELETE FROM auth_attempts WHERE key=?',(key,))
                raw=secrets.token_urlsafe(32);c.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(raw.encode()).hexdigest(),uid,time.time()+86400))
                c.execute('DELETE FROM sessions WHERE expires<=?',(time.time(),))
                if token:c.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(token.encode()).hexdigest(),))
                self.cookie='session='+raw+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400'+('; Secure' if SECURE_COOKIES else '')
                c.commit();self.send(200,{'ok':True});return
            if path=='/api/state' and self.command=='GET':
                listings=growth.discovery(c,user['id'] if user else None)
                saved=[];following=[];leads=[];sent=[]
                if user:
                    saved=[r[0] for r in c.execute("SELECT s.listing_id FROM saves s JOIN listings l ON l.id=s.listing_id WHERE s.user_id=? AND l.status='published'",(user['id'],))]
                    following=[r[0] for r in c.execute('SELECT seller_id FROM follows WHERE user_id=?',(user['id'],))]
                    leads=[dict(r) for r in c.execute('SELECT a.*,l.title,u.name buyer_name FROM leads a JOIN listings l ON l.id=a.listing_id JOIN users u ON u.id=a.buyer WHERE l.owner=? ORDER BY a.created DESC',(user['id'],))]
                    sent=[dict(r) for r in c.execute('SELECT a.*,l.title,u.name seller_name FROM leads a JOIN listings l ON l.id=a.listing_id JOIN users u ON u.id=l.owner WHERE a.buyer=? ORDER BY a.created DESC',(user['id'],))]
                self.send(200,{'user':dict(user) if user else None,'listings':listings,'saved':saved,'following':following,'leads':leads,'sent':sent});return
            if path=='/api/reviews' and self.command=='GET':
                listing_id=commerce.ident_query(urlparse(self.path).query,'listing_id')
                self.send(200,commerce.reviews(c,listing_id));return
            if not user:self.send(401,{'error':'Please sign in first'});return
            uid=user['id']
            if path in commerce.ROUTES:
                if self.command!='GET':c.execute('BEGIN IMMEDIATE')
                result=commerce.dispatch(c,uid,path,self.command,data,urlparse(self.path).query)
                c.commit();self.send(200,result);return
            if path=='/api/checkout' and self.command=='POST':
                result=payments.checkout(c,uid,data);c.commit();self.send(200,result);return
            if path=='/api/orders' and self.command=='GET':
                self.send(200,{'orders':payments.owned_orders(c,uid)});return
            if path in growth.ROUTES:
                # Serialize validated growth mutations, including duplicate retries.
                if self.command!='GET':c.execute('BEGIN IMMEDIATE')
                result=growth.dispatch(c,uid,path,self.command,data)
                c.commit();self.send(200,result);return
            if path=='/api/logout' and self.command=='POST':
                c.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(token.encode()).hexdigest(),));self.cookie='session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'+('; Secure' if SECURE_COOKIES else '')
            elif path=='/api/listings' and self.command=='POST':
                title=text('title',3,100);category=text('category');desc=text('description',10,2000);price=data.get('price')
                if category not in ['Services','Products','Courses','SaaS','Startups','Businesses','Agencies']:raise ValueError('Invalid category')
                if type(price)!=int or not 0<=price<=100000000:raise ValueError('Invalid price in centavos')
                pricing=data.get('pricing','one_time');status=data.get('status','published')
                if pricing not in ['one_time','monthly','yearly','starting_at','quote','free']:raise ValueError('Choose a supported pricing model')
                if status not in ['draft','published','archived']:raise ValueError('Invalid publication status')
                if pricing in ['quote','free']:price=0
                elif price<=0:raise ValueError('Enter a positive price, or choose Free / Request a quote')
                if 'id' in data:
                    identifier()
                    changed=c.execute('UPDATE listings SET title=?,category=?,description=?,price=?,pricing=?,status=? WHERE id=? AND owner=?',(title,category,desc,price,pricing,status,data['id'],uid)).rowcount
                    if not changed:self.send(403,{'error':'You do not own this listing'});return
                else:c.execute('INSERT INTO listings(owner,title,category,description,price,created,pricing,status) VALUES(?,?,?,?,?,?,?,?)',(uid,title,category,desc,price,int(time.time()),pricing,status))
            elif path=='/api/profile' and self.command=='POST':
                c.execute('UPDATE users SET name=? WHERE id=?',(text('name',2,80),uid))
            elif path=='/api/password' and self.command=='POST':
                current=data.get('current_password');new=data.get('new_password')
                if not isinstance(current,str) or not 10<=len(current)<=128:raise ValueError('Enter your current password')
                if not isinstance(new,str) or not 10<=len(new)<=128:raise ValueError('New password must have 10–128 characters')
                if new==current:raise ValueError('Choose a different new password')
                existing=c.execute('SELECT password FROM users WHERE id=?',(uid,)).fetchone()['password']
                if not hmac.compare_digest(password(current,existing.split(':')[0]),existing):self.send(403,{'error':'Current password is incorrect'});return
                c.execute('UPDATE users SET password=? WHERE id=?',(password(new),uid))
                c.execute('DELETE FROM sessions WHERE user_id=? AND token<>?',(uid,hashlib.sha256(token.encode()).hexdigest()))
            elif path in ['/api/save','/api/follow'] and self.command=='POST':
                ident=identifier()
                table,key=('saves','listing_id') if path.endswith('save') else ('follows','seller_id')
                if table=='saves' and not c.execute("SELECT 1 FROM listings WHERE id=? AND status='published'",(ident,)).fetchone():raise ValueError('Listing is not published')
                if table=='follows' and (ident==uid or not c.execute('SELECT 1 FROM users WHERE id=?',(ident,)).fetchone()):raise ValueError('Choose another seller to follow')
                old=c.execute(f'SELECT 1 FROM {table} WHERE user_id=? AND {key}=?',(uid,ident)).fetchone()
                if old:c.execute(f'DELETE FROM {table} WHERE user_id=? AND {key}=?',(uid,ident))
                else:c.execute(f'INSERT INTO {table} VALUES(?,?)',(uid,ident))
            elif path=='/api/leads' and self.command=='POST':
                ident=identifier();message=text('message',10,2000);listing=c.execute("SELECT owner FROM listings WHERE id=? AND status='published'",(ident,)).fetchone()
                if not listing:raise ValueError('Listing not found')
                if listing['owner']==uid:raise ValueError('You cannot inquire about your own listing')
                c.execute('INSERT INTO leads(buyer,listing_id,message,created) VALUES(?,?,?,?)',(uid,data['id'],message,int(time.time())))
            elif path=='/api/leads' and self.command=='PATCH':
                identifier()
                status=text('status')
                if status not in ['New','In progress','Closed']:raise ValueError('Invalid status')
                changed=c.execute('UPDATE leads SET status=? WHERE id=? AND listing_id IN (SELECT id FROM listings WHERE owner=?)',(status,data.get('id'),uid)).rowcount
                if not changed:self.send(403,{'error':'Lead not accessible'});return
            elif path=='/api/reply' and self.command=='POST':
                ident=identifier();reply=text('reply',1,2000)
                changed=c.execute("UPDATE leads SET reply=? WHERE id=? AND listing_id IN (SELECT id FROM listings WHERE owner=?)",(reply,ident,uid)).rowcount
                if not changed:self.send(403,{'error':'Lead not accessible'});return
            else:self.send(404,{'error':'Not found'});return
            c.commit();self.send(200,{'ok':True})
if __name__=='__main__':
    host=os.environ.get('DESKTER_HOST','127.0.0.1');port=int(os.environ.get('DESKTER_PORT','8000'))
    init();print(f'Deskter: http://{host}:{port} · Dashboard: /app',flush=True)
    ThreadingHTTPServer((host,port),Handler).serve_forever()
