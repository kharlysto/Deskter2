"""Database checks and consistent backups. Does not restore or delete user data."""
import argparse, datetime, sqlite3
from pathlib import Path
import server

def check():
    if not Path(server.DB).is_file():raise SystemExit('Database not found. Start Deskter first.')
    with server.connect() as c:
        integrity=[r[0] for r in c.execute('PRAGMA integrity_check')]
        foreign=list(c.execute('PRAGMA foreign_key_check'))
        if integrity!=['ok'] or foreign:raise SystemExit('Database check failed. Keep a backup and investigate before continuing.')
        print('Database integrity and foreign-key checks passed.')

def backup(directory):
    check()
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    name='deskter-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.sqlite3'
    destination=directory/name
    with server.connect() as source:
        target=sqlite3.connect(destination)
        try:source.backup(target)
        finally:target.close()
    print(f'Backup saved: {destination}')
    return destination

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['check','backup']);parser.add_argument('--directory',default=str(server.ROOT/'backups'));args=parser.parse_args()
    if args.action=='check':check()
    else:backup(args.directory)
