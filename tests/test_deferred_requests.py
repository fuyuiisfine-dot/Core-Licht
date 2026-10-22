import ast
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest

from game_server.protocol import Protocol
from game_server.snpacket import SNPacket
from tools.test_server_exe import initialize

ROOT=Path(__file__).resolve().parents[1]


class DeferredRequestsTests(unittest.TestCase):
    def test_phone_optional_query_does_not_close_connection_when_enabled(self):
        protocol=Protocol(ROOT/'analysis')
        codec=SNPacket(ROOT/'analysis/packet_xor_table.bin')
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name)
            log=folder/'protocol.jsonl'
            process=subprocess.Popen([sys.executable,'-u','-m','game_server','--port','0',
                '--database',str(folder/'test.sqlite3'),'--defer-unimplemented','--protocol-log',str(log),'--issue-uid','deferred-test'],
                cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                credentials=json.loads(process.stdout.readline())['local_credentials']
                address=ast.literal_eval(json.loads(process.stdout.readline())['listening'])
                with socket.create_connection(address,timeout=3) as connection:
                    login=initialize(protocol.make('c2s','1_1'))
                    for key in ('uid','uname','p_key','token','time'):setattr(login,key,credentials[key])
                    authentication=codec.encode_c2s('1_1',login.SerializeToString(),99)
                    optional=codec.encode_c2s('52_3',protocol.encode('c2s','52_3',{}),100)
                    heartbeat=codec.encode_c2s('1_0',protocol.encode('c2s','1_0',dict(index=42,client_time=0,server_time=0)),101)
                    connection.sendall(b'\x01\x02'+authentication+optional+heartbeat)
                    buffer=bytearray();response=None
                    observed=[]
                    while not response or response[0]!='1_0':
                        response=codec.pop_s2c(buffer)
                        if response:observed.append(response[0])
                        else:
                            part=connection.recv(4096)
                            self.assertTrue(part)
                            buffer.extend(part)
                    self.assertEqual(observed,['1_1','1_0'])
                    self.assertEqual(response[0],'1_0')  # No fabricated optional reply.
                    self.assertEqual(protocol.decode('s2c',*response).index,42)
                events=[json.loads(line) for line in log.read_text().splitlines()]
                self.assertTrue(any(event.get('pending_handler')=='52_3' for event in events))
            finally:
                process.terminate();process.communicate(timeout=5)


if __name__=='__main__':unittest.main()
