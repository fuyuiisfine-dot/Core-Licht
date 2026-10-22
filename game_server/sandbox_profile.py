"""Explicit local GM profile, derived from the shipped tables, never publisher state."""
import json


def load(directory,name):
    return json.loads((directory/'config'/(name+'.json')).read_text(encoding='utf-8'))['data']


def build(directory,now):
    children=load(directory,'children');awake=load(directory,'children_awake')
    sync=load(directory,'children_sync');stats=load(directory,'children_lvl_attr')
    skill_levels=load(directory,'children_skill_lvl');skins=load(directory,'children_skin')
    favor_levels=load(directory,'children_favor_lvl')
    cards=[]
    for base in sorted(children.values(),key=lambda r:r['id']):
        if base['is_hero'] or base['is_informal']:continue
        sid=base['id']
        upgrades=[r for r in awake.values()if r['id']==sid]
        if not upgrades:raise ValueError(f'missing awakening table: {sid}')
        top=max(upgrades,key=lambda r:r['times']);level=top['max_lvl']
        stat=stats[f'{sid}|=|{level}']
        # Exact display attribute IDs recovered from CardDefine.CardShowAttr.
        attributes={11:stat['hp'],12:stat['atk'],14:stat['def'],15:stat['magic_def']}
        # Awakening rows contain additive bonuses for each attained stage.
        for upgrade in upgrades:
            for key,value in upgrade['attr']:
                attributes[key]=attributes.get(key,0)+value
        max_sync=max(r['times']for r in sync.values()if r['id']==sid)
        # Preserve percent modifiers as their own protocol attributes; do not
        # invent an authoritative combat formula for this display profile.
        for upgrade in sync.values():
            if upgrade['id']==sid:
                for key,value in upgrade['attr']:attributes[key]=attributes.get(key,0)+value
        owned_skins=[s for s in base['skin_list']if str(s)in skins]
        if not owned_skins:raise ValueError(f'missing skin: {sid}')
        favor=max((r for r in favor_levels.values()if r['id']==sid),key=lambda r:r['lvl'])
        cards.append(dict(id=str(sid),type=1,sys_id=sid,exp='0',lvl=level,
            sync_times=max_sync,awake_times=top['times'],secondary_skill=[],
            attr=[{'k':str(k),'v':str(v)}for k,v in sorted(attributes.items())],get_time=now,
            favor_lvl=favor['lvl'],favor_award_lvl=[],favor=favor['range_max'],fight_skill=top['skill_id'],
            skill_lvl=max((r['lvl']for r in skill_levels.values()if r['children_id']==sid),default=1),
            use_skin=str(owned_skins[0]),skin_list=[str(s)for s in owned_skins],dispatch_id=0,
            star=base['star'],gain_times=1,power='0',auth_equip_id='0',is_new=0,fetter_break=0,patrol_id=0))
    heroes=[]
    forms=load(directory,'hero');hero_levels=load(directory,'hero_lvl');hero_awake=load(directory,'hero_awake')
    for sid in sorted({r['id']for r in hero_awake.values()}):
        form_list=[];form_children=[]
        for f in sorted((r for r in forms.values()if r['id']==sid),key=lambda r:r['form']):
            child=children[str(f['children_id'])];skin_list=[s for s in child['skin_list']if str(s)in skins]
            max_lvl=max(r['lvl']for r in hero_levels.values()if r['id']==sid and r['form']==f['form'])
            form_list.append(dict(form=f['form'],sync_times=0,lvl=max_lvl,exp=0,
                use_skin=str(skin_list[0]),skin_list=[str(s)for s in skin_list]))
            form_children.append(f['children_id'])
        heroes.append(dict(id=str(sid),type=7,awaketimes=max(r['awake_times']for r in hero_awake.values()if r['id']==sid),
            sys_id=str(sid),children_id=str(form_children[0]),form_list=form_list))
    levels=load(directory,'lvl');levels=levels if isinstance(levels,list)else levels.values()
    return {'version':1,'created_time':now,'all_functions':True,
            'account_level':max(r['lvl']for r in levels),'cards':cards,'heroes':heroes,
            'skin_list':sorted({s for c in cards for s in c['skin_list']},key=int),
            'limitations':['Combat formulas, equipment and advanced system behavior remain incomplete.']}
