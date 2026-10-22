import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing

from tools.server_exe_entry import initialize

ROOT = Path(__file__).resolve().parents[1]


class ServerExeEntryTests(unittest.TestCase):
    def test_empty_install_seeds_once_and_preserves_progress_without_seed_file(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            resources = directory/'resources'
            for relative in ('message_ids.json','protocol.desc','active_protocol_files.json','player_attributes.json',
                             'config/lvl.json','config/config.json','config/open_func.json'):
                target = resources/'analysis'/relative
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(ROOT/'analysis'/relative,target)
            seed = resources/'default-profile.json'
            seed.write_text(json.dumps({'account_level':100,'cards':[]}),encoding='utf-8')
            database = directory/'external-save/state.sqlite3'
            initialize(database,resources)
            with closing(sqlite3.connect(database)) as db:
                self.assertEqual(db.execute('SELECT uid,level FROM roles').fetchall(),[('windows-preview',100)])
                self.assertEqual(db.execute('SELECT count(*) FROM accounts').fetchone()[0],0)
                db.execute('UPDATE roles SET name=?',('Keep my progress',))
                db.execute('INSERT INTO role_snapshots VALUES (?,?,?)',(1,'native_rehearsal','{"points":123}'))
                db.commit()
            seed.unlink()
            initialize(database,resources)
            with closing(sqlite3.connect(database)) as db:
                self.assertEqual(db.execute('SELECT name FROM roles').fetchall(),[('Keep my progress',)])
                self.assertEqual(json.loads(db.execute("SELECT value FROM role_snapshots WHERE domain='native_rehearsal'").fetchone()[0])['points'],123)


if __name__=='__main__':
    unittest.main()
