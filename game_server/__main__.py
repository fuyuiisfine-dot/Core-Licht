"""Loopback server with reconstructed SNPacket transport."""
import argparse
import importlib
import json
import socket
import socketserver
import threading
import time
from google.protobuf.message import DecodeError
from pathlib import Path
from .core import GameCore, Session
from . import core as core_module
from .protocol import Protocol
from .wire import FrameProfile
from .snpacket import SNPacket
from .bootstrap import make_server


def serve(args):
    config = json.loads(Path(args.profile).read_text()) if args.profile else {'status':'APK static reconstruction; awaiting client validation'}
    profile = FrameProfile(**config['frame']) if args.profile else SNPacket(Path(args.analysis)/'packet_xor_table.bin')
    protocol = Protocol(args.analysis)
    core = GameCore(protocol, args.database)
    if args.issue_uid:
        print(json.dumps({'local_credentials':core.issue_local_credentials(args.issue_uid)}),flush=True)

    core.close()
    event_lock=threading.Lock()
    code_lock=threading.Lock()
    module_stamp=Path(core_module.__file__).stat().st_mtime_ns if args.reload_core else 0
    def record(event):
        event={'time':int(time.time()),**event}
        if args.protocol_log:
            with event_lock:
                with Path(args.protocol_log).open('a',encoding='utf-8') as log:
                    log.write(json.dumps(event)+'\n')

    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            nonlocal module_stamp
            session,buffer = Session(),bytearray()
            connection_profile=profile if args.profile else SNPacket(Path(args.analysis)/'packet_xor_table.bin',expect_preface=True)
            connection_core = core_module.GameCore(protocol,args.database)
            core_stamp=module_stamp
            pending=[]
            self.request.settimeout(1 if args.reload_core else 60)

            def dispatch(frame):
                try:response=connection_core.handle(session,*frame)
                except NotImplementedError:
                    if not args.reload_core:raise
                    if len(pending)>=128:raise ValueError('too many pending local test requests')
                    pending.append(frame)
                    record({'pending_handler':frame[0]})
                    return
                if response is not None:
                    for response_id,payload in (response if isinstance(response,list) else [response]):
                        self.request.sendall(connection_profile.encode(response_id,payload))
                        record({'direction':'s2c','id':response_id,'payload_bytes':len(payload)})

            try:
                while True:
                    if args.reload_core:
                        stamp=Path(core_module.__file__).stat().st_mtime_ns
                        if stamp!=core_stamp:
                            with code_lock:
                                if stamp!=module_stamp:
                                    importlib.invalidate_caches()
                                    importlib.reload(core_module)
                                    module_stamp=stamp
                                connection_core.close()
                                connection_core=core_module.GameCore(protocol,args.database)
                                core_stamp=stamp
                            retry=pending[:];pending.clear()
                            for frame in retry:dispatch(frame)
                            record({'core_reloaded':True})
                    try:data = self.request.recv(65536)
                    except socket.timeout:
                        if args.reload_core:continue
                        raise
                    if not data: break
                    buffer.extend(data)
                    if args.capture_first_packet and len(buffer)>=2:
                        offset=2 if buffer[:2]==b'\x01\x02' else 0
                        size=offset+2+int.from_bytes(buffer[offset:offset+2],'big')
                        capture=Path(args.capture_first_packet)
                        if len(buffer)>=size and not capture.exists():
                            capture.write_bytes(buffer[:size])
                    while (frame := connection_profile.pop(buffer)) is not None:
                        record({'direction':'c2s','id':frame[0],'payload_bytes':len(frame[1])})
                        dispatch(frame)
            except (ValueError,KeyError,DecodeError,PermissionError,NotImplementedError,socket.timeout) as error:
                print(json.dumps({'connection_closed':type(error).__name__}),flush=True)
            finally: connection_core.close()

    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True
        allow_reuse_address = True

    with Server(('127.0.0.1',args.port),Handler) as server:
        http_server = make_server(protocol,args.database,args.http_port,server.server_address[1],args.cdn_fixtures,args.request_log,args.allow_local_client_login) if args.http_port else None
        if http_server:
            threading.Thread(target=http_server.serve_forever,daemon=True).start()
        print(json.dumps({'listening':str(server.server_address),
                          'http_port':http_server.server_address[1] if http_server else None,
                          'profile_status':config.get('status','unverified'),
                          'client_compatibility':'full game flow not yet verified'}),flush=True)
        try:server.serve_forever()
        finally:
            if http_server:http_server.shutdown();http_server.server_close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',help='Optional synthetic frame profile; default is reconstructed SNPacket')
    parser.add_argument('--analysis',default='analysis')
    parser.add_argument('--database',default='server.sqlite3')
    parser.add_argument('--port',type=int,default=19090)
    parser.add_argument('--http-port',type=int,help='Optional prototype HTTP login listener')
    parser.add_argument('--cdn-fixtures',help='Explicit local config/driver fixtures for device validation')
    parser.add_argument('--request-log',help='GET route log without credentials or query strings')
    parser.add_argument('--allow-local-client-login',action='store_true',help='Enable mock auth routes for an SDK-disabled local testing client')
    parser.add_argument('--protocol-log',help='Message IDs and byte counts only; never payloads or credentials')
    parser.add_argument('--capture-first-packet',help='Optional private local-test wire fixture; may contain local-test credentials')
    parser.add_argument('--reload-core',action='store_true',help='Local development: reload core edits and retry up to 128 unimplemented requests')
    parser.add_argument('--issue-uid')
    serve(parser.parse_args())


if __name__ == '__main__': main()
