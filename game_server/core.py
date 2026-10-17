"""Local compatibility core; full gameplay and main scene remain incomplete."""
import secrets
import json
import sqlite3
import time
from dataclasses import dataclass


@dataclass
class Session:
    uid: str | None = None
    role_id: int | None = None


class GameCore:
    def __init__(self, protocol, database=':memory:', clock=time.time):
        self.protocol, self.clock = protocol, clock
        self.started = int(clock())
        self.db = sqlite3.connect(database)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS accounts (
                uid TEXT PRIMARY KEY, token TEXT NOT NULL, p_key TEXT NOT NULL,
                expires INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT NOT NULL,
                name TEXT NOT NULL UNIQUE, sex INTEGER NOT NULL,
                level INTEGER NOT NULL DEFAULT 1, last_login_time INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS tutorial_fights (
                uid TEXT NOT NULL, map_id TEXT NOT NULL, start_time INTEGER NOT NULL,
                child_ids TEXT NOT NULL, result INTEGER NOT NULL, dup_time INTEGER NOT NULL,
                recorded_time INTEGER NOT NULL, PRIMARY KEY(uid,map_id,start_time));
            CREATE TABLE IF NOT EXISTS monster_states (
                uid TEXT NOT NULL, role_id INTEGER NOT NULL, mon_id INTEGER NOT NULL,
                status INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(uid,role_id,mon_id));
            CREATE TABLE IF NOT EXISTS monster_guides (
                uid TEXT NOT NULL, mon_id TEXT NOT NULL, count INTEGER NOT NULL,
                PRIMARY KEY(uid,mon_id));
            CREATE TABLE IF NOT EXISTS account_views (uid TEXT PRIMARY KEY, view INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS role_snapshots (
                role_id INTEGER NOT NULL, domain TEXT NOT NULL, value TEXT NOT NULL,
                PRIMARY KEY(role_id,domain));
            CREATE TABLE IF NOT EXISTS tutorial_entries (
                uid TEXT NOT NULL, role_id INTEGER NOT NULL, map_id TEXT NOT NULL,
                child_ids TEXT NOT NULL, recorded_time INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS tutorial_results (
                uid TEXT NOT NULL, role_id INTEGER NOT NULL, map_id TEXT NOT NULL,
                payload BLOB NOT NULL, recorded_time INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS role_grants (
                role_id INTEGER NOT NULL, grant_key TEXT NOT NULL,
                PRIMARY KEY(role_id,grant_key));
        ''')
        level_data=json.loads((protocol.directory/'config/lvl.json').read_text(encoding='utf-8'))['data']
        self.levels={row['lvl']:row for row in (level_data if isinstance(level_data,list) else level_data.values())}
        self.attributes=json.loads((protocol.directory/'player_attributes.json').read_text(encoding='utf-8'))['attributes']
        self.config=json.loads((protocol.directory/'config/config.json').read_text(encoding='utf-8'))['data']
        self.open_functions=json.loads((protocol.directory/'config/open_func.json').read_text(encoding='utf-8'))['data']

    def close(self): self.db.close()

    def issue_local_credentials(self, uid):
        """Local test credentials, independent of original publisher accounts."""
        if not uid or len(uid) > 128: raise ValueError('invalid local uid')
        token, key = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        now = int(self.clock())
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO accounts VALUES (?,?,?,?)',
                            (uid, token, key, now+3600))
        return {'uid': uid, 'uname': uid, 'token': token, 'p_key': key, 'time': now}

    def valid(self, uid, token, key):
        row = self.db.execute('SELECT * FROM accounts WHERE uid=?', (uid,)).fetchone()
        return bool(row and row['expires'] > self.clock()
                    and secrets.compare_digest(row['token'], token)
                    and secrets.compare_digest(row['p_key'], key))

    @staticmethod
    def role(row):
        return {k: row[k] for k in ('id','name','sex','level','last_login_time')}

    def snapshot(self,role_id,domain,initial):
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO role_snapshots VALUES (?,?,?)',
                            (role_id,domain,json.dumps(initial,ensure_ascii=False)))
        row=self.db.execute('SELECT value FROM role_snapshots WHERE role_id=? AND domain=?',(role_id,domain)).fetchone()
        return json.loads(row['value'])

    def role_attributes(self,row):
        defaults={key:value['5'] for key,value in self.attributes.items()}
        values=self.snapshot(row['id'],'attributes',defaults)
        with self.db:
            granted=self.db.execute('INSERT OR IGNORE INTO role_grants VALUES (?,?)',
                (row['id'],'role_born_item')).rowcount
            if granted:
                for key,amount in self.config['role_born_item']['value']:
                    if str(key) not in self.attributes:raise NotImplementedError('non-currency birth grant')
                    values[str(key)]=int(values[str(key)])+amount
                self.db.execute('INSERT OR REPLACE INTO role_snapshots VALUES (?,?,?)',
                    (row['id'],'attributes',json.dumps(values)))
        level=self.levels[row['level']]
        values.update({'601':row['id'],'602':row['name'],'603':row['sex'],
                       '604':row['level'],'610':level['exp'],'619':level['spell_slots']})
        return {'kv_list':[{'k':int(k),'v':str(v)} for k,v in values.items() if isinstance(v,(int,bool))],
                'ks_list':[{'k':int(k),'s':v} for k,v in values.items() if isinstance(v,str)]}

    def tutorial_stage(self,role_id):
        # ScenarioDefine: AfterCreateRole=23; Finished=29. Never skip to Finished.
        return self.snapshot(role_id,'tutorial_stage',{'stage':23})

    def sandbox(self,role_id):
        row=self.db.execute('SELECT value FROM role_snapshots WHERE role_id=? AND domain=?',
                            (role_id,'sandbox_gm')).fetchone()
        return json.loads(row['value'])if row else None

    def handle(self, session, message_id, payload):
        request = self.protocol.decode('c2s', message_id, payload)
        now = int(self.clock())
        pushes=[]
        if message_id == '47_2':
            if not session.uid:raise PermissionError('authenticate first')
            with self.db:self.db.execute('INSERT INTO tutorial_results VALUES (?,?,?,?,?)',
                (session.uid,session.role_id or 0,str(request.map_id),payload,now))
            return None
        elif message_id == '47_1':
            if not session.uid:raise PermissionError('authenticate first')
            with self.db:
                self.db.execute('INSERT INTO tutorial_entries VALUES (?,?,?,?,?)',
                    (session.uid,session.role_id or 0,str(request.map_id),
                     json.dumps([str(v) for v in request.child_id_list]),now))
            return None  # ProtoMap has no S2C acknowledgement.
        elif message_id == '47_3':
            # The client's pre-role tutorial runs locally and reports its result.
            # ProtoMap defines no corresponding S2C response for this message.
            if not session.uid or request.uid!=session.uid:raise PermissionError('tutorial account mismatch')
            with self.db:
                self.db.execute('''INSERT INTO tutorial_fights VALUES (?,?,?,?,?,?,?)
                    ON CONFLICT(uid,map_id,start_time) DO UPDATE SET
                    child_ids=excluded.child_ids,result=excluded.result,
                    dup_time=excluded.dup_time,recorded_time=excluded.recorded_time''',
                    (session.uid,str(request.map_id),request.start_time,
                     json.dumps([str(v) for v in request.child_id_list]),request.result,request.dup_time,now))
            return None
        elif message_id == '1_0':
            response = {'index': request.index, 'server_time': now, 'run_time': now-self.started}
        elif message_id == '1_1':
            if not self.valid(request.uid, request.token, request.p_key):
                raise PermissionError('invalid local credentials')
            session.uid, session.role_id = request.uid, None
            rows = self.db.execute('SELECT * FROM roles WHERE uid=? ORDER BY id', (session.uid,))
            response = {'code':0, 'time_zone':8, 'serv_id':1, 'open_time':self.started,
                        'role_list':[self.role(row) for row in rows]}
        elif message_id == '1_4':
            row = self.db.execute('SELECT * FROM roles WHERE id=?', (request.id,)).fetchone()
            if not row or not self.valid(row['uid'], request.token, request.p_key):
                raise PermissionError('invalid reconnect')
            session.uid, session.role_id = row['uid'], row['id']
            pushes.append(('2_2',self.role_attributes(row)))
            pushes.append(('2_9',self.tutorial_stage(row['id'])))
            response = {'code':0}
        else:
            if not session.uid: raise PermissionError('authenticate first')
            gm=self.sandbox(session.role_id)if session.role_id else None
            initial_queries={
                '3_1':('inventory',{'info':[]}),
                '11_46':('skins',{'skin_list':[]}),
                '18_1':('tasks',{'task_done':[],'task_doing':[]}),
                '18_17':('island_task_stage',{'stage':0}),
                '17_1':('dungeons',{'info':[]}),
                '17_27':('daily_drop_selection',{'info':[]}),
                '5_1':('equipment',{'info':[]}),
                '11_9':('team_favor',{'team_favor_list':[]}),
                '11_16':('character_unlocks',{'char_list':[],'voice_list':[],'remember_list':[]}),
                '11_42':('character_groups',{'group_list':[]}),
                '11_45':('character_count',{'num':0}),
                '20_2':('sign_records',{'sign_records':[]}),
                '21_4':('month_cards',{'list':[]}),
                '22_1':('friends',{'is_inc':0,'friends':[]}),
                '22_2':('friend_applications',{'is_inc':0,'apply_list':[]}),
                '22_9':('friend_assists',{'assists':[]}),
                '22_14':('friendship_points',{'assist_times':[],'friend_times':[],'record_list':[]}),
                '23_1':('settings',{'setting':[]}),
                '26_4':('scenario_history',{'list':[]}),
                '26_1':('scenario_cursor',{'script_id':0,'timepoint':0,'cur_sublist':[],
                                         'chosen_sublist':[],'next_list':[]}),
                '26_6':('scenario_videos',{'cg_list':[]}),
                '27_1':('subplots',{'list':[]}),
                '30_1':('activities',{'list':[]}),
                '31_32':('building_cores',{'core_list':[]}),
                '35_1':('heroes',{'list':[]}),
                '36_1':('dispatches',{'visible':[],'doing':[]}),
                '37_2':('trade_orders',{'order_list':[]}),
                '38_12':('post_records',{'record_list':[]}),
                '45_3':('recharge_history',{'times_list':[]}),
                '48_1':('pvp_equipment',{'equips':[],'slots':[]}),
            }
            if gm and message_id=='11_16'and 'documents'in gm:
                response=gm['documents']
            elif gm and message_id=='11_37'and 'documents'in gm:
                names={1:'char_list',2:'voice_list',3:'remember_list'}
                if request.type not in names:raise ValueError('unknown document type')
                entry=next((v for v in gm['documents'][names[request.type]]if int(v['k'])==request.sys_id),None)
                if not entry:raise PermissionError('document is not owned')
                entry['v']='1'
                with self.db:self.db.execute('UPDATE role_snapshots SET value=? WHERE role_id=? AND domain=?',
                    (json.dumps(gm),session.role_id,'sandbox_gm'))
                response={'type':request.type,'sys_id':request.sys_id}
            elif gm and message_id in ('11_20','11_31'):
                card=next((c for c in gm['cards']if int(c['id'])==request.id),None)
                if not card:raise PermissionError('character is not owned')
                if message_id=='11_20':
                    if str(request.skin_id)not in card['skin_list']:raise PermissionError('skin is not owned by this character')
                    card['use_skin']=str(request.skin_id)
                else:card['is_new']=0
                with self.db:self.db.execute('UPDATE role_snapshots SET value=? WHERE role_id=? AND domain=?',
                    (json.dumps(gm),session.role_id,'sandbox_gm'))
                response={'code':0,'id':str(request.id)}
                if message_id=='11_20':response['skin_id']=str(request.skin_id)
            elif gm and message_id in ('35_7','35_8','35_9'):
                heroes=gm['heroes']
                if message_id!='35_7':
                    hero=next((h for h in heroes if int(h['id'])==request.hero_id),None)
                    if not hero:raise PermissionError('hero is not owned')
                    heroes=[hero]
                if message_id=='35_8':
                    form=next((f for f in hero['form_list']if f['form']==request.form),None)
                    if not form or str(request.skin_id)not in form['skin_list']:raise PermissionError('hero skin is not owned')
                    form['use_skin']=str(request.skin_id)
                    with self.db:self.db.execute('UPDATE role_snapshots SET value=? WHERE role_id=? AND domain=?',
                        (json.dumps(gm),session.role_id,'sandbox_gm'))
                    response={'code':0,'form':request.form,'hero_id':str(request.hero_id),'skin_id':str(request.skin_id)}
                else:
                    skins=[{'hero_id':h['id'],'skin_list':[{k:f[k]for k in ('form','use_skin','skin_list')}
                               for f in h['form_list']]}for h in heroes]
                    response={'skin_list':skins}if message_id=='35_7'else {'skin_info':skins[0]}
            elif gm and message_id=='2_5':
                row=self.db.execute('SELECT * FROM roles WHERE id=?',(session.role_id,)).fetchone()
                response={'info':dict(role_id=str(row['id']),name=row['name'],name_num=0,
                    level=row['level'],sex=row['sex'],create_time=gm['created_time'],birth=[],
                    head_id=str(self.config['default_head_id']['value']),
                    frame_id=str(self.config['default_frame_id']['value']),signature='',
                    children_num=len(gm['cards']),dup_id=0,assist_sys_id=gm['cards'][0]['sys_id'],
                    assist_skin_id=gm['cards'][0]['use_skin'],fight_assist_grids=[],fight_assists=[],
                    show_badges=[],show_type_badges=[])}
            elif gm and message_id in ('11_1','11_45','11_46','35_1','11_23','15_4'):
                if message_id=='11_1':response={'children_list':gm['cards']}
                elif message_id=='11_45':response={'num':len(gm['cards'])}
                elif message_id=='11_46':response={'skin_list':gm['skin_list']}
                elif message_id=='35_1':response={'list':gm['heroes']}
                elif message_id=='11_23':response={'mode':1,'index':1,'list':[
                    {'index':1,'id':gm['cards'][0]['id'],'type':1,'skin_sys_id':gm['cards'][0]['use_skin']}]}
                else:
                    # One persisted team per event, referencing owned instances.
                    assist={f.name:(''if f.type==f.TYPE_STRING else 0)for f in
                        self.protocol.pool.FindMessageTypeByName('ZeroProto.p_friend_assist').fields}
                    team={'team_index':1,'team_id':str(request.event_id),'event_id':str(request.event_id),
                        'team_name':'Sandbox','children_list':[{'k':str(i),'v':c['id']}
                            for i,c in enumerate(gm['cards'][:8],1)],'spell_list':[],
                        'friend_assist':assist,'up_flag':0,'hero_list':[
                            {'index':1,'hero_id':gm['heroes'][0]['id'],'hero_form':1}], 'fetter_child_list':[]}
                    response=self.snapshot(session.role_id,'sandbox_team:'+str(request.event_id),
                                           {'default_index':1,'children_team':[team]})
            elif message_id in initial_queries or message_id in ('13_1','18_5','17_31','17_19'):
                if not session.role_id:raise PermissionError('select a role first')
                if message_id in initial_queries:
                    domain,initial=initial_queries[message_id]
                elif message_id=='18_5':
                    domain='liveness:'+str(request.type)
                    initial={'type':request.type,'liveness':0,'reward':0}
                elif message_id in ('17_31','17_19'):
                    domain=('chapter_strategy_rewards:' if message_id=='17_31' else 'chapter_rewards:')+str(request.chapters)
                    initial={'chapters':request.chapters,'list':[]}
                else:
                    row=self.db.execute('SELECT level FROM roles WHERE id=?',(session.role_id,)).fetchone()
                    config=self.levels[row['level']]
                    domain='vitality'
                    initial={'vitality':config['gain_vit'],'vit_max':config['vit_max'],
                        'exchange_num':0,'daily_reward':0,'new_role_reward':0,'next_time':0}
                response=self.snapshot(session.role_id,domain,initial)
            elif message_id=='24_1':
                if not session.role_id:raise PermissionError('select a role first')
                level=self.db.execute('SELECT level FROM roles WHERE id=?',(session.role_id,)).fetchone()['level']
                # A fresh role has no cleared normal dungeons or upgraded rooms.
                # Only unconditional functions and satisfied level gates open.
                opened=[r['id'] for r in self.open_functions.values() if (gm and gm['all_functions'])or all(
                    cond[0]==1 and level>=cond[1] for cond in r['open_limit'])]
                response={'list':sorted(opened)}
            elif message_id in ('26_2','26_3','26_5'):
                if not session.role_id:raise PermissionError('select a role first')
                if message_id=='26_2':
                    history=self.snapshot(session.role_id,'scenario_history',{'list':[]})
                    if any(int(v['k'])==request.script_id for v in history['list']):return None
                    cursor=self.snapshot(session.role_id,'scenario_cursor',
                        {'script_id':0,'timepoint':0,'cur_sublist':[],'chosen_sublist':[],'next_list':[]})
                    cursor.update(script_id=request.script_id,timepoint=request.timepoint)
                    with self.db:
                        self.db.execute('INSERT OR REPLACE INTO role_snapshots VALUES (?,?,?)',
                            (session.role_id,'scenario_cursor',json.dumps(cursor)))
                        self.db.execute('INSERT OR REPLACE INTO role_snapshots VALUES (?,?,?)',
                            (session.role_id,'scenario_last_choice',json.dumps({'script_id':request.script_id,
                                'timepoint':request.timepoint,'choice':request.choice})))
                    return None
                if message_id=='26_5':
                    with self.db:self.db.execute('INSERT OR REPLACE INTO role_snapshots VALUES (?,?,?)',
                        (session.role_id,'scenario_skip_requested',json.dumps({'time':now})))
                    return None
                history=self.snapshot(session.role_id,'scenario_history',{'list':[]})
                if not any(int(v['k'])==request.script_id for v in history['list']):
                    history['list'].append({'k':str(request.script_id),'v':'1'})
                with self.db:
                    self.db.execute('INSERT OR REPLACE INTO role_snapshots VALUES (?,?,?)',
                        (session.role_id,'scenario_history',json.dumps(history)))
                    cursor={'script_id':0,'timepoint':0,'cur_sublist':[],'chosen_sublist':[],'next_list':[]}
                    self.db.execute('INSERT OR REPLACE INTO role_snapshots VALUES (?,?,?)',
                        (session.role_id,'scenario_cursor',json.dumps(cursor)))
                response={'script_id':request.script_id}
            elif message_id in ('2_9','2_10'):
                if not session.role_id:raise PermissionError('select a role first')
                if message_id=='2_10':
                    if request.stage not in range(23,31):raise ValueError('unsupported tutorial stage')
                    with self.db:
                        self.db.execute('INSERT OR REPLACE INTO role_snapshots VALUES (?,?,?)',
                            (session.role_id,'tutorial_stage',json.dumps({'stage':request.stage})))
                    response={'code':0,'stage':request.stage}
                else:response=self.tutorial_stage(session.role_id)
            elif message_id == '4_17':
                if not session.role_id:raise PermissionError('select a role first')
                # MapController.On_4_17 branches type==0 to ReturnToFloor;
                # its other branch enters the PvP simulator.
                response={'type':0}
            elif message_id == '4_20':
                response={'code':0}
            elif message_id == '4_29':
                rows=self.db.execute('SELECT mon_id,count FROM monster_guides WHERE uid=? ORDER BY mon_id',(session.uid,))
                response={'guide_list':[{'k':row['mon_id'],'v':str(row['count'])} for row in rows]}
            elif message_id == '4_30':
                with self.db:
                    self.db.execute('INSERT INTO monster_guides VALUES (?,?,1) ON CONFLICT(uid,mon_id) DO UPDATE SET count=count+1',
                        (session.uid,str(request.mon_id)))
                count=self.db.execute('SELECT count FROM monster_guides WHERE uid=? AND mon_id=?',
                    (session.uid,str(request.mon_id))).fetchone()['count']
                response={'mon_id':str(request.mon_id),'count':count}
            elif message_id == '4_31':
                with self.db:self.db.execute('INSERT OR REPLACE INTO account_views VALUES (?,?)',(session.uid,request.view))
                response={'code':0,'view':request.view}
            elif message_id == '4_26':
                if len(request.mon_id_list)>1024:raise ValueError('too many monster IDs')
                states=[]
                for mon_id in request.mon_id_list:
                    row=self.db.execute('SELECT status FROM monster_states WHERE uid=? AND role_id=? AND mon_id=?',
                        (session.uid,session.role_id or 0,mon_id)).fetchone()
                    states.append({'mon_id':mon_id,'status':row['status'] if row else 0})
                response={'code':0,'kill_mon_list':states}
            elif message_id == '1_2':
                name = request.name.strip()
                if not name or len(name) > 24: raise ValueError('invalid role name')
                # Error codes remain unverified: never invent client-visible codes.
                with self.db:
                    cursor = self.db.execute('INSERT INTO roles (uid,name,sex,last_login_time) VALUES (?,?,?,?)',
                                             (session.uid,name,request.sex,now))
                row = self.db.execute('SELECT * FROM roles WHERE id=?', (cursor.lastrowid,)).fetchone()
                response = {'code':0, 'role_info':self.role(row)}
            elif message_id == '1_3':
                row = self.db.execute('SELECT * FROM roles WHERE id=? AND uid=?',
                                      (request.id,session.uid)).fetchone()
                if not row: raise PermissionError('role does not belong to account')
                with self.db:
                    self.db.execute('UPDATE roles SET last_login_time=? WHERE id=?', (now,request.id))
                session.role_id = request.id
                pushes.append(('2_2',self.role_attributes(row)))
                pushes.append(('2_9',self.tutorial_stage(row['id'])))
                response = {'code':0, 'id':request.id}
            elif message_id == '1_6':
                if request.amount > 20: raise ValueError('too many names')
                response = {'sex':request.sex, 'list':['Player'+secrets.token_hex(3) for _ in range(request.amount)]}
            else:
                raise NotImplementedError(f'handler not reconstructed: {message_id}')
        result=(message_id,self.protocol.encode('s2c',message_id,response))
        if pushes:
            # Identity must exist for the login callback; tutorial actions run
            # after the callback has marked the connection as in-game.
            encoded=[(key,self.protocol.encode('s2c',key,values)) for key,values in pushes]
            return [v for v in encoded if v[0]=='2_2']+[result]+[v for v in encoded if v[0]!='2_2']
        return result
