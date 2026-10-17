"""Compare a test installation to the explicit packaging inputs, before launching it."""
import argparse
import hashlib
import json
from pathlib import Path


def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--installed',type=Path,required=True)
    p.add_argument('--client',type=Path,required=True)
    p.add_argument('--server',type=Path,required=True)
    p.add_argument('--release',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    expected={'CoreLicht.exe':a.client/'CoreLicht.exe',
              'CoreLichtLauncher.exe':a.release/'CoreLichtLauncher.exe',
              'Windows-README.txt':a.release/'Windows-README.txt',
              'server/CoreLichtServer.exe':a.server,
              'data/catalog.json':a.client/'data/catalog.json'}
    for folder in ['protocol','portraits','ui','voices']:
        for path in (a.client/'data'/folder).rglob('*'):
            if path.is_file():expected[path.relative_to(a.client).as_posix()]=path
    actual={path.relative_to(a.installed).as_posix() for path in a.installed.rglob('*') if path.is_file()}
    if actual!=set(expected)|{'Uninstall.exe'}:
        raise ValueError('Installation file list mismatch: '+str(actual.symmetric_difference(set(expected)|{'Uninstall.exe'})))
    for relative,original in expected.items():
        if sha256(a.installed/relative)!=sha256(original):raise ValueError('Hash mismatch: '+relative)
    report=dict(success=True,verified_files=len(expected),
                voices=len(list((a.installed/'data/voices').glob('*.wav'))),
                private_database_included=False,all_file_hashes_match=True)
    a.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':main()
