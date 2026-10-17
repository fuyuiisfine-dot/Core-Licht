"""Portable frozen-server entry point. Bundled resources are always read-only."""
import argparse
import json
from pathlib import Path
import socket
import sys
import time
from types import SimpleNamespace

from game_server.__main__ import serve
from game_server.core import GameCore
from game_server.protocol import Protocol
from game_server.network import NetworkPolicy


def initialize(database, resources):
    """Seed an empty installation only; never replace existing roles or progress."""
    database.parent.mkdir(parents=True, exist_ok=True)
    protocol = Protocol(resources/'analysis')
    core = GameCore(protocol, database)
    try:
        with core.db:
            # Recheck under a write lock so two launches cannot seed twice.
            core.db.execute('BEGIN IMMEDIATE')
            if core.db.execute('SELECT 1 FROM roles LIMIT 1').fetchone():
                return
            profile = json.loads((resources/'default-profile.json').read_text(encoding='utf-8'))
            role = core.db.execute('INSERT INTO roles(uid,name,sex,level,last_login_time) VALUES (?,?,?,?,?)',
                                  ('windows-preview','Windows Preview',1,profile['account_level'],int(time.time()))).lastrowid
            levels = core.levels[profile['account_level']]
            vitality = dict(vitality=levels['vit_max'],vit_max=levels['vit_max'],exchange_num=0,
                            daily_reward=0,new_role_reward=0,next_time=0)
            for domain, value in [('sandbox_gm',profile),('tutorial_stage',{'stage':29}),('vitality',vitality)]:
                core.db.execute('INSERT INTO role_snapshots VALUES (?,?,?)',(role,domain,json.dumps(value)))
    finally:
        core.close()


def main():
    frozen = getattr(sys,'frozen',False)
    base = Path(sys.executable).resolve().parent if frozen else Path(__file__).resolve().parents[1]
    config_path=base/'server-config.json'
    config=json.loads(config_path.read_text(encoding='utf-8-sig')) if config_path.is_file() else {}
    if not isinstance(config,dict):raise ValueError('server-config.json must contain an object')
    parser = argparse.ArgumentParser(description='Core Licht standalone local server')
    parser.add_argument('--database',type=Path,default=base/'server-data'/'server.sqlite3')
    parser.add_argument('--port',type=int,default=19090)
    parser.add_argument('--http-port',type=int,default=18080)
    parser.add_argument('--listen-host',default=config.get('listen_host','127.0.0.1'))
    parser.add_argument('--allow-network',dest='allowed_networks',action='append',default=config.get('allowed_networks',[]))
    parser.add_argument('--resources',type=Path,default=Path(sys._MEIPASS)/'server-resources' if frozen else base/'client-work/server-build/resources')
    parser.add_argument('--check',action='store_true',help='Validate bundled data and database, then exit')
    args = parser.parse_args()
    NetworkPolicy(args.allowed_networks)
    resources = args.resources.resolve()
    database = args.database.resolve()
    if resources == database or resources in database.parents:
        raise ValueError('Database must be outside bundled resources')
    if not args.check:
        for port in (args.port,args.http_port):
            if not 1 <= port <= 65535:
                raise ValueError('Ports must be between 1 and 65535')
            with socket.socket() as probe:
                probe.bind((args.listen_host,port))
        if args.port == args.http_port:
            raise ValueError('TCP and HTTP must use different ports')
    initialize(database,resources)
    if args.check:
        core = GameCore(Protocol(resources/'analysis'),database)
        try:
            count = core.db.execute('SELECT count(*) FROM roles').fetchone()[0]
            print(json.dumps(dict(success=True,frozen=frozen,roles=count,database=str(database))))
        finally:
            core.close()
        return
    print('Core Licht Server | '+args.listen_host+' | HTTP '+str(args.http_port)+' | TCP '+str(args.port),flush=True)
    print('Save file: '+str(database),flush=True)
    print('Keep this window open. Press Ctrl+C to stop.',flush=True)
    serve(SimpleNamespace(profile=None,analysis=str(resources/'analysis'),database=str(database),port=args.port,
                          http_port=args.http_port,cdn_fixtures=str(resources/'cdn-fixtures'),
                          request_log=str(database.parent/'http_requests.jsonl'),protocol_log=str(database.parent/'protocol_events.jsonl'),
                          capture_first_packet=None,reload_core=False,defer_unimplemented=True,issue_uid=None,
                          allow_local_client_login=True,listen_host=args.listen_host,allowed_networks=args.allowed_networks))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Server stopped.')
    except Exception as error:
        print('Server could not start: '+str(error),file=sys.stderr,flush=True)
        if getattr(sys,'frozen',False) and sys.stdin and sys.stdin.isatty():
            input('Press Enter to close...')
        sys.exit(1)
