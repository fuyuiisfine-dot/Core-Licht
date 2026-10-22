"""Create one isolated native-preview role without changing the phone account."""
import argparse
import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path


def prepare(database,source_id):
    with closing(sqlite3.connect(database))as db:
        source=db.execute('SELECT level,sex FROM roles WHERE id=?',(source_id,)).fetchone()
        gm=db.execute('SELECT value FROM role_snapshots WHERE role_id=? AND domain=?',(source_id,'sandbox_gm')).fetchone()
        if not source or not gm:raise ValueError('source sandbox role is missing')
        existing=db.execute('SELECT id FROM roles WHERE uid=?',('windows-preview',)).fetchone()
        if existing:return {'role_id':existing[0],'created':False}
        backup=database.with_name(database.stem+'.before-windows-'+str(time.time_ns())+'.sqlite3')
        with closing(sqlite3.connect(backup))as out:db.backup(out)
        with db:
            cursor=db.execute('INSERT INTO roles(uid,name,sex,level,last_login_time) VALUES (?,?,?,?,?)',
                              ('windows-preview','Windows Preview',source[1],source[0],int(time.time())))
            role_id=cursor.lastrowid
            db.execute('INSERT INTO role_snapshots VALUES (?,?,?)',(role_id,'sandbox_gm',gm[0]))
            db.execute('INSERT INTO role_snapshots VALUES (?,?,?)',(role_id,'tutorial_stage','{"stage":29}'))
            for domain in ('vitality','inventory','scenario_history'):
                row=db.execute('SELECT value FROM role_snapshots WHERE role_id=? AND domain=?',(source_id,domain)).fetchone()
                if row:db.execute('INSERT INTO role_snapshots VALUES (?,?,?)',(role_id,domain,row[0]))
        return {'role_id':role_id,'created':True,'backup':str(backup.resolve()),'isolated_account':'windows-preview'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--database',type=Path,default=Path('client-work/device.sqlite3'))
    p.add_argument('--source-role',type=int,default=1);a=p.parse_args();print(json.dumps(prepare(a.database,a.source_role),indent=2))
