"""Grant one local phone role access to all non-test dungeons, without clears."""
import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
sys.path.insert(0, str(ROOT))
from game_server.dungeons import catalogue, create_schema, grant_access


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=WORKSPACE / 'client-work/device.sqlite3')
    parser.add_argument('--analysis', type=Path, default=WORKSPACE / 'analysis')
    parser.add_argument('--role-id', type=int, required=True)
    args = parser.parse_args()
    database = args.database.resolve()
    stage_ids = sorted(catalogue(SimpleNamespace(directory=args.analysis.resolve())))
    if not database.is_file():
        raise FileNotFoundError(database)
    backup_dir = database.parent / 'device-backups'
    backup_dir.mkdir(exist_ok=True)
    backup = backup_dir / f'{database.stem}-before-dungeon-access-{int(time.time())}.sqlite3'
    with sqlite3.connect(database) as db:
        role = db.execute('SELECT id,name FROM roles WHERE id=?', (args.role_id,)).fetchone()
        if not role:
            raise ValueError('role does not exist')
        with sqlite3.connect(backup) as copy:
            db.backup(copy)
        create_schema(db)
        grant_access(db, args.role_id, stage_ids, int(time.time()))
        count = db.execute('SELECT COUNT(*) FROM dungeon_access WHERE role_id=?',
                           (args.role_id,)).fetchone()[0]
        earned = db.execute('SELECT COUNT(*) FROM dungeon_records WHERE role_id=?',
                            (args.role_id,)).fetchone()[0]
    print(json.dumps(dict(role_id=role[0], role_name=role[1], available=count,
                          earned_clears=earned, backup=str(backup)), ensure_ascii=False))


if __name__ == '__main__':
    main()
