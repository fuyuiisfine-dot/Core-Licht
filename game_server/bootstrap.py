"""Local HTTP bootstrap; phone login verified, full gameplay incomplete.

No publisher credential verification is implemented. /local/login only issues
local testing credentials, and is not mapped to publisher SDK endpoints.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit, parse_qs
from .core import GameCore
from .network import NetworkPolicy


def make_handler(protocol,database,http_port,game_port,fixtures=None,request_log=None,allow_local_client_login=False):
    fixture_root=Path(fixtures).resolve() if fixtures else None
    fixture_routes=json.loads((fixture_root/'routes.json').read_text()) if fixture_root and (fixture_root/'routes.json').is_file() else {}
    log_lock=threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,fmt,*args): pass  # never log login credentials

        def send_json(self,status,body):
            data=json.dumps(body,ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path=urlsplit(self.path).path
            if request_log:
                with log_lock:
                    with Path(request_log).open('a',encoding='utf-8') as log:
                        log.write(json.dumps({'time':int(time.time()),'method':'GET','path':path})+'\n')
            if fixture_root and path.startswith('/cdnconfig_'):
                # Explicit CDN fixtures only; no directory listings or source assets.
                name=path.rsplit('/',1)[-1]
                relative=path.partition('/res/')[2]
                mapped=fixture_routes.get(relative)
                if name in ('config.txt','DriverVersion.txt') or mapped:
                    target=(fixture_root/(mapped or name)).resolve()
                    if fixture_root not in target.parents:
                        self.send_json(400,{'error':'invalid fixture path'});return
                    if target.is_file():
                        body=target.read_bytes()
                        self.send_response(200)
                        self.send_header('Content-Type','text/plain; charset=utf-8')
                        self.send_header('Content-Length',str(len(body)))
                        self.end_headers();self.wfile.write(body);return
            if path=='/health':
                self.send_json(200,{'status':'prototype','client_verified':False})
            elif '/serverlists/announcement/' in path:
                self.send_json(200,{'data':[]})
            elif path.endswith('/serv_list.txt'):
                self.send_json(200,{'list':[{'id':1,'name':'Local test',
                    'ip':f'{self.connection.getsockname()[0]}:{http_port}','cp':[],'type':0}],'tips':''})
            else:self.send_json(404,{'error':'route not reconstructed'})

        def do_POST(self):
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<=size<=16384:raise ValueError('request too large')
                path=urlsplit(self.path).path
                body=self.rfile.read(size)
                if 'application/x-www-form-urlencoded' in self.headers.get('Content-Type',''):
                    values={k:v[-1] for k,v in parse_qs(body.decode('utf-8')).items()}
                else:values=json.loads(body or b'{}')
                if not isinstance(values,dict):raise ValueError('JSON object required')
                if request_log:
                    with log_lock:
                        with Path(request_log).open('a',encoding='utf-8') as log:
                            log.write(json.dumps({'time':int(time.time()),'method':'POST',
                                'path':path,'fields':sorted(values)})+'\n')
                core=GameCore(protocol,database)
                try:
                    now=int(time.time())
                    local_client_route=path in ('/fn/login_auth','/tw/android_login_auth','/exe/login_auth')
                    if path=='/local/login' or (allow_local_client_login and local_client_route):
                        uid=values.get('uid') or values.get('name')
                        if not isinstance(uid,str):raise ValueError('uid string required')
                        response={'code':0,'data':dict(core.issue_local_credentials(uid),
                            time_zone=8,serv_time=now,is_white_ip=1,ios_auth=0)}
                    elif path.startswith('/local/game/') and allow_local_client_login:
                        from .native_game import handle
                        response={'code':0,'data':handle(core,path.removeprefix('/local/game/'),values)}
                    elif path in ('/client/role_region_list','/client/select_region'):
                        if not core.valid(str(values.get('uid','')),str(values.get('token','')),str(values.get('p_key',''))):
                            self.send_json(403,{'error':'local credentials required'});return
                        data={'serv_time':now,'time_zone':8}
                        if path.endswith('role_region_list'):
                            # Header/row representation is observed; individual region
                            # columns remain inferred and need real-client confirmation.
                            data.update(region_key=['id','name','open_time','status','server_id','region_id'],
                                region_list=[[1,'Local test',now-86400,1,1,1]],
                                role_key=['region_id','id','name','level'],
                                role_list=[[1,r['id'],r['name'],r['level']] for r in
                                    core.db.execute('SELECT id,name,level FROM roles WHERE uid=? ORDER BY id',
                                                    (str(values['uid']),))])
                        else:
                            # MainFrameView.RefreshTestInfos also concatenates
                            # selectedGameServer.name; omission aborts view opening.
                            data.update(server_key=['serv_ip','serv_port','convert_ip_port','server_id','id','name'],
                                serv_list=[[self.connection.getsockname()[0],game_port,[],1,1,'Local test']],login_sid=1)
                        response={'code':0,'data':data}
                    else:
                        self.send_json(404,{'error':'route not reconstructed'});return
                    self.send_json(200,response)
                finally:core.close()
            except PermissionError:self.send_json(403,{'error':'local credentials or owned role required'})
            except (ValueError,TypeError,StopIteration) as error:self.send_json(400,{'error':str(error) or 'invalid request'})
    return Handler


def make_server(protocol,database,http_port,game_port,fixtures=None,request_log=None,allow_local_client_login=False,listen_host='127.0.0.1',allowed_networks=()):
    policy=NetworkPolicy(allowed_networks)
    class Server(ThreadingHTTPServer):
        def verify_request(self,request,client_address):
            return policy.allows(client_address[0])
    return Server((listen_host,http_port),
        make_handler(protocol,database,http_port,game_port,fixtures,request_log,allow_local_client_login))
