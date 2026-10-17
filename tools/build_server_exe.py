"""Build a private single-file server from an explicit resource allowlist."""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from game_server.sandbox_profile import build
from game_server.affection import maximize

FILES = ('message_ids.json','protocol.desc','active_protocol_files.json',
         'player_attributes.json','packet_xor_table.bin')
TABLES = ('lvl','config','open_func','dungeon')


def prepare(analysis, fixtures, resources):
    resources.mkdir(parents=True,exist_ok=True)
    manifest = []
    for name in list(FILES)+['config/'+table+'.json' for table in TABLES]:
        source = analysis/name
        target = resources/'analysis'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        manifest.append(dict(path='analysis/'+name,sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
    # Construct a fresh configuration-derived profile; no private account data.
    profile = maximize(build(analysis,0),analysis)
    (resources/'default-profile.json').write_text(json.dumps(profile,ensure_ascii=False),encoding='utf-8')
    if fixtures:
        routes = json.loads((fixtures/'routes.json').read_text(encoding='utf-8'))
        if not isinstance(routes,dict) or any(not isinstance(v,str) for v in routes.values()):
            raise ValueError('Invalid CDN route manifest')
        names = {'config.txt','DriverVersion.txt','routes.json',*routes.values()}
        fixture_files = [(fixtures/name).resolve() for name in sorted(names)]
        for source in fixture_files:
            if fixtures not in source.parents:
                raise ValueError('CDN route escapes fixture directory')
            if source.suffix.lower() not in ('.ab','.json','.txt','.jar'):
                raise ValueError('Unexpected CDN fixture type: '+source.name)
            target = resources/'cdn-fixtures'/source.relative_to(fixtures)
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
            manifest.append(dict(path=str(target.relative_to(resources)),sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
    else:
        (resources/'cdn-fixtures').mkdir(exist_ok=True)
    (resources/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--analysis',type=Path,required=True)
    p.add_argument('--fixtures',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--packaging-path',type=Path,help='Optional isolated PyInstaller installation')
    p.add_argument('--copy-database',type=Path,help='Create an external SQLite snapshot only if destination is absent')
    a = p.parse_args()
    work,output,analysis = a.work.resolve(),a.output.resolve(),a.analysis.resolve()
    if work == analysis or analysis in work.parents or work in analysis.parents:
        raise ValueError('Build directory must be separate from source analysis')
    if work.exists():
        # A new private work directory prevents stale data being bundled.
        if any(work.iterdir()):
            raise ValueError('Use a new empty --work directory for each build')
    resources = work/'resources'
    prepare(analysis,a.fixtures.resolve() if a.fixtures else None,resources)
    output.mkdir(parents=True,exist_ok=True)
    env = dict(os.environ)
    if a.packaging_path:
        env['PYTHONPATH'] = str(a.packaging_path.resolve())
    command = [sys.executable,'-m','PyInstaller','--onefile','--console','--noupx','--noconfirm',
               '--name','CoreLichtServer','--distpath',str(output),'--workpath',str(work/'build'),
               '--specpath',str(work),'--paths',str(ROOT),'--collect-submodules','game_server',
               '--add-data',str(resources)+os.pathsep+'server-resources',str(ROOT/'tools/server_exe_entry.py')]
    subprocess.run(command,env=env,cwd=ROOT,check=True)
    if a.copy_database:
        target = output/'server-data/server.sqlite3'
        if target.exists():
            print('Existing output save preserved:',target)
        else:
            if not a.copy_database.is_file():
                raise ValueError('Source database does not exist')
            target.parent.mkdir(parents=True,exist_ok=True)
            with closing(sqlite3.connect(a.copy_database.resolve().as_uri()+'?mode=ro',uri=True)) as source:
                with closing(sqlite3.connect(target)) as destination:
                    source.backup(destination)
            print('External save snapshot:',target)
    executable = output/'CoreLichtServer.exe'
    report = dict(file=executable.name,size=executable.stat().st_size,
                  sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),single_file=True,
                  private_accounts_embedded=False)
    (output/'build-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
