"""Inspect a backup and copy selected APK members for static analysis."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backup',type=Path,required=True)
    p.add_argument('--output',type=Path,default=Path('analysis'))
    args=p.parse_args()
    backup=args.backup.resolve();out=args.output.resolve()
    if out==backup or backup in out.parents:raise ValueError('output must be outside backup')
    apks=list(backup.glob('*.apk'))
    if len(apks)!=1:raise ValueError('expected exactly one APK')
    native=out/'native';native.mkdir(parents=True,exist_ok=True)
    apk=apks[0]
    report={'apk':str(apk),'apk_sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),
            'members':{},'obb':[]}
    with zipfile.ZipFile(apk) as z:
        for source,target in [('lib/arm64-v8a/libil2cpp.so','libil2cpp.so'),
            ('assets/bin/Data/Managed/Metadata/global-metadata.dat','global-metadata.dat')]:
            data=z.read(source);(native/target).write_bytes(data)
            report['members'][source]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        report['native_abis']=sorted({n.split('/')[1] for n in z.namelist() if n.startswith('lib/')})
    for obb in sorted(backup.rglob('*.obb')):
        with zipfile.ZipFile(obb) as z:
            bundles={n:{'bytes':z.getinfo(n).file_size,'crc32':hex(z.getinfo(n).CRC)}
                for n in z.namelist() if n.endswith(('Zero/Lua/lua.ab','Zero/PB/pb.ab'))}
            report['obb'].append({'path':str(obb),'bytes':obb.stat().st_size,
                                  'entries':len(z.namelist()),'protocol_bundles':bundles})
    (out/'backup_inventory.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))


if __name__=='__main__':main()
