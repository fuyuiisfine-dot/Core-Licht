"""Back up local state, maximize affection and enable owned character files in place."""
import argparse
import json
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from game_server.affection import maximize


def apply(database,role_id,directory):
    with closing(sqlite3.connect(database))as db:
        row=db.execute('SELECT value FROM role_snapshots WHERE role_id=? AND domain=?',(role_id,'sandbox_gm')).fetchone()
        if not row:raise ValueError('role has no explicit local GM profile')
        profile=maximize(json.loads(row[0]),directory)
        backup=database.with_name(database.stem+'.before-affection-'+str(time.time_ns())+'.sqlite3')
        with closing(sqlite3.connect(backup))as out:db.backup(out)
        with db:db.execute('UPDATE role_snapshots SET value=? WHERE role_id=? AND domain=?',
            (json.dumps(profile),role_id,'sandbox_gm'))
        return {'role_id':role_id,'backup':str(backup.resolve()),'characters':len(profile['cards']),
                'favor_levels':sorted({c['favor_lvl']for c in profile['cards']}),
                'documents':{k:len(v)for k,v in profile['documents'].items()}}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,required=True);parser.add_argument('--role',type=int,required=True)
    parser.add_argument('--analysis',type=Path,default=Path('analysis'))
    args=parser.parse_args();print(json.dumps(apply(args.database,args.role,args.analysis),indent=2))
