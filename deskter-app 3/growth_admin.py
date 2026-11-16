"""Local operator tool. Never expose this command through a public HTTP route."""
import argparse
import time
import server
import growth

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['grant','revoke'])
    p.add_argument('kind',choices=['pro','boost'])
    p.add_argument('target',type=int,help='User ID for pro grants; subscription ID for pro revocation; boost ID otherwise')
    p.add_argument('--days',type=int,default=30)
    p.add_argument('--reference',required=True,help='Unique operator approval reference; not proof of payment')
    p.add_argument('--actor',required=True,help='Operator identifier for audit')
    a=p.parse_args();server.init()
    try:
        with server.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if a.action=='grant':growth.grant(c,a.kind,a.target,a.reference,a.days,a.actor)
            else:
                table='subscriptions' if a.kind=='pro' else 'boosts'
                growth.integer(a.target,'target')
                changed=c.execute(f"UPDATE {table} SET status='revoked' WHERE id=? AND status!='revoked'",(a.target,)).rowcount
                if not changed:raise growth.Error(404,'Active or pending record not found')
                c.execute('INSERT INTO growth_audit(kind,target,reference,actor,created) VALUES(?,?,?,?,?)',
                          ('revoke_'+a.kind,a.target,growth.text(a.reference,'reference'),growth.text(a.actor,'actor'),int(time.time())))
        print('Operator action recorded. No payment was processed.')
    except (growth.Error,server.sqlite3.IntegrityError) as e:
        raise SystemExit(getattr(e,'message','Duplicate approval reference; nothing changed.'))
if __name__=='__main__':main()
