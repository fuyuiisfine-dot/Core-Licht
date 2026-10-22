import concurrent.futures
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
import urllib.request
import urllib.error

from game_server.core import GameCore
from game_server.native_game import handle
from game_server.protocol import Protocol
from game_server.bootstrap import make_server

ROOT = Path(__file__).resolve().parents[1]


class NativeGameTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'game.sqlite3'
        self.now = 1800000000
        self.protocol = Protocol(ROOT/'analysis')
        self.core = GameCore(self.protocol, self.path, clock=lambda: self.now)
        self.credentials = self.core.issue_local_credentials('rehearsal-test')
        with self.core.db:
            self.role = self.core.db.execute('INSERT INTO roles(uid,name,sex,level,last_login_time) VALUES (?,?,?,?,?)',
                                             ('rehearsal-test', 'Rehearsal', 0, 100, self.now)).lastrowid
            self.other = self.core.db.execute('INSERT INTO roles(uid,name,sex,level,last_login_time) VALUES (?,?,?,?,?)',
                                              ('other', 'Other', 0, 100, self.now)).lastrowid
            cards = [dict(id=str(i), sys_id=str(i), use_skin=str(i), attr=[dict(k=11, v=8000), dict(k=12, v=900), dict(k=14, v=500)]) for i in (1001, 1002)]
            self.core.db.execute('INSERT INTO role_snapshots VALUES (?,?,?)', (self.role, 'sandbox_gm', json.dumps(dict(cards=cards))))
        self.base = dict(self.credentials, role_id=self.role)

    def tearDown(self):
        self.core.close()
        self.temp.cleanup()

    def call(self, command, **values):
        return handle(self.core, command, dict(self.base, **values))

    def start(self, key='request-0000000001', stage=10001):
        return self.call('start', stage=stage, request_id=key)

    def win(self):
        start = self.start()
        battle = start['battle']['id']
        self.call('deploy', battle_id=battle, card_id='1001', x=5, y=3)
        self.now += 14
        state = self.call('state')
        self.assertEqual(state['battle']['status'], 'victory')
        return battle

    def test_charge_once_and_reject_parallel_run(self):
        before = self.call('state')['vitality']['vitality']
        first = self.start()
        again = self.start()
        self.assertEqual(first['battle']['id'], again['battle']['id'])
        self.assertEqual(again['vitality']['vitality'], before-6)
        with self.assertRaises(ValueError):
            self.start('request-0000000002')
        self.assertEqual(self.call('state')['vitality']['vitality'], before-6)

    def test_three_stage_campaign_unlocks_and_saves_each_result(self):
        for index, stage in enumerate((10001,10002,10003), 1):
            battle = self.start('campaign-request-'+str(index), stage)['battle']['id']
            self.call('deploy', battle_id=battle, card_id='1001', x=5, y=3)
            self.now += 25
            self.assertEqual(self.call('state')['battle']['status'], 'victory')
            result = self.call('claim', battle_id=battle)
            self.assertIn(str(stage), result['progress']['clears'])
        self.assertEqual(result['progress']['points'], 600)
        self.assertEqual(result['progress']['victories'], 3)

    def test_victory_claim_is_once_and_unlocks_next_rehearsal(self):
        battle = self.win()
        self.assertEqual(self.call('state')['progress']['points'], 0)
        one = self.call('claim', battle_id=battle)
        two = self.call('claim', battle_id=battle)
        self.assertEqual(one['progress'], two['progress'])
        self.assertEqual(two['progress']['points'], 100)
        self.assertEqual(two['progress']['victories'], 1)
        self.assertEqual(two['progress']['clears']['10001'], 3)
        self.assertEqual(self.start('request-0000000002', 10002)['battle']['stage'], 10002)
        self.assertFalse(self.core.db.execute("SELECT 1 FROM role_snapshots WHERE domain='dungeons'").fetchone())

    def test_defeat_and_abandon_cannot_grant_points(self):
        battle = self.start()['battle']['id']
        with self.assertRaises(ValueError):
            self.call('claim', battle_id=battle, result='victory')
        self.now += 20
        self.assertEqual(self.call('state')['battle']['status'], 'defeat')
        self.assertEqual(self.call('claim', battle_id=battle)['progress']['points'], 0)
        battle = self.start('request-0000000002')['battle']['id']
        self.assertEqual(self.call('abandon', battle_id=battle)['battle']['outcome'], 'abandoned')
        self.assertEqual(self.call('claim', battle_id=battle)['progress']['points'], 0)

    def test_deployment_rejects_unowned_duplicate_and_outside_cells(self):
        battle = self.start()['battle']['id']
        for values in (dict(card_id='not-owned', x=1, y=1), dict(card_id='1001', x=6, y=1), dict(card_id='1001', x=True, y=1)):
            with self.assertRaises(ValueError):
                self.call('deploy', battle_id=battle, **values)
        self.call('deploy', battle_id=battle, card_id='1001', x=5, y=3)
        for card in ('1001', '1002'):
            with self.assertRaises(ValueError):
                self.call('deploy', battle_id=battle, card_id=card, x=5, y=3)
        self.assertEqual(len(self.call('state')['battle']['units']), 1)

    def test_authorization_and_stage_gate(self):
        with self.assertRaises(PermissionError):
            self.call('state', token='wrong')
        with self.assertRaises(PermissionError):
            self.call('state', role_id=self.other)
        with self.assertRaises(ValueError):
            self.start(stage=10002)
        with self.assertRaises(ValueError):
            self.start(stage=999)
        battle = self.start()['battle']['id']
        foreign = self.core.issue_local_credentials('other')
        with self.assertRaises(PermissionError):
            handle(self.core, 'claim', dict(foreign, role_id=self.other, battle_id=battle))

    def test_low_stamina_and_empty_team_are_atomic(self):
        self.core.snapshot(self.role, 'vitality', dict(vitality=5, vit_max=140))
        with self.assertRaises(ValueError):
            self.start()
        self.assertEqual(self.call('state')['vitality']['vitality'], 5)
        self.assertEqual(self.core.db.execute('SELECT count(*) FROM native_battles').fetchone()[0], 0)
        with self.core.db:
            self.core.db.execute('DELETE FROM role_snapshots WHERE domain=?', ('vitality',))
        self.core.snapshot(self.role, 'sandbox_team:10001', dict(default_index=1, children_team=[dict(team_index=1, children_list=[])]))
        before = self.call('state')['vitality']['vitality']
        with self.assertRaises(ValueError):
            self.start()
        self.assertEqual(self.call('state')['vitality']['vitality'], before)

    def test_resume_and_concurrent_claim_survive_database_reopen(self):
        battle = self.win()
        self.core.close()
        self.core = GameCore(self.protocol, self.path, clock=lambda: self.now)
        self.assertEqual(self.call('state')['battle']['id'], battle)

        def claim():
            core = GameCore(self.protocol, self.path, clock=lambda: self.now)
            try:
                return handle(core, 'claim', dict(self.base, battle_id=battle))['progress']['points']
            finally:
                core.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(lambda _: claim(), range(2))), [100, 100])
        self.assertEqual(self.call('state')['progress']['victories'], 1)
        # An old start retry returns the same settled run without spending again.
        stamina = self.call('state')['vitality']['vitality']
        self.assertEqual(self.start()['battle']['id'], battle)
        self.assertEqual(self.call('state')['vitality']['vitality'], stamina)

    def test_http_extension_requires_explicit_enable_and_credentials(self):
        for enabled in (False, True):
            server = make_server(self.protocol, self.path, 0, 19090, allow_local_client_login=enabled)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = 'http://127.0.0.1:'+str(server.server_address[1])+'/local/game/state'
                def request(body):
                    return urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(body).encode(), headers={'Content-Type':'application/json'}))
                if enabled:
                    with request(self.base) as response:
                        self.assertFalse(json.load(response)['data']['original_combat'])
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        request(dict(self.base, token='wrong'))
                    self.assertEqual(error.exception.code, 403)
                else:
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        request(self.base)
                    self.assertEqual(error.exception.code, 404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_running_battle_keeps_character_snapshot_after_roster_changes(self):
        battle = self.start()['battle']['id']
        profile = self.core.sandbox(self.role)
        profile['cards'][0]['attr'] = [dict(k=11,v=1),dict(k=12,v=1),dict(k=14,v=0)]
        with self.core.db:
            self.core.db.execute('UPDATE role_snapshots SET value=? WHERE role_id=? AND domain=?', (json.dumps(profile),self.role,'sandbox_gm'))
        result = self.call('deploy', battle_id=battle, card_id='1001', x=5, y=3)
        unit = result['battle']['units'][0]
        self.assertEqual((unit['hp'], unit['attack'], unit['defense']), (8000,900,500))


if __name__ == '__main__':
    unittest.main()
