"""Extract original UI art into private client output; never alter the OBBs."""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.dependencies/python'))
import UnityPy


def prepare(backup, output):
    backup, output = Path(backup).resolve(), Path(output).resolve()
    if output == backup or backup in output.parents:
        raise ValueError('Output must be outside original backup')
    output.mkdir(parents=True, exist_ok=True)
    records = []
    with zipfile.ZipFile(backup / 'patch.138.com.tw99.no23.an.obb') as archive:
        for bundle in ['Texture/main_c_bg.ab', 'Atlas/Module_MainFrame.ab',
                       'Atlas/Global_Common.ab', 'Atlas/Global_Main.ab',
                       'Atlas/Module_Card.ab', 'Atlas/Module_CardTab.ab',
                       'Atlas/Icon_CardIcon.ab']:
            member = 'assets/ZeroThemePark/tw/Zero/UI/' + bundle
            raw = archive.read(member)
            env = UnityPy.load(raw)
            for obj in env.objects:
                if obj.type.name != 'Sprite':
                    continue
                sprite = obj.read()
                name = sprite.m_Name.replace('/', '_').replace('\\', '_')
                sprite.image.save(output / (name + '.png'))
                records.append(dict(member=member, sprite=sprite.m_Name,
                                    sha256=hashlib.sha256(raw).hexdigest(), file=name+'.png'))
        # Use the game's own card crops rather than cropping a full-screen portrait.
        catalog = json.loads((output.parent / 'catalog.json').read_text(encoding='utf-8-sig'))
        photos = {Path(skin['image']).stem for char in catalog['characters'].values()
                  for skin in char['skins'].values() if skin['image'].startswith('portraits/')}
        for photo in sorted(photos):
            member = 'assets/ZeroThemePark/tw/Zero/UI/Texture/CardPicIcon/card_pic_' + photo + '.ab'
            if member not in archive.namelist():
                continue
            raw = archive.read(member)
            for obj in UnityPy.load(raw).objects:
                if obj.type.name == 'Sprite':
                    sprite = obj.read()
                    name = 'card_pic_' + photo + '.png'
                    sprite.image.save(output / name)
                    records.append(dict(member=member, sprite=sprite.m_Name,
                                        sha256=hashlib.sha256(raw).hexdigest(), file=name))
                    break
    (output / 'provenance.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    config = ROOT / 'analysis' / 'config'
    jobs = {str(row['id']): row for row in json.loads((config/'children_fightjob.json').read_text(encoding='utf-8'))['data']}
    children = json.loads((config/'children.json').read_text(encoding='utf-8'))['data']
    metadata = {sid: dict(job_icon='card_c_occIcon_'+jobs[str(row['job'])]['icon']+'_128',
                         cost=row['cost'], attack_speed=row['attack_speed'], speed=row['speed'],
                         target=row['target'], move_style=row['move_style'], hurt=row['hurt'], attack_rang=row['attack_rang'])
                for sid, row in children.items() if sid in catalog['characters']}
    (output / 'characters.json').write_text(json.dumps(metadata, ensure_ascii=False), encoding='utf-8')
    print('Extracted', len(records), 'original UI sprites')


if __name__ == '__main__':
    prepare(sys.argv[1], sys.argv[2])
