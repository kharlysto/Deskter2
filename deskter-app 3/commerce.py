"""Purchase-bound lessons, seller receivables, and verified reviews."""
import os
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

class Error(Exception):
    def __init__(self,status,message):
        self.status,self.message=status,message

def migrate(c):
    # ALTER is needed for databases from the previous payment release.
    cols={r['name'] for r in c.execute('PRAGMA table_info(orders)')}
    if 'commission_bps' not in cols:
        c.execute('ALTER TABLE orders ADD COLUMN commission_bps INTEGER')
    if 'platform_fee' not in cols:
        c.execute('ALTER TABLE orders ADD COLUMN platform_fee INTEGER')
    c.executescript((Path(__file__).parent/'commerce.sql').read_text())
    c.execute('INSERT OR IGNORE INTO schema_migrations VALUES(4,?)',(int(time.time()),))

def ident(v,name='id'):
    if type(v) is not int or v<=0:raise Error(400,'Invalid '+name)
    return v

def name(v,name='title',limit=120,minimum=2):
    if not isinstance(v,str) or not minimum<=len(v.strip())<=limit:raise Error(400,'Invalid '+name)
    return v.strip()

def sales_rate():
    try:rate=int(os.environ.get('DESKTER_SALES_COMMISSION_BPS','400'))
    except ValueError:rate=0
    if not 300<=rate<=500:raise Error(503,'Seller commission is not configured')
    return rate

def purchased(c,uid,lid,kind=None):
    sql="SELECT 1 FROM purchases p JOIN orders o ON o.id=p.order_id WHERE p.buyer=? AND p.listing_id=? AND o.status='paid'"
    args=(uid,lid)
    if kind:sql+=' AND p.kind=?';args+=(kind,)
    return bool(c.execute(sql,args).fetchone())

def own_course(c,uid,lid):
    item=c.execute('SELECT id FROM listings WHERE id=? AND owner=? AND category=?',(lid,uid,'Courses')).fetchone()
    if not item:raise Error(404,'Course not found')

def outline(c,uid,lid):
    ident(lid,'listing id')
    listing=c.execute('SELECT id,title,owner,category FROM listings WHERE id=?',(lid,)).fetchone()
    if not listing or (listing['category']!='Courses' and not purchased(c,uid,lid,'course')):raise Error(404,'Course not found')
    seller=listing['owner']==uid and listing['category']=='Courses'
    if not seller and not purchased(c,uid,lid,'course'):raise Error(403,'Purchase this course to view its lessons')
    modules=[];total=done=0
    for m in c.execute('SELECT id,title,position FROM course_modules WHERE listing_id=? ORDER BY position,id',(lid,)):
        lessons=[]
        for lesson in c.execute('''SELECT l.id,l.title,l.kind,l.body,l.video_url,l.position,
          EXISTS(SELECT 1 FROM lesson_progress p WHERE p.lesson_id=l.id AND p.buyer=?) completed
          FROM course_lessons l WHERE l.module_id=? ORDER BY l.position,l.id''',(uid,m['id'])):
            item=dict(lesson);total+=1;done+=int(item['completed']);lessons.append(item)
        modules.append({'id':m['id'],'title':m['title'],'position':m['position'],'lessons':lessons})
    return {'listing_id':lid,'title':listing['title'],'seller':seller,'modules':modules,'completed':done,'total':total}

def seller_earnings(c,uid):
    records=[dict(r) for r in c.execute('''SELECT o.id,o.title,o.amount,o.currency,o.commission_bps,o.platform_fee,
            o.paid_at,o.target_id listing_id,u.name buyer_name
            FROM orders o JOIN listings l ON l.id=o.target_id
            JOIN users u ON u.id=o.buyer
            WHERE o.kind='listing' AND o.status='paid' AND l.owner=?
            ORDER BY o.paid_at DESC,o.id DESC''',(uid,))]
    gross=sum(r['amount'] for r in records)
    fee=sum(r['platform_fee'] or 0 for r in records)
    for r in records:r['net_owed']=r['amount']-r['platform_fee'] if r['platform_fee'] is not None else None
    known=sum(r['net_owed'] for r in records if r['net_owed'] is not None)
    return {'currency':'PHP','gross_sales':gross,'platform_fees':fee,'net_owed':known,
            'unpriced_orders':sum(r['platform_fee'] is None for r in records),
            'orders':records,'payouts_sent':0,
            'note':'PayMongo test orders only. Illustrative amounts before provider fees, refunds, taxes, and seller payouts. No transfers have been made.'}

def reviews(c,lid):
    ident(lid,'listing id')
    row=c.execute("SELECT id FROM listings WHERE id=? AND status='published'",(lid,)).fetchone()
    if not row:raise Error(404,'Listing not found')
    items=[dict(r) for r in c.execute('''SELECT r.rating,r.body,r.updated,u.name buyer_name
       FROM reviews r JOIN users u ON u.id=r.buyer WHERE r.listing_id=?
       ORDER BY r.updated DESC,r.id DESC LIMIT 100''',(lid,))]
    stats=c.execute('SELECT COUNT(*) count,AVG(rating) average FROM reviews WHERE listing_id=?',(lid,)).fetchone()
    return {'listing_id':lid,'count':stats['count'],'average':round(stats['average'],1) if stats['average'] is not None else None,'reviews':items}

def dispatch(c,uid,path,method,data,query):
    if path=='/api/course' and method=='GET':return outline(c,uid,ident_query(query,'listing_id'))
    if path=='/api/course/modules' and method=='POST':
        lid=ident(data.get('listing_id'),'listing id');own_course(c,uid,lid)
        title=name(data.get('title'))
        pos=c.execute('SELECT COALESCE(MAX(position)+1,0) FROM course_modules WHERE listing_id=?',(lid,)).fetchone()[0]
        mid=c.execute('INSERT INTO course_modules(listing_id,title,position,created) VALUES(?,?,?,?)',(lid,title,pos,int(time.time()))).lastrowid
        return {'id':mid}
    if path=='/api/course/lessons' and method=='POST':
        mid=ident(data.get('module_id'),'module id')
        module=c.execute('SELECT listing_id FROM course_modules WHERE id=?',(mid,)).fetchone()
        if not module:raise Error(404,'Module not found')
        own_course(c,uid,module['listing_id'])
        title=name(data.get('title'));kind=data.get('kind')
        if kind not in ('text','video'):raise Error(400,'Choose a text or video lesson')
        body=data.get('body','');url=data.get('video_url','')
        if not isinstance(body,str) or len(body)>12000:raise Error(400,'Lesson text is too long')
        if kind=='text':
            body=name(body,'lesson text',12000,1);url=''
        else:
            if not isinstance(url,str) or len(url)>1500:raise Error(400,'Invalid video URL')
            u=urlsplit(url)
            if u.scheme!='https' or not u.hostname or u.username or u.password or not re.search(r'\.(mp4|webm)$',u.path,re.I):
                raise Error(400,'Use a direct HTTPS .mp4 or .webm video URL')
            allowed={h.strip().lower() for h in os.environ.get('DESKTER_VIDEO_HOSTS','').split(',') if h.strip()}
            if not allowed or u.hostname.lower() not in allowed or u.fragment:
                raise Error(400,'Video host is not configured for this course')
            url=url.strip()
        pos=c.execute('SELECT COALESCE(MAX(position)+1,0) FROM course_lessons WHERE module_id=?',(mid,)).fetchone()[0]
        lid=c.execute('''INSERT INTO course_lessons(module_id,title,kind,body,video_url,position,created)
             VALUES(?,?,?,?,?,?,?)''',(mid,title,kind,body,url,pos,int(time.time()))).lastrowid
        return {'id':lid}
    if path=='/api/course/progress' and method=='POST':
        lesson=ident(data.get('lesson_id'),'lesson id')
        row=c.execute('''SELECT m.listing_id FROM course_lessons l JOIN course_modules m ON m.id=l.module_id
                         WHERE l.id=?''',(lesson,)).fetchone()
        if not row:raise Error(404,'Lesson not found')
        if not purchased(c,uid,row['listing_id'],'course'):raise Error(403,'Enrollment required')
        completed=data.get('completed')
        if type(completed) is not bool:raise Error(400,'Invalid completion status')
        if completed:c.execute('INSERT OR IGNORE INTO lesson_progress(buyer,lesson_id,completed_at) VALUES(?,?,?)',(uid,lesson,int(time.time())))
        else:c.execute('DELETE FROM lesson_progress WHERE buyer=? AND lesson_id=?',(uid,lesson))
        return {'lesson_id':lesson,'completed':completed}
    if path=='/api/seller/earnings' and method=='GET':return seller_earnings(c,uid)
    if path=='/api/reviews' and method=='GET':return reviews(c,ident_query(query,'listing_id'))
    if path=='/api/reviews' and method=='POST':
        lid=ident(data.get('listing_id'),'listing id')
        rating=data.get('rating')
        if type(rating) is not int or rating not in (1,2,3,4,5):raise Error(400,'Choose 1–5 stars')
        body=name(data.get('body'),'review',1000,10)
        if not c.execute("SELECT 1 FROM listings WHERE id=? AND status='published'",(lid,)).fetchone():raise Error(404,'Listing not found')
        if not purchased(c,uid,lid):raise Error(403,'Only verified buyers can review this listing')
        now=int(time.time())
        c.execute('''INSERT INTO reviews(listing_id,buyer,rating,body,created,updated)
           VALUES(?,?,?,?,?,?) ON CONFLICT(listing_id,buyer) DO UPDATE SET
           rating=excluded.rating,body=excluded.body,updated=excluded.updated''',(lid,uid,rating,body,now,now))
        return {'ok':True}
    if path=='/api/my-purchases' and method=='GET':
        return {'purchases':[dict(r) for r in c.execute('''SELECT p.listing_id,p.kind,l.title,
          EXISTS(SELECT 1 FROM reviews v WHERE v.listing_id=p.listing_id AND v.buyer=?) reviewed
          FROM purchases p JOIN listings l ON l.id=p.listing_id
          JOIN orders o ON o.id=p.order_id WHERE p.buyer=? AND o.status='paid'
          GROUP BY p.listing_id ORDER BY MAX(p.created) DESC''',(uid,uid))]}
    raise Error(404,'Not found')

def ident_query(query,key):
    from urllib.parse import parse_qs
    params=parse_qs(query,keep_blank_values=True)
    found=params.get(key,[])
    if len(found)!=1 or not re.fullmatch(r'[1-9]\d*',found[0]) or len(found[0])>14:
        raise Error(400,'Invalid '+key)
    return int(found[0])

ROUTES={'/api/course','/api/course/modules','/api/course/lessons','/api/course/progress',
        '/api/seller/earnings','/api/reviews','/api/my-purchases'}
