import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
import threading
import sqlite3
from contextlib import closing
import urllib.request
import urllib.error
from game_server.protocol import Protocol
from game_server.core import GameCore, Session
from game_server.wire import FrameProfile
from game_server.snpacket import SNPacket
from game_server.bootstrap import make_server


ROOT = Path(__file__).resolve().parents[1]


def initialize(message):
    for field in message.DESCRIPTOR.fields:
        if field.label != field.LABEL_REQUIRED: continue
        if field.message_type: initialize(getattr(message,field.name))
        elif field.type == field.TYPE_STRING: setattr(message,field.name,'test')
        elif field.type == field.TYPE_BYTES: setattr(message,field.name,b'')
        elif field.type == field.TYPE_ENUM: setattr(message,field.name,field.enum_type.values[0].number)
        elif field.type == field.TYPE_BOOL: setattr(message,field.name,False)
        else: setattr(message,field.name,0)
    return message


class ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.protocol = Protocol(ROOT/'analysis')

    def test_every_mapped_message_roundtrip(self):
        count = 0
        for direction,mapping in self.protocol.ids.items():
            for key in mapping:
                message = initialize(self.protocol.make(direction,key))
                encoded = message.SerializeToString()
                self.assertEqual(self.protocol.decode(direction,key,encoded),message)
                count += 1
        self.assertEqual(count,1048)
        self.assertEqual(len(self.protocol.files),57)
        self.assertEqual(len(self.protocol.inactive_files),5)

    def test_missing_required_fields_rejected(self):
        with self.assertRaises(ValueError): self.protocol.decode('c2s','1_1',b'')

    def test_known_login_ids(self):
        for number in (0,1,2,3,4,6,7):
            key = f'1_{number}'
            self.assertEqual(self.protocol.ids['c2s'][key][:-3],self.protocol.ids['s2c'][key][:-3])


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.now = 1800000000
        self.protocol = Protocol(ROOT/'analysis')
        self.core = GameCore(self.protocol,clock=lambda:self.now)
        self.session = Session()
        self.credentials = self.core.issue_local_credentials('local-test')
        auth = initialize(self.protocol.make('c2s','1_1'))
        for key in ('uid','uname','p_key','time','token'): setattr(auth,key,self.credentials[key])
        self.auth = auth

    def tearDown(self): self.core.close()

    def call(self,key,values=None,session=None):
        payload = self.protocol.encode('c2s',key,values) if values is not None else self.auth.SerializeToString()
        response=self.core.handle(session or self.session,key,payload)
        response_key,payload=next((k,v) for k,v in response if k==key) if isinstance(response,list) else response
        return self.protocol.decode('s2c',response_key,payload)

    def test_auth_create_select_and_reconnect(self):
        self.assertEqual(self.call('1_1').code,0)
        role = self.call('1_2',{'name':'Tester','sex':1}).role_info
        selected = self.call('1_3',{'id':str(role.id)})
        self.assertEqual(selected.id,role.id)
        self.assertEqual(len(self.call('1_1').role_list),1)
        reconnect = Session()
        self.call('1_4',{'id':str(role.id),'p_key':self.credentials['p_key'],
                        'time':self.now,'token':self.credentials['token'],
                        'game_version':'test','login_sid':1,'proto_num':0},reconnect)
        self.assertEqual(reconnect.role_id,role.id)

    def test_invalid_and_expired_credentials(self):
        self.auth.token = 'wrong'
        with self.assertRaises(PermissionError): self.call('1_1')
        self.auth.token = self.credentials['token']
        self.now += 3601
        with self.assertRaises(PermissionError): self.call('1_1')

    def test_create_requires_auth(self):
        with self.assertRaises(PermissionError): self.call('1_2',{'name':'X','sex':1})

    def test_cross_account_role_denied(self):
        self.call('1_1')
        role = self.call('1_2',{'name':'Owner','sex':0}).role_info
        with self.assertRaises(PermissionError):
            self.call('1_3',{'id':str(role.id)},Session(uid='other-account'))

    def test_heartbeat(self):
        result = self.call('1_0',{'index':23,'client_time':self.now,'server_time':0})
        self.assertEqual(result.index,23)
        self.assertEqual(result.server_time,self.now)

    def test_pre_role_tutorial_report_is_one_way_and_idempotent(self):
        self.call('1_1')
        self.assertNotIn('47_3',self.protocol.ids['s2c'])
        payload=self.protocol.encode('c2s','47_3',{'uid':self.credentials['uid'],'map_id':'10001',
            'child_id_list':['1','2'],'result':1,'start_time':self.now,'dup_time':30})
        for _ in range(2):self.assertIsNone(self.core.handle(self.session,'47_3',payload))
        self.assertEqual(self.core.db.execute('SELECT COUNT(*) FROM tutorial_fights').fetchone()[0],1)
        revised=self.protocol.make('c2s','47_3')
        revised.ParseFromString(payload);revised.result=2;revised.dup_time=32
        self.core.handle(self.session,'47_3',revised.SerializeToString())
        self.assertEqual(self.core.db.execute('SELECT result FROM tutorial_fights').fetchone()[0],2)
        self.assertEqual(self.core.db.execute('SELECT COUNT(*) FROM tutorial_fights').fetchone()[0],1)
        with self.assertRaises(PermissionError):self.core.handle(Session(uid='other'),'47_3',payload)

    def test_monster_history_query_reads_account_state(self):
        self.call('1_1')
        self.assertEqual(self.call('4_26',{'mon_id_list':[1001]}).kill_mon_list[0].status,0)
        with self.core.db:
            self.core.db.execute('INSERT INTO monster_states VALUES (?,?,?,?)',
                                 (self.session.uid,0,1001,1))
        self.assertEqual(self.call('4_26',{'mon_id_list':[1001]}).kill_mon_list[0].status,1)
        self.assertEqual(self.call('4_26',{'mon_id_list':[1001]},Session(uid='other')).kill_mon_list[0].status,0)

    def test_tutorial_guide_history_and_view_persist(self):
        self.call('1_1')
        for count in (1,2):self.assertEqual(self.call('4_30',{'mon_id':'9001'}).count,count)
        guides=self.call('4_29',{}).guide_list
        self.assertEqual([(v.k,v.v) for v in guides],[(9001,2)])
        self.assertFalse(self.call('4_29',{},Session(uid='other')).guide_list)
        self.assertEqual(self.call('4_31',{'view':1}).view,1)
        self.assertEqual(self.core.db.execute('SELECT view FROM account_views WHERE uid=?',(self.session.uid,)).fetchone()[0],1)

    def test_selected_role_pushes_identity_before_ack_and_configured_vitality(self):
        self.call('1_1')
        role=self.call('1_2',{'name':'Identity','sex':1}).role_info
        response=self.core.handle(self.session,'1_3',self.protocol.encode('c2s','1_3',{'id':str(role.id)}))
        self.assertEqual([key for key,payload in response],['2_2','1_3','2_9'])
        attributes=self.protocol.decode('s2c',*response[0])
        numbers={v.k:v.v for v in attributes.kv_list};strings={v.k:v.s for v in attributes.ks_list}
        self.assertEqual(numbers[601],role.id);self.assertEqual(strings[602],'Identity')
        self.assertEqual(numbers[610],720)
        self.assertEqual(numbers[502],200)
        again=self.core.role_attributes(self.core.db.execute('SELECT * FROM roles WHERE id=?',(role.id,)).fetchone())
        self.assertEqual(next(v['v']for v in again['kv_list']if v['k']==502),'200')
        vitality=self.call('13_1',{})
        self.assertEqual((vitality.vitality,vitality.vit_max),(30,30))
        self.assertFalse(self.call('3_1',{}).info)
        self.assertEqual(self.call('18_5',{'type':2}).type,2)
        opened=set(self.call('24_1',{}).list)
        self.assertTrue({1,15,17,20,21,22}.issubset(opened))
        self.assertNotIn(40,opened)  # Island requires normal dungeon 10210.
        self.assertNotIn(45,opened)  # Auto battle requires normal dungeon 10102.

    def test_tutorial_stage_resumes_without_skipping_and_requires_role(self):
        self.call('1_1')
        with self.assertRaises(PermissionError):self.call('2_9',{})
        role=self.call('1_2',{'name':'Tutorial','sex':1}).role_info
        self.call('1_3',{'id':str(role.id)})
        self.assertEqual(self.call('2_9',{}).stage,23)
        self.assertEqual(self.call('2_10',{'stage':24}).stage,24)
        self.assertEqual(self.call('2_9',{}).stage,24)
        with self.assertRaises(ValueError):self.call('2_10',{'stage':10086})

    def test_scenario_cursor_and_completion_persist_without_duplicate_history(self):
        self.call('1_1')
        role=self.call('1_2',{'name':'Story','sex':1}).role_info
        self.call('1_3',{'id':str(role.id)})
        payload=self.protocol.encode('c2s','26_2',{'script_id':123,'choice':0,'timepoint':5})
        self.assertIsNone(self.core.handle(self.session,'26_2',payload))
        cursor=self.call('26_1',{})
        self.assertEqual((cursor.script_id,cursor.timepoint),(123,5))
        for _ in range(2):self.assertEqual(self.call('26_3',{'script_id':123,'quit_flag':0}).script_id,123)
        self.assertEqual(self.call('26_1',{}).script_id,0)
        history=self.call('26_4',{}).list
        self.assertEqual([(v.k,v.v)for v in history],[(123,1)])
        for key,values,table in [('47_1',{'map_id':'1','child_id_list':['2']},'tutorial_entries'),
             ('47_2',{'map_id':'1','result':1,'dup_time':10,'goal':0,'cnt':'1',
                       'child_id_list':['2'],'depolylist':[],'deaths':[]},'tutorial_results')]:
            data=self.protocol.encode('c2s',key,values)
            self.assertIsNone(self.core.handle(self.session,key,data))
            self.assertEqual(self.core.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],1)

    def test_role_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp)/'state.sqlite3')
            core = GameCore(self.protocol,path)
            with core.db:
                core.db.execute("INSERT INTO roles(uid,name,sex,last_login_time) VALUES ('u','Saved',0,1)")
            core.close()
            core = GameCore(self.protocol,path)
            try: self.assertEqual(core.db.execute('SELECT name FROM roles').fetchone()[0],'Saved')
            finally: core.close()

    def test_max_affection_unlocks_files_and_preserves_skins_and_read_state(self):
        from game_server.affection import maximize
        self.call('1_1')
        role=self.call('1_2',{'name':'Files','sex':1}).role_info
        self.call('1_3',{'id':str(role.id)})
        profile={'cards':[{'sys_id':3008,'favor':0,'favor_lvl':0,'use_skin':'keep-skin'}],
                 'heroes':[],'custom_state':'preserve'}
        maximize(profile,ROOT/'analysis')
        self.assertEqual((profile['cards'][0]['favor_lvl'],profile['cards'][0]['favor']),(5,1252000))
        self.assertEqual(profile['cards'][0]['use_skin'],'keep-skin')
        self.core.snapshot(role.id,'sandbox_gm',profile)
        unlocked=self.call('11_16',{})
        self.assertEqual(len(unlocked.char_list),2)
        entry=unlocked.char_list[0]
        self.assertEqual(entry.v,0)
        self.call('11_37',{'type':1,'sys_id':entry.k})
        self.assertEqual(self.call('11_16',{}).char_list[0].v,1)
        with self.assertRaises(PermissionError):self.call('11_37',{'type':1,'sys_id':999})
        updated=self.core.sandbox(role.id)
        maximize(updated,ROOT/'analysis')
        self.assertEqual(updated['documents']['char_list'][0]['v'],'1')
        self.assertEqual(updated['custom_state'],'preserve')

    def test_team_edits_validate_ownership_slots_and_preserve_event_isolation(self):
        self.call('1_1');role=self.call('1_2',{'name':'Teams','sex':1}).role_info
        self.call('1_3',{'id':str(role.id)})
        self.core.snapshot(role.id,'sandbox_gm',{'cards':[{'id':'101'},{'id':'102'}],
            'heroes':[{'id':'1001','form_list':[{'form':1},{'form':2}]}]})
        team=self.call('15_4',{'event_id':'123'}).children_team[0]
        values={'team_index':1,'team_id':str(team.team_id),'event_id':'123',
                'children_list':[{'k':'2','v':'102'}],'fetter_child_list':[]}
        changed=self.call('15_2',values).children_team
        self.assertEqual([(v.k,v.v)for v in changed.children_list],[(2,102)])
        self.call('15_3',{'team_index':'1','event_id':'123','team_name':'Test team'})
        payload=self.protocol.encode('c2s','15_1',{'team_id':str(team.team_id),
            'hero_list':[{'index':1,'hero_id':'1001','hero_form':2}]})
        self.assertIsNone(self.core.handle(self.session,'15_1',payload))
        self.assertEqual(self.call('15_4',{'event_id':'123'}).children_team[0].hero_list[0].hero_form,2)
        self.assertEqual(self.call('15_4',{'event_id':'123'}).children_team[0].team_name,'Test team')
        self.assertEqual(len(self.call('15_4',{'event_id':'456'}).children_team[0].children_list),2)
        values['children_list']=[{'k':'1','v':'999'}]
        with self.assertRaises(PermissionError):self.call('15_2',values)
        values['children_list']=[{'k':'1','v':'101'},{'k':'1','v':'102'}]
        with self.assertRaises(ValueError):self.call('15_2',values)
        self.assertEqual(self.call('15_4',{'event_id':'123'}).children_team[0].children_list[0].v,102)

    def test_explicit_gm_profile_is_backed_up_persistent_and_role_scoped(self):
        from tools.enable_sandbox_profile import enable
        self.call('1_1')
        role=self.call('1_2',{'name':'GM','sex':1}).role_info
        other=self.call('1_2',{'name':'Ordinary','sex':1}).role_info
        with tempfile.TemporaryDirectory()as tmp:
            path=Path(tmp)/'state.sqlite3'
            with closing(sqlite3.connect(path))as target:self.core.db.backup(target)
            result=enable(path,role.id,ROOT/'analysis')
            with closing(sqlite3.connect(result['backup']))as backup:
                self.assertEqual(backup.execute('SELECT level FROM roles WHERE id=?',(role.id,)).fetchone()[0],1)
            self.core.close();self.core=GameCore(self.protocol,path,clock=lambda:self.now)
            self.call('1_3',{'id':str(role.id)})
            self.assertEqual(self.core.db.execute('SELECT level FROM roles WHERE id=?',(role.id,)).fetchone()[0],100)
            self.assertEqual(self.core.db.execute('SELECT level FROM roles WHERE id=?',(other.id,)).fetchone()[0],1)
            cards=self.call('11_1',{}).children_list
            self.assertEqual(len(cards),75);self.assertEqual(len({c.id for c in cards}),75)
            for c in cards:
                self.assertGreaterEqual(c.lvl,80)
                self.assertIn(c.use_skin,c.skin_list)
            heroes=self.call('35_1',{}).list
            self.assertEqual(len(heroes[0].form_list),8)
            self.assertEqual(set(self.call('24_1',{}).list),{r['id']for r in self.core.open_functions.values()})
            team=self.call('15_4',{'event_id':'1'}).children_team[0]
            self.assertTrue(all(v.v in {c.id for c in cards}for v in team.children_list))
            self.assertEqual(self.call('11_45',{}).num,75)
            card=cards[0]
            self.call('11_20',{'id':str(card.id),'skin_id':str(card.skin_list[-1])})
            self.assertEqual(self.call('11_1',{}).children_list[0].use_skin,card.skin_list[-1])
            with self.assertRaises(PermissionError):self.call('11_20',{'id':str(card.id),'skin_id':'999'})
            self.assertEqual(self.call('2_5',{}).info.children_num,75)
            self.assertEqual(len(self.call('35_7',{}).skin_list[0].skin_list),8)
            form=heroes[0].form_list[0]
            self.call('35_8',{'hero_id':str(heroes[0].id),'form':form.form,'skin_id':str(form.skin_list[-1])})
            self.assertEqual(self.call('35_9',{'hero_id':str(heroes[0].id)}).skin_info.skin_list[0].use_skin,form.skin_list[-1])
            self.assertEqual(self.call('2_9',{}).stage,29)
            self.call('1_3',{'id':str(other.id)})
            self.assertNotIn(40,self.call('24_1',{}).list)
            with self.assertRaises(NotImplementedError):self.call('11_1',{})
            self.core.close();self.core=GameCore(self.protocol,clock=lambda:self.now)


class WireTests(unittest.TestCase):
    def test_real_connection_preface_is_consumed_once(self):
        client=SNPacket(ROOT/'analysis/packet_xor_table.bin')
        server=SNPacket(ROOT/'analysis/packet_xor_table.bin',expect_preface=True)
        packet=client.encode_c2s('1_0',b'abc',100)
        buffer=bytearray(b'\x01')
        self.assertIsNone(server.pop(buffer))
        buffer.extend(b'\x02'+packet+packet)
        self.assertEqual(server.pop(buffer),('1_0',b'abc'))
        self.assertEqual(server.pop(buffer),('1_0',b'abc'))
        self.assertFalse(buffer)
    def test_snpacket_asymmetric_headers(self):
        codec=SNPacket(ROOT/'analysis/packet_xor_table.bin')
        request=codec.encode_c2s('1_0',b'abc',100)
        self.assertEqual(request[:6],b'\x00\x07\x00\x64\x01\x00')
        self.assertEqual(codec.pop(bytearray(request)),('1_0',b'abc'))
        response=codec.encode('1_0',b'abc')
        self.assertEqual(response[:5],b'\x00\x06\x01\x00\x00')
        self.assertEqual(codec.pop_s2c(bytearray(response)),('1_0',b'abc'))
        self.assertNotEqual(request[-3:],response[-3:])

    def test_snpacket_xor_wrap_and_coalescing(self):
        codec=SNPacket(ROOT/'analysis/packet_xor_table.bin')
        payload=bytes(range(256))*3
        frame=codec.encode_c2s('57_3',payload,65535)
        buffer=bytearray(frame[:1])
        self.assertIsNone(codec.pop(buffer))
        buffer.extend(frame[1:]+frame)
        for _ in range(2):self.assertEqual(codec.pop(buffer),('57_3',payload))
        self.assertFalse(buffer)

    def test_fragmentation_and_coalescing(self):
        for order in ('big','little'):
            for includes in (False,True):
                profile = FrameProfile(4,2,order,includes)
                frame = profile.encode('1_0',b'abc')
                buffer = bytearray(frame[:3])
                self.assertIsNone(profile.pop(buffer))
                buffer.extend(frame[3:]+frame)
                self.assertEqual(profile.pop(buffer),('1_0',b'abc'))
                self.assertEqual(profile.pop(buffer),('1_0',b'abc'))
                self.assertEqual(buffer,b'')

    def test_invalid_frame_lengths(self):
        profile = FrameProfile(4,2,'big',False,max_frame=1024)
        for size in (0,3,1025):
            with self.assertRaises(ValueError): profile.pop(bytearray(size.to_bytes(4,'big')))

    def test_loopback_listener_heartbeat(self):
        # Synthetic test framing, explicitly NOT evidence of game compatibility.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            profile_data = {'status':'synthetic-test-only','frame':{
                'length_bytes':4,'id_bytes':2,'byteorder':'big','length_includes_prefix':False}}
            (path/'profile.json').write_text(json.dumps(profile_data))
            process = subprocess.Popen([sys.executable,'-u','-m','game_server',
                '--profile',str(path/'profile.json'),'--database',str(path/'state.sqlite3'),
                '--port','0'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                line = process.stdout.readline()
                if not line: self.fail(process.stderr.read())
                import ast
                address = ast.literal_eval(json.loads(line)['listening'])
                protocol = Protocol(ROOT/'analysis')
                profile = FrameProfile(**profile_data['frame'])
                payload = protocol.encode('c2s','1_0',{'index':99,'client_time':0,'server_time':0})
                with socket.create_connection(address,timeout=3) as connection:
                    connection.sendall(profile.encode('1_0',payload))
                    buffer = bytearray()
                    frame = None
                    while frame is None:
                        data = connection.recv(4096)
                        self.assertTrue(data)
                        buffer.extend(data)
                        frame = profile.pop(buffer)
                    self.assertEqual(protocol.decode('s2c',*frame).index,99)
            finally:
                process.terminate()
                process.communicate(timeout=5)

    def test_loopback_snpacket(self):
        with tempfile.TemporaryDirectory() as tmp:
            process=subprocess.Popen([sys.executable,'-u','-m','game_server',
                '--database',str(Path(tmp)/'state.sqlite3'),'--port','0'],
                cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                import ast
                address=ast.literal_eval(json.loads(process.stdout.readline())['listening'])
                protocol=Protocol(ROOT/'analysis');codec=SNPacket(ROOT/'analysis/packet_xor_table.bin')
                payload=protocol.encode('c2s','1_0',{'index':123,'client_time':0,'server_time':0})
                with socket.create_connection(address,timeout=3) as connection:
                    frame=codec.encode_c2s('1_0',payload,100)
                    connection.sendall(b'\x01\x02'+frame[:3]);connection.sendall(frame[3:])
                    buffer=bytearray();response=None
                    while response is None:
                        part=connection.recv(4096);self.assertTrue(part);buffer.extend(part)
                        response=codec.pop_s2c(buffer)
                    self.assertEqual(protocol.decode('s2c',*response).index,123)
            finally:
                process.terminate();process.communicate(timeout=5)


class BootstrapTests(unittest.TestCase):
    def test_mock_client_auth_is_explicit_and_accepts_form(self):
        with tempfile.TemporaryDirectory() as tmp:
            for enabled in (False,True):
                server=make_server(Protocol(ROOT/'analysis'),str(Path(tmp)/'db.sqlite3'),0,19090,
                                   allow_local_client_login=enabled)
                thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
                req=urllib.request.Request('http://127.0.0.1:'+str(server.server_address[1])+'/fn/login_auth',
                    data=b'uid=local-device-test&name=Local',headers={'Content-Type':'application/x-www-form-urlencoded'})
                try:
                    if enabled:
                        with urllib.request.urlopen(req,timeout=3) as response:
                            result=json.load(response)
                            self.assertEqual(result['code'],0)
                            self.assertEqual(result['data']['uid'],'local-device-test')
                    else:
                        with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(req,timeout=3)
                        self.assertEqual(error.exception.code,404)
                finally:server.shutdown();server.server_close();thread.join(timeout=3)

    def test_cdn_only_serves_verified_explicit_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixtures=root/'fixtures';fixtures.mkdir()
            (fixtures/'config.txt').write_bytes(b'default public\n')
            (fixtures/'bundle.ab').write_bytes(b'verified fixture bytes')
            (fixtures/'routes.json').write_text(json.dumps({'Zero/GameVersion_123.ab':'bundle.ab',
                                                          'escape.ab':'../outside.txt'}))
            (root/'outside.txt').write_text('private')
            server=make_server(Protocol(ROOT/'analysis'),str(root/'db.sqlite3'),0,19090,fixtures)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base='http://127.0.0.1:'+str(server.server_address[1])
            try:
                with urllib.request.urlopen(base+'/cdnconfig_1/config.txt',timeout=3) as response:
                    self.assertEqual(response.read(),b'default public\n')
                with urllib.request.urlopen(base+'/cdnconfig_1/res/Zero/GameVersion_123.ab',timeout=3) as response:
                    self.assertEqual(response.read(),b'verified fixture bytes')
                for route,status in [('escape.ab',400),('unknown.ab',404)]:
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(base+'/cdnconfig_1/res/'+route,timeout=3)
                    self.assertEqual(error.exception.code,status)
            finally:server.shutdown();server.server_close();thread.join(timeout=3)

    def test_http_credentials_work_with_protobuf_login(self):
        with tempfile.TemporaryDirectory() as tmp:
            protocol=Protocol(ROOT/'analysis');database=str(Path(tmp)/'state.sqlite3')
            server=make_server(protocol,database,0,19090)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                base='http://127.0.0.1:'+str(server.server_address[1])
                req=urllib.request.Request(base+'/local/login',data=b'{"uid":"http-test"}',
                                           headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(req,timeout=3) as response:
                    credentials=json.load(response)['data']
                message=initialize(protocol.make('c2s','1_1'))
                for k in ('uid','uname','token','p_key','time'):setattr(message,k,credentials[k])
                core=GameCore(protocol,database)
                try:
                    key,payload=core.handle(Session(),'1_1',message.SerializeToString())
                    self.assertEqual(protocol.decode('s2c',key,payload).code,0)
                    core.handle(Session(uid='http-test'),'1_2',protocol.encode('c2s','1_2',{'name':'SavedHTTP','sex':1}))
                finally:core.close()
                req=urllib.request.Request(base+'/client/select_region',
                    data=json.dumps(credentials).encode(),headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(req,timeout=3) as response:
                    data=json.load(response)['data']
                    selected=dict(zip(data['server_key'],data['serv_list'][0]))
                    self.assertEqual(selected['serv_port'],19090)
                    self.assertEqual(selected['name'],'Local test')
                req=urllib.request.Request(base+'/client/role_region_list',
                    data=json.dumps(credentials).encode(),headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(req,timeout=3) as response:
                    data=json.load(response)['data']
                    self.assertEqual(dict(zip(data['role_key'],data['role_list'][0]))['name'],'SavedHTTP')
                with urllib.request.urlopen(base+'/cdnconfig_1/serverlists/announcement/local.txt',timeout=3) as response:
                    self.assertEqual(json.load(response),{'data':[]})
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(base+'/unimplemented',timeout=3)
                self.assertEqual(error.exception.code,404)
            finally:server.shutdown();server.server_close();thread.join(timeout=3)


if __name__ == '__main__': unittest.main()
