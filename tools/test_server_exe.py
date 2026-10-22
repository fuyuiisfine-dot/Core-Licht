"""Copy only the EXE, remove Python paths, then test TCP, gameplay and restart."""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from game_server.protocol import Protocol
from game_server.snpacket import SNPacket


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]


def initialize(message):
    for field in message.DESCRIPTOR.fields:
        if field.label != field.LABEL_REQUIRED:
            continue
        if field.message_type:
            initialize(getattr(message,field.name))
        else:
            setattr(message,field.name,'' if field.type==field.TYPE_STRING else b'' if field.type==field.TYPE_BYTES else False if field.type==field.TYPE_BOOL else field.enum_type.values[0].number if field.enum_type else 0)
    return message


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--exe',type=Path,required=True)
    p.add_argument('--analysis',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a = p.parse_args()
    folder = a.output.resolve()
    folder.mkdir(parents=True,exist_ok=False)
    executable = folder/'CoreLichtServer.exe'
    shutil.copy2(a.exe,executable)
    environment = dict(os.environ)
    for name in ('PYTHONPATH','PYTHONHOME'):
        environment.pop(name,None)
    environment['PATH'] = str(Path(os.environ['WINDIR'])/'System32')
    flags = subprocess.CREATE_NO_WINDOW
    checked = subprocess.run([str(executable),'--check'],env=environment,cwd=folder,stdin=subprocess.DEVNULL,
                             capture_output=True,text=True,creationflags=flags,timeout=30,check=True)
    assert json.loads(checked.stdout)['frozen'] is True
    with sqlite3.connect(folder/'server-data/server.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM accounts').fetchone()[0]==0
    http_port,game_port = free_port(),free_port()
    while game_port==http_port:
        game_port = free_port()
    protocol = Protocol(a.analysis.resolve())
    codec = SNPacket(a.analysis.resolve()/'packet_xor_table.bin')
    auth = None
    role = None

    def post(route,values):
        req = urllib.request.Request('http://127.0.0.1:'+str(http_port)+route,data=json.dumps(values).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=5) as response:
            return json.load(response)['data']

    def game(command,**values):
        return post('/local/game/'+command,dict(values,uid=auth['uid'],token=auth['token'],p_key=auth['p_key'],role_id=role))

    def start():
        log = (folder/'server-test.log').open('ab')
        process = subprocess.Popen([str(executable),'--port',str(game_port),'--http-port',str(http_port)],
                                   cwd=folder,env=environment,stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=flags)
        log.close()
        try:
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError('EXE exited; inspect server-test.log')
                try:
                    with urllib.request.urlopen('http://127.0.0.1:'+str(http_port)+'/health',timeout=.2) as reply:
                        if json.load(reply)['status']=='prototype':
                            return process
                except (OSError,ValueError):
                    time.sleep(.1)
            raise TimeoutError('EXE did not start')
        except Exception:
            stop(process)
            raise

    def stop(process):
        # PyInstaller onefile has a bootloader child; stop this test tree only.
        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
        process.wait(timeout=10)

    process = start()
    try:
        auth = post('/local/login',dict(uid='windows-preview'))
        with socket.create_connection(('127.0.0.1',game_port),timeout=5) as sock:
            sock.sendall(b'\x01\x02')
            buffer = bytearray()
            sequence = 100
            def call(key,message):
                nonlocal sequence
                sock.sendall(codec.encode_c2s(key,message.SerializeToString(),sequence))
                sequence += 1
                while True:
                    response = codec.pop_s2c(buffer)
                    if response:
                        if response[0]==key:
                            return protocol.decode('s2c',*response)
                    else:
                        packet = sock.recv(65536)
                        if not packet:
                            raise EOFError('Server disconnected')
                        buffer.extend(packet)
            login = initialize(protocol.make('c2s','1_1'))
            for field in ('uid','uname','p_key','token','time'):
                setattr(login,field,auth[field])
            roles = call('1_1',login).role_list
            role = roles[0].id
            call('1_3',protocol.make('c2s','1_3',{'id':str(role)}))
            roster = call('11_1',protocol.make('c2s','11_1'))
            assert len(roster.children_list)==75
        state = game('start',stage=10001,request_id='portable-exe-test-00001')
        identity = state['battle']['id']
        for i,card in enumerate(state['battle']['roster'][:3]):
            game('deploy',battle_id=identity,card_id=card['id'],x=5,y=1+i*2)
        for _ in range(100):
            state = game('state')
            if state['battle']['status']!='active':
                break
            time.sleep(.2)
        assert state['battle']['status']=='victory'
        first = game('claim',battle_id=identity)
        assert game('claim',battle_id=identity)['progress']==first['progress']
        with urllib.request.urlopen('http://127.0.0.1:'+str(http_port)+'/cdnconfig_test/res/config.txt',timeout=5) as response:
            assert response.status==200
    finally:
        stop(process)
    process = start()
    try:
        restored = game('state')
        assert restored['progress']==first['progress'] and restored['battle']['status']=='claimed'
    finally:
        stop(process)
    report = dict(success=True,exe_only_copy=True,python_paths_removed=True,roles=len(roles),characters=75,
                  battle_victory=True,reward_once=True,process_restart_preserved=True,cdn_fixture=True)
    (folder/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
