"""Publish explicit release assets using Git's existing GitHub credential helper.

Never print or persist credentials. Existing remote assets are not overwritten.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.error
import urllib.parse
import urllib.request


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository',required=True)
    p.add_argument('--checkout',type=Path,required=True)
    p.add_argument('--tag',required=True)
    p.add_argument('--title',required=True)
    p.add_argument('--notes-file',type=Path,required=True)
    p.add_argument('--asset',type=Path,action='append',required=True)
    p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    for asset in a.asset:
        if not asset.is_file():raise ValueError('Asset does not exist: '+str(asset))
    credentials=subprocess.run(['git','-C',str(a.checkout),'credential','fill'],input='protocol=https\nhost=github.com\n\n',
                               text=True,capture_output=True,check=True)
    values=dict(line.split('=',1) for line in credentials.stdout.splitlines() if '=' in line)
    token=values['password']
    headers={'Authorization':'Bearer '+token,'User-Agent':'Core-Licht-release','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'}
    def request(url,data=None,content_type='application/json'):
        request_headers=dict(headers)
        if data is not None:request_headers['Content-Type']=content_type
        with urllib.request.urlopen(urllib.request.Request(url,data=data,headers=request_headers),timeout=180) as response:
            return json.load(response)
    base='https://api.github.com/repos/'+a.repository
    commit=subprocess.check_output(['git','-C',str(a.checkout),'rev-parse','HEAD'],text=True).strip()
    try:release=request(base+'/releases/tags/'+urllib.parse.quote(a.tag,safe=''))
    except urllib.error.HTTPError as error:
        if error.code!=404:raise
        release=request(base+'/releases',json.dumps(dict(tag_name=a.tag,target_commitish=commit,name=a.title,
            body=a.notes_file.read_text(encoding='utf-8'),draft=False,prerelease=True)).encode())
    uploaded=[]
    for asset in a.asset:
        digest=hashlib.sha256(asset.read_bytes()).hexdigest()
        existing=next((item for item in release['assets'] if item['name']==asset.name),None)
        if existing:
            if existing.get('digest')!='sha256:'+digest:raise ValueError('Remote asset already exists with another digest: '+asset.name)
            result=existing
        else:
            url=release['upload_url'].split('{')[0]+'?'+urllib.parse.urlencode({'name':asset.name})
            print('Uploading '+asset.name+' ('+str(asset.stat().st_size)+' bytes)',flush=True)
            result=request(url,asset.read_bytes(),'application/octet-stream')
        if result['size']!=asset.stat().st_size:raise ValueError('Remote size mismatch: '+asset.name)
        if result.get('digest') and result['digest']!='sha256:'+digest:raise ValueError('Remote hash mismatch: '+asset.name)
        uploaded.append(dict(name=result['name'],url=result['browser_download_url'],size=result['size'],sha256=digest))
        print('Verified upload: '+asset.name,flush=True)
    report=dict(url=release['html_url'],tag=a.tag,commit=commit,assets=uploaded)
    a.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Release: '+report['url'],flush=True)


if __name__=='__main__':main()
