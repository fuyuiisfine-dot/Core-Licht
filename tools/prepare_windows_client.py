"""Build private Windows client resources from read-only exported tables and OBBs."""
import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.dependencies/python'))
import UnityPy


def prepare(analysis,backup,output):
    backup=backup.resolve();output=output.resolve()
    if output==backup or backup in output.parents:raise ValueError('output must be outside the original backup')
    def load(name):return json.loads((analysis/'config'/(name+'.json')).read_text(encoding='utf-8'))['data']
    data=output/'data';data.mkdir(parents=True,exist_ok=True)
    protocol=data/'protocol';protocol.mkdir(exist_ok=True)
    for name in ['message_ids.json','schemas.json','packet_xor_table.bin']:
        shutil.copy2(analysis/name,protocol/name)
    children=load('children');skins=load('children_skin');docs=load('children_doc')
    text=load('children_doc_char');voices=load('children_doc_voice')
    archives=[zipfile.ZipFile(p)for p in sorted(backup.glob('*.obb'),reverse=True)]
    catalog={};images={};failures=[];provenance=[]
    (data/'portraits').mkdir(exist_ok=True)
    try:
        for child in children.values():
            if child['is_hero']or child['is_informal']:continue
            sid=child['id'];meta=docs[str(sid)];styles={}
            for skin_id in child['skin_list']:
                skin=skins.get(str(skin_id))
                if not skin:continue
                picture=skin['photo'];target='portraits/'+str(picture)+'.png'
                if picture not in images:
                    path='assets/ZeroThemePark/tw/Zero/UI/Texture/CardTexture/card_'+str(picture)+'.ab'
                    archive=next((a for a in archives if path in a.namelist()),None)
                    if archive is None:
                        # Main OBB may use the unprefixed namespace.
                        path=path.replace('ZeroThemePark/tw/','')
                        archive=next((a for a in archives if path in a.namelist()),None)
                    if archive is None:failures.append({'skin':skin_id,'image':picture,'reason':'bundle absent'})
                    else:
                        try:
                            raw=archive.read(path);env=UnityPy.load(raw)
                            sprites=[o for o in env.objects if o.type.name=='Sprite']
                            textures=[o for o in env.objects if o.type.name=='Texture2D']
                            if not sprites and not textures:raise ValueError('no portrait object')
                            obj=(sprites or textures)[0].read();image=obj.image
                            image.save(data/target)
                            provenance.append({'member':path,'source':Path(archive.filename).name,
                                'sha256':hashlib.sha256(raw).hexdigest(),'output':target})
                        except Exception as ex:failures.append({'skin':skin_id,'image':picture,'reason':str(ex)})
                    images[picture]=True
                styles[str(skin_id)]={'name':skin['name']+' · '+skin['sub_title'],
                                     'image':target if(data/target).is_file()else 'missing-portrait.png'}
            catalog[str(sid)]={'name':child['name'],'skins':styles,
                'documents':[{'id':i,'title':text[str(i)]['title'],'content':text[str(i)]['content']}for i in meta['per']],
                'voices':[{'id':i,'title':voices[str(i)]['title'],'content':voices[str(i)]['desc']}for i in meta['voice']]}
    finally:
        for a in archives:a.close()
    (data/'catalog.json').write_text(json.dumps({'characters':catalog},ensure_ascii=False),encoding='utf-8')
    (data/'resource-provenance.json').write_text(json.dumps({'images':provenance,'failures':failures},ensure_ascii=False,indent=2),encoding='utf-8')
    return {'characters':len(catalog),'portraits':len(provenance),'missing_portraits':len(failures),'directory':str(output.resolve())}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--analysis',type=Path,default=Path('analysis'))
    p.add_argument('--backup',type=Path,default=Path(r'D:\tool\platform-tools-latest-windows\platform-tools\game_backup\obb'))
    p.add_argument('--output',type=Path,default=Path('client-work/windows-client'))
    a=p.parse_args();print(json.dumps(prepare(a.analysis,a.backup,a.output),indent=2))
