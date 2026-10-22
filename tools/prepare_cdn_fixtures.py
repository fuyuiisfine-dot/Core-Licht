"""Build exact boot resource responses from the phone manifest and backup OBBs."""
import hashlib
import json
from pathlib import Path
import zipfile

backup=Path(r'D:\tool\platform-tools-latest-windows\platform-tools\game_backup\obb')
fixture=Path('client-work/cdn-fixtures');fixture.mkdir(parents=True,exist_ok=True)
manifest=Path('analysis/device/DriverVersion_local.generated.txt').read_bytes()
(fixture/'DriverVersion.txt').write_bytes(manifest)
(fixture/'config.txt').write_bytes(b'default public\n')
archives=[zipfile.ZipFile(p) for p in sorted(backup.glob('*.obb'),reverse=True)]
routes={};entries=[]
try:
    for line in manifest.decode('utf-8-sig').splitlines():
        if not line.strip():continue
        name,digest,size,revision=line.split(',')
        source='assets/'+name
        found=None
        for archive in archives:
            if source in archive.namelist():found=archive.read(source);break
        if found is None:raise ValueError('missing backup resource: '+name)
        if len(found)!=int(size) or hashlib.md5(found).hexdigest()!=digest:
            raise ValueError('backup manifest mismatch: '+name)
        path=fixture/'resources'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(found)
        for version in [None,revision,digest]:
            route=Path(name)
            if version:route=route.with_name(route.stem+'_'+version+route.suffix)
            routes[route.as_posix()]='resources/'+name
        entries.append({'resource':name,'bytes':len(found),'md5':digest,'revision':revision})
finally:
    for archive in archives:archive.close()
(fixture/'routes.json').write_text(json.dumps(routes,indent=2),encoding='utf-8')
Path('analysis/device/cdn_fixture_provenance.json').write_text(json.dumps(entries,indent=2),encoding='utf-8')
print('Verified exact backup resources:',len(entries))
