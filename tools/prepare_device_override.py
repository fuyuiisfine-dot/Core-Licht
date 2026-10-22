"""Prepare an additive URL override. Does not write to the phone."""
import hashlib
import json
from pathlib import Path

source=Path('analysis/device/SHASD_local.original.txt')
original=source.read_bytes()
config=json.loads(original)
release=config['gameReleaseVersion']
base='http://127.0.0.1:18080/'
config.update(baseUrl=base+'cdnconfig_{0}/',
    configFileUrl=base+'cdnconfig_{0}/android_tw/stable/release/config.txt',
    updatePackageUrl=base+'cdnconfig_{0}/android_tw/stable/release/{1}/updatePackage',
    updateUrl=base+'cdnconfig_{0}/android_tw/stable/release/{1}/res',
    useBackup=base)
assert config['gameReleaseVersion']==release
out=Path('client-work');out.mkdir(exist_ok=True)
target=out/'UrlList_Android.txt'
target.write_text(json.dumps(config,separators=(',',':')),encoding='utf-8')
fixtures=out/'cdn-fixtures';fixtures.mkdir(exist_ok=True)
# LoadConfig splits newline then space into exactly two tokens per setting.
(fixtures/'config.txt').write_bytes(b'default public\n')
# DriverVersion.txt is produced separately from verified backup data by
# prepare_cdn_fixtures.py. Do not replace it with an empty placeholder.
plan={'source_sha256':hashlib.sha256(original).hexdigest(),
      'release_unchanged':release,'override_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
      'phone_target':'/sdcard/Android/data/com.tw99.no23.an/files/res/UrlList_Android.txt',
      'target_previously_present':False,'state':'prepared; not yet applied',
      'restore':'Remove only the newly added UrlList_Android.txt; original SHASD_local.txt is untouched.'}
(out/'device_change.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
print(json.dumps(plan,indent=2))
