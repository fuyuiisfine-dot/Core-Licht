"""Owned local teams; no battle completion or reward shortcuts."""
import json


def get(core,role_id,gm,event_id):
    assist={f.name:(''if f.type==f.TYPE_STRING else 0)for f in
        core.protocol.pool.FindMessageTypeByName('ZeroProto.p_friend_assist').fields}
    team={'team_index':1,'team_id':str(event_id),'event_id':str(event_id),
          'team_name':'Sandbox','children_list':[{'k':str(i),'v':c['id']}
              for i,c in enumerate(gm['cards'][:8],1)],'spell_list':[],
          'friend_assist':assist,'up_flag':0,'hero_list':[
              {'index':1,'hero_id':gm['heroes'][0]['id'],'hero_form':1}], 'fetter_child_list':[]}
    return core.snapshot(role_id,'sandbox_team:'+str(event_id),{'default_index':1,'children_team':[team]})


def change(core,role_id,gm,key,request):
    if key=='15_1':
        rows=core.db.execute('SELECT domain,value FROM role_snapshots WHERE role_id=? AND domain LIKE ?',
                            (role_id,'sandbox_team:%')).fetchall()
        found=[(r['domain'],json.loads(r['value']))for r in rows
               if any(int(t['team_id'])==request.team_id for t in json.loads(r['value'])['children_team'])]
        if len(found)!=1:raise ValueError('unknown or ambiguous owned team')
        domain,state=found[0]
        team=next(t for t in state['children_team']if int(t['team_id'])==request.team_id)
        slots=set();selected=set();heroes={int(h['id']):h for h in gm['heroes']}
        converted=[]
        for item in request.hero_list:
            hero=heroes.get(item.hero_id)
            if not hero or item.hero_form not in {f['form']for f in hero['form_list']}:raise PermissionError('hero form is not owned')
            if item.index not in (1,2,3)or item.index in slots or item.hero_id in selected:raise ValueError('invalid hero slot')
            slots.add(item.index);selected.add(item.hero_id)
            converted.append({'index':item.index,'hero_id':str(item.hero_id),'hero_form':item.hero_form})
        team['hero_list']=converted
        response=None  # This C2S intentionally has no S2C counterpart.
    else:
        state=get(core,role_id,gm,request.event_id)
        domain='sandbox_team:'+str(request.event_id)
        index=request.default_index if key=='15_5'else request.team_index
        team=next((t for t in state['children_team']if t['team_index']==index),None)
        if not team:raise ValueError('team index does not exist')
        if key=='15_2':
            if int(team['team_id'])!=request.team_id:raise PermissionError('team identity mismatch')
            owned={int(c['id'])for c in gm['cards']}
            slots=set();members=set();converted=[]
            max_slots=max(v[2]for v in core.config['team_slots']['value'])
            for item in request.children_list:
                if item.v not in owned:raise PermissionError('character is not owned')
                if not 1<=item.k<=max_slots or item.k in slots or item.v in members:raise ValueError('invalid character slot')
                slots.add(item.k);members.add(item.v);converted.append({'k':str(item.k),'v':str(item.v)})
            fetters=[]
            for item in request.fetter_child_list:
                if item.v not in owned:raise PermissionError('fetter character is not owned')
                fetters.append({'k':str(item.k),'v':str(item.v)})
            team['children_list']=converted;team['fetter_child_list']=fetters
            response={'result':0,'children_team':team}
        elif key=='15_3':
            name=request.team_name.strip()
            if not name or len(name)>32:raise ValueError('invalid team name')
            team['team_name']=name
            response={'result':0,'event_id':str(request.event_id),'team_index':str(index),'team_name':name}
        elif key=='15_5':
            state['default_index']=index
            response={'result':0,'event_id':str(request.event_id),'default_index':index}
        else:raise NotImplementedError(key)
    with core.db:core.db.execute('UPDATE role_snapshots SET value=? WHERE role_id=? AND domain=?',
                                (json.dumps(state),role_id,domain))
    return response
