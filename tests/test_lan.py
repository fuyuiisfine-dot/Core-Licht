from contextlib import closing
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request

from game_server.bootstrap import make_server
from game_server.core import GameCore
from game_server.network import NetworkPolicy
from game_server.protocol import Protocol

ROOT=Path(__file__).resolve().parents[1]


class LanTests(unittest.TestCase):
    def test_only_selected_subnet_and_loopback_are_accepted(self):
        policy=NetworkPolicy(['192.168.0.0/24'])
        for address in ('127.0.0.1','192.168.0.1','192.168.0.210'):
            self.assertTrue(policy.allows(address))
        for address in ('10.56.20.235','26.78.166.166','192.168.1.3','8.8.8.8','::1','invalid'):
            self.assertFalse(policy.allows(address))
        for networks in (['0.0.0.0/0'],['::/0'],'192.168.0.0/24',[123]):
            with self.assertRaises(ValueError):NetworkPolicy(networks)

    def test_advertised_host_comes_from_socket_not_untrusted_http_headers(self):
        protocol=Protocol(ROOT/'analysis')
        with tempfile.TemporaryDirectory() as directory:
            database=Path(directory)/'lan.sqlite3'
            core=GameCore(protocol,database)
            try:credentials=core.issue_local_credentials('lan-test')
            finally:core.close()
            server=make_server(protocol,database,0,19090,allow_local_client_login=True,listen_host='0.0.0.0',allowed_networks=['192.168.0.0/24'])
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                origin='http://127.0.0.1:'+str(server.server_address[1])
                request=urllib.request.Request(origin+'/client/select_region',data=json.dumps(credentials).encode(),
                    headers={'Content-Type':'application/json','Host':'attacker.example','X-Forwarded-For':'8.8.8.8'})
                with urllib.request.urlopen(request,timeout=3) as response:
                    self.assertEqual(json.load(response)['data']['serv_list'][0][0],'127.0.0.1')
                self.assertFalse(server.verify_request(None,('10.56.20.235',1234)))
                self.assertTrue(server.verify_request(None,('192.168.0.210',1234)))
            finally:
                server.shutdown();server.server_close();thread.join(timeout=3)


if __name__=='__main__':unittest.main()
