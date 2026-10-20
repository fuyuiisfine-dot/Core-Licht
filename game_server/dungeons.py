"""Original-client dungeon catalogue, earned progress, and access grants.

Access grants are kept separate from earned clear records. The original client
uses the completed task count, as well as stars, to open later chapters.
"""
import json


def catalogue(protocol):
    rows = json.loads((protocol.directory / 'config/dungeon.json').read_text(encoding='utf-8'))['data']
    return {int(key): row for key, row in rows.items() if int(row['chapter']) != 99}


def create_schema(db):
    db.execute('''CREATE TABLE IF NOT EXISTS dungeon_records (
        role_id INTEGER NOT NULL, dup_id INTEGER NOT NULL, star INTEGER NOT NULL,
        challenge_times INTEGER NOT NULL, first_pass_time INTEGER NOT NULL,
        PRIMARY KEY(role_id,dup_id))''')
    db.execute('''CREATE TABLE IF NOT EXISTS dungeon_access (
        role_id INTEGER NOT NULL, dup_id INTEGER NOT NULL, granted_time INTEGER NOT NULL,
        PRIMARY KEY(role_id,dup_id))''')


def grant_access(db, role_id, stage_ids, granted_time):
    if not db.execute('SELECT 1 FROM roles WHERE id=?', (role_id,)).fetchone():
        raise ValueError('role does not exist')
    with db:
        db.executemany('''INSERT OR IGNORE INTO dungeon_access VALUES (?,?,?)''',
                       ((role_id, stage_id, granted_time) for stage_id in stage_ids))


def progress(db, role_id):
    rows = db.execute('''SELECT dup_id,star,challenge_times FROM dungeon_records
                         WHERE role_id=? UNION ALL
                         SELECT a.dup_id,1,0 FROM dungeon_access a
                         WHERE a.role_id=? AND NOT EXISTS (
                             SELECT 1 FROM dungeon_records r
                             WHERE r.role_id=a.role_id AND r.dup_id=a.dup_id)
                         ORDER BY dup_id''', (role_id, role_id))
    return {'info': [dict(dup_id=row['dup_id'], star=row['star'], is_agent=0,
                          task=[{'k': 1, 'v': 1}] if row['star'] else [],
                          challenge_times=row['challenge_times'], sweep_lineup=[])
                     for row in rows]}
