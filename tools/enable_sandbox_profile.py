"""Back up a local SQLite database, then enable one role's explicit GM profile."""
import argparse
import json
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from game_server.sandbox_profile import build


def enable(database,role_id,directory):
    profile=build(directory,int(time.time()))
    db=sqlite3.connect(database)
    try:
        role=db.execute('SELECT name FROM roles WHERE id=?',(role_id,)).fetchone()
        if not role:raise ValueError('local role does not exist')
        backup=database.with_name(database.stem+'.before-gm-'+str(time.time_ns())+'.sqlite3')
        with closing(sqlite3.connect(backup))as target:db.backup(target)
        with db:
            db.execute('UPDATE roles SET level=? WHERE id=?',(profile['account_level'],role_id))
            db.execute('INSERT OR REPLACE INTO role_snapshots VALUES (?,?,?)',
                (role_id,'sandbox_gm',json.dumps(profile)))
            config=load_level(directory,profile['account_level'])
            vitality={'vitality':config['vit_max'],'vit_max':config['vit_max'],
                'exchange_num':0,'daily_reward':0,'new_role_reward':0,'next_time':0}
            db.execute('INSERT OR REPLACE INTO role_snapshots VALUES (?,?,?)',(role_id,'vitality',json.dumps(vitality)))
            db.execute('INSERT OR REPLACE INTO role_snapshots VALUES (?,?,?)',(role_id,'tutorial_stage','{"stage":29}'))
            db.execute('INSERT OR REPLACE INTO role_snapshots VALUES (?,?,?)',
                (role_id,'scenario_cursor',json.dumps(dict(script_id=0,timepoint=0,cur_sublist=[],chosen_sublist=[],next_list=[]))))
        return dict(role_id=role_id,name=role[0],backup=str(backup.resolve()),level=profile['account_level'],
                    characters=len(profile['cards']),heroes=len(profile['heroes']),
                    hero_forms=sum(len(h['form_list'])for h in profile['heroes']),skins=len(profile['skin_list']))
    finally:db.close()


def load_level(directory,level):
    data=json.loads((directory/'config/lvl.json').read_text(encoding='utf-8'))['data']
    return next(r for r in (data if isinstance(data,list)else data.values())if r['lvl']==level)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,required=True);parser.add_argument('--role',type=int,required=True)
    parser.add_argument('--analysis',type=Path,default=Path('analysis'))
    args=parser.parse_args();print(json.dumps(enable(args.database,args.role,args.analysis),ensure_ascii=False,indent=2))
