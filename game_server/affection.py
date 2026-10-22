"""Local GM affection and document state; never grant inventory rewards."""
import json


def maximize(profile,directory):
    def load(name):
        return json.loads((directory/'config'/(name+'.json')).read_text(encoding='utf-8'))['data']
    levels=load('children_favor_lvl');docs=load('children_doc')
    references={'char_list':('per',load('children_doc_char')),
                'voice_list':('voice',load('children_doc_voice')),
                'remember_list':('remember',load('children_doc_remember'))}
    old=profile.get('documents',{})
    unlocked={name:{int(v['k']):int(v['v'])for v in old.get(name,[])}for name in references}
    for card in profile['cards']:
        sid=card['sys_id']
        favor=max((r for r in levels.values()if r['id']==sid),key=lambda r:r['lvl'])
        card['favor_lvl']=favor['lvl'];card['favor']=favor['range_max']
        if str(sid)not in docs:raise ValueError(f'missing character documents: {sid}')
        for name,(field,records)in references.items():
            for entry_id in docs[str(sid)][field]:
                if str(entry_id)not in records:raise ValueError(f'missing document entry: {entry_id}')
                # DocumentModel: key presence unlocks; 0 means unread,
                # children_unlock response changes the state to 1 (read).
                unlocked[name].setdefault(entry_id,0)
    profile['documents']={name:[{'k':str(k),'v':str(v)}for k,v in sorted(values.items())]
                          for name,values in unlocked.items()}
    return profile
