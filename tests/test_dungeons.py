import unittest
from pathlib import Path

from game_server.core import GameCore, Session
from game_server.dungeons import catalogue, grant_access
from game_server.protocol import Protocol


ROOT = Path(__file__).resolve().parents[1]


class DungeonProgressTests(unittest.TestCase):
    def setUp(self):
        self.protocol = Protocol(ROOT / 'analysis')
        self.core = GameCore(self.protocol)
        self.session = Session(uid='test', role_id=123)

    def tearDown(self):
        self.core.close()

    def query(self):
        response_id, payload = self.core.handle(self.session, '17_1', b'')
        self.assertEqual(response_id, '17_1')
        return self.protocol.decode('s2c', response_id, payload)

    def test_catalogue_covers_non_test_chapters(self):
        if not (ROOT.parent / 'analysis/config/dungeon.json').exists():
            self.skipTest('private dungeon catalogue is unavailable')
        stages = catalogue(Protocol(ROOT.parent / 'analysis'))
        self.assertIn(10001, stages)
        self.assertEqual(stages[10001]['number'], '0-1')
        self.assertTrue(all(row['chapter'] != 99 for row in stages.values()))
        self.assertEqual(len(stages), 190)
        self.assertEqual(set(row['chapter'] for row in stages.values()),
                         {0, 1, 2, 3, 4, 5, 6, 7, 8, 106, 1001, 2001, 2002, 2003})

    def test_query_reports_only_earned_role_progress(self):
        self.assertEqual(len(self.query().info), 0)
        with self.core.db:
            self.core.db.execute('INSERT INTO dungeon_records VALUES (?,?,?,?,?)',
                                 (123, 10001, 3, 2, 123456789))
            self.core.db.execute('INSERT INTO dungeon_records VALUES (?,?,?,?,?)',
                                 (999, 10002, 2, 1, 123456790))
        rows = self.query().info
        self.assertEqual([(r.dup_id, r.star, r.challenge_times) for r in rows],
                         [(10001, 3, 2)])
        other_id, other_payload = self.core.handle(Session(uid='test', role_id=999), '17_1', b'')
        other = self.protocol.decode('s2c', other_id, other_payload)
        self.assertEqual([r.dup_id for r in other.info], [10002])

    def test_manual_access_does_not_create_clears_or_rewards(self):
        with self.core.db:
            self.core.db.execute('INSERT INTO roles VALUES (?,?,?,?,?,?)',
                                 (123, 'test', 'OpenOnly', 1, 1, 0))
        grant_access(self.core.db, 123, [10001, 20005], 100)
        grant_access(self.core.db, 123, [10001, 20005], 101)
        self.assertEqual([(r.dup_id, r.star, r.challenge_times) for r in self.query().info],
                         [(10001, 1, 0), (20005, 1, 0)])
        self.assertEqual([(t.k, t.v) for t in self.query().info[1].task], [(1, 1)])
        self.assertEqual(self.core.db.execute('SELECT COUNT(*) FROM dungeon_records').fetchone()[0], 0)
        with self.core.db:
            self.core.db.execute('INSERT INTO dungeon_records VALUES (?,?,?,?,?)',
                                 (123, 10001, 2, 1, 200))
        self.assertEqual([(r.dup_id, r.star) for r in self.query().info],
                         [(10001, 2), (20005, 1)])
        with self.assertRaises(ValueError):
            grant_access(self.core.db, 999, [10001], 100)

    def test_query_requires_selected_role(self):
        with self.assertRaises(PermissionError):
            self.core.handle(Session(uid='test'), '17_1', b'')


if __name__ == '__main__':
    unittest.main()
