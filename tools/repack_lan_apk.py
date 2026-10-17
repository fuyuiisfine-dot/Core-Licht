"""Patch only the APK's embedded Unity URL text, then align/sign/verify it.

Original APK/OBBs are read-only. Signing key/password stay in a private directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import struct
import subprocess
import sys
import zipfile


def decode_blob(raw):
    def string(offset):
        length=0;shift=0
        while True:
            byte=raw[offset];offset+=1;length|=(byte&127)<<shift
            if not byte&128:break
            shift+=7
            if shift>28:raise ValueError('Invalid embedded string length')
        return raw[offset:offset+length],offset+length
    magic,offset=string(0);name,offset=string(offset)
    if magic!=b'LXT_SHA' or name!=b'UrlList_Android.txt':raise ValueError('Unexpected URL resource header')
    length=struct.unpack_from('<I',raw,offset)[0];offset+=4
    if len(raw)-offset!=length:raise ValueError('Unexpected URL resource payload length')
    return raw[:offset-4],json.loads(raw[offset:])


def patch(source,output,host,unity_path):
    sys.path.insert(0,str(unity_path))
    import UnityPy
    prefix='assets/bin/Data/sharedassets0.assets.split'
    with zipfile.ZipFile(source) as archive:
        parts=sorted([n for n in archive.namelist() if n.startswith(prefix)],key=lambda n:int(n[len(prefix):]))
        if not parts:raise ValueError('Missing split Unity assets')
        env=UnityPy.load(b''.join(archive.read(n) for n in parts))
        before={o.path_id:hashlib.sha256(o.get_raw_data()).hexdigest() for o in env.objects}
        matches=[o for o in env.objects if o.type.name=='TextAsset' and o.read().m_Name=='UrlList_Android']
        if len(matches)!=1:raise ValueError('Expected one embedded URL resource')
        obj=matches[0];text=obj.read()
        header,config=decode_blob(text.m_Script.encode('utf-8','surrogateescape'))
        base='http://'+host+':18080/'
        config.update(baseUrl=base+'cdnconfig_{0}/',configFileUrl=base+'cdnconfig_{0}/android_tw/stable/release/config.txt',
                      updatePackageUrl=base+'cdnconfig_{0}/android_tw/stable/release/{1}/updatePackage',
                      updateUrl=base+'cdnconfig_{0}/android_tw/stable/release/{1}/res',useBackup=base,
                      versionCustomContent="return {isRelease=false,server='tw_debug_888',isDisabledSdk=true}")
        encoded=json.dumps(config,separators=(',',':')).encode('utf-8')
        text.m_Script=(header+struct.pack('<I',len(encoded))+encoded).decode('utf-8','surrogateescape');text.save()
        raw=env.file.save()
        checked=UnityPy.load(raw)
        for item in checked.objects:
            if item.path_id!=obj.path_id and hashlib.sha256(item.get_raw_data()).hexdigest()!=before[item.path_id]:
                raise ValueError('Unrelated Unity object changed: '+str(item.path_id))
        updated=next(o for o in checked.objects if o.path_id==obj.path_id).read()
        assert decode_blob(updated.m_Script.encode('utf-8','surrogateescape'))[1]==config
        split_size=archive.getinfo(parts[0]).file_size
        replacements={prefix+str(i):raw[start:start+split_size] for i,start in enumerate(range(0,len(raw),split_size))}
        with zipfile.ZipFile(output,'w') as target:
            for info in archive.infolist():
                if info.filename.startswith(prefix) or info.filename.upper().startswith('META-INF/'):
                    continue
                target.writestr(info,archive.read(info.filename))
            for name,value in replacements.items():target.writestr(name,value,compress_type=zipfile.ZIP_DEFLATED)
    # All non-signature files outside the one serialized Unity file are unchanged.
    with zipfile.ZipFile(source) as original,zipfile.ZipFile(output) as patched:
        for name in original.namelist():
            if not name.startswith(prefix) and not name.upper().startswith('META-INF/'):
                assert hashlib.sha256(original.read(name)).digest()==hashlib.sha256(patched.read(name)).digest()
    return dict(host=host,release=config['gameReleaseVersion'],unity_objects=len(before),changed_object=obj.path_id,
                unchanged_objects=len(before)-1,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--host',required=True)
    p.add_argument('--unity-path',type=Path,required=True)
    p.add_argument('--java',type=Path,required=True)
    p.add_argument('--signer',type=Path,required=True)
    p.add_argument('--private-key-dir',type=Path,required=True)
    a=p.parse_args()
    from ipaddress import IPv4Address
    IPv4Address(a.host)
    source=a.source.resolve();output=a.output.resolve();work=a.work.resolve()
    if source==output or source.parent==work:raise ValueError('Use a separate output/work directory')
    if output.exists():raise ValueError('Output already exists; choose a new file')
    work.mkdir(parents=True,exist_ok=False);output.parent.mkdir(parents=True,exist_ok=True)
    unsigned=work/'unsigned.apk';aligned=work/'aligned.apk'
    report=patch(source,unsigned,a.host,a.unity_path.resolve())
    key_dir=a.private_key_dir.resolve();key_dir.mkdir(parents=True,exist_ok=True)
    password_file=key_dir/'signing-secret.json';key_file=key_dir/'core-licht-local.p12'
    environment=dict(os.environ)
    if not password_file.exists():password_file.write_text(json.dumps(dict(password=secrets.token_urlsafe(32))),encoding='utf-8')
    environment['LICHT_APK_KEY_PASSWORD']=json.loads(password_file.read_text())['password']
    java=a.java.resolve();jar=a.signer.resolve()
    if not key_file.exists():
        subprocess.run([str(java.with_name('keytool.exe')),'-genkeypair','-keystore',str(key_file),'-storetype','PKCS12',
                        '-storepass:env','LICHT_APK_KEY_PASSWORD','-keypass:env','LICHT_APK_KEY_PASSWORD',
                        '-alias','core-licht-local','-dname','CN=Core Licht Local','-keyalg','RSA','-keysize','3072','-validity','10000'],env=environment,check=True)
    with zipfile.ZipFile(jar) as tool:
        zipalign=work/'zipalign.exe';zipalign.write_bytes(tool.read('win-zipalign_33_0_2.exe'))
    subprocess.run([str(zipalign),'-p','-f','4',str(unsigned),str(aligned)],check=True)
    cli=[str(java),'-cp',str(jar),'com.android.apksigner.ApkSignerTool']
    subprocess.run(cli+['sign','--ks',str(key_file),'--ks-key-alias','core-licht-local',
                       '--ks-pass','env:LICHT_APK_KEY_PASSWORD','--key-pass','env:LICHT_APK_KEY_PASSWORD',
                       '--v1-signing-enabled','true','--v2-signing-enabled','true','--v3-signing-enabled','true',
                       '--v4-signing-enabled','false','--out',str(output),str(aligned)],env=environment,check=True)
    verified=subprocess.run(cli+['verify','--verbose','--print-certs',str(output)],capture_output=True,text=True,check=True)
    subprocess.run([str(zipalign),'-c','-p','4',str(output)],check=True)
    (work/'signature-verification.txt').write_text(verified.stdout,encoding='utf-8')
    report.update(file=output.name,bytes=output.stat().st_size,sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                  signature_verified=True,alignment_verified=True,original_signature_preserved=False,installed_on_phone=False)
    output.with_suffix('.build.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
