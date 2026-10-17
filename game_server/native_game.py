"""Server-authoritative native rehearsal battles, not the original combat engine.

Original character attributes and stage labels/costs are reused. Movement, AI,
enemy waves, progression and rehearsal points are explicitly prototype rules.
No original dungeon clear, drop or quest state is fabricated.
"""
import json
import math
import secrets

STAGES = (10001, 10002, 10003)
STEP = .25
DOMAIN = 'native_rehearsal'


def _load(core, role, domain, default):
    row = core.db.execute('SELECT value FROM role_snapshots WHERE role_id=? AND domain=?', (role, domain)).fetchone()
    return json.loads(row['value']) if row else default


def _save(core, role, domain, value):
    core.db.execute('INSERT OR REPLACE INTO role_snapshots VALUES (?,?,?)', (role, domain, json.dumps(value)))


def _integer(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or not -(2**63) <= value < 2**63:
        raise ValueError(name+' must be an integer')
    return value


def _stages(core):
    source = json.loads((core.protocol.directory/'config/dungeon.json').read_text(encoding='utf-8'))['data']
    return [dict(id=sid, number=source[str(sid)]['number'], name=source[str(sid)]['name'],
                 cost=source[str(sid)]['cost_vita'], reward=100*(i+1), prerequisite=STAGES[i-1] if i else 0)
            for i, sid in enumerate(STAGES)]


def _vitality(core, role):
    level = core.db.execute('SELECT level FROM roles WHERE id=?', (role,)).fetchone()['level']
    config = core.levels[level]
    return _load(core, role, 'vitality', dict(vitality=config['gain_vit'], vit_max=config['vit_max'],
                exchange_num=0, daily_reward=0, new_role_reward=0, next_time=0))


def _owned_team(core, role):
    gm = _load(core, role, 'sandbox_gm', None)
    if not gm:
        raise ValueError('Rehearsal currently requires a prepared character roster')
    owned = {str(card['id']): card for card in gm['cards']}
    teams = _load(core, role, 'sandbox_team:10001', None)
    if teams:
        team = next(t for t in teams['children_team'] if t['team_index'] == teams['default_index'])
        ids = [str(v['v']) for v in sorted(team['children_list'], key=lambda v: int(v['k']))]
    else:
        ids = [str(card['id']) for card in gm['cards'][:8]]
    if not ids or len(set(ids)) != len(ids) or len(ids) > 8 or any(i not in owned for i in ids):
        raise ValueError('Save a valid nonempty team first')
    result = []
    for identity in ids:
        card = owned[identity]
        attrs = {int(a['k']): int(a['v']) for a in card['attr']}
        result.append(dict(id=identity, sys_id=str(card['sys_id']), skin=str(card['use_skin']),
                           hp=max(1, attrs.get(11, 1)), attack=max(1, attrs.get(12, 1)),
                           defense=max(0, attrs.get(14, 0)), deployed=False))
    return result


def _persist_battle(core, role, battle):
    core.db.execute('UPDATE native_battles SET status=?,state=? WHERE id=? AND role_id=?',
                    (battle['status'], json.dumps(battle), battle['id'], role))


def _tick(battle):
    battle['tick'] += 1
    time = battle['tick'] * STEP
    if battle['spawned'] < battle['enemy_total'] and time >= battle['spawned']*1.5:
        i = battle['spawned']
        rank = STAGES.index(battle['stage'])+1
        hp = 750+rank*250
        battle['units'].append(dict(id='enemy-'+str(i), side='enemy', x=12.5, y=1+(i%5),
                                    hp=hp, max_hp=hp, attack=80+rank*35, defense=20*rank,
                                    cooldown=0, sys_id=''))
        battle['spawned'] += 1
    units = battle['units']
    for unit in units:
        if unit['hp'] <= 0:
            continue
        targets = [t for t in units if t['side'] != unit['side'] and t['hp'] > 0]
        unit['cooldown'] = max(0, unit['cooldown']-STEP)
        if not targets:
            continue
        target = min(targets, key=lambda t: (math.hypot(t['x']-unit['x'], t['y']-unit['y']), t['id']))
        dx, dy = target['x']-unit['x'], target['y']-unit['y']
        distance = math.hypot(dx, dy)
        if distance <= 2.2:
            if unit['cooldown'] <= 0:
                target['hp'] = max(0, target['hp']-max(1, unit['attack']-target['defense']//2))
                unit['cooldown'] = 1
                battle['last_hit'] = dict(source=unit['id'], target=target['id'], tick=battle['tick'])
        elif distance:
            movement = min(distance-2.1, STEP*1.3)
            unit['x'] += dx/distance*movement
            unit['y'] += dy/distance*movement
    battle['kills'] = sum(1 for u in units if u['side'] == 'enemy' and u['hp'] <= 0)
    if battle['kills'] == battle['enemy_total']:
        battle['status'] = 'victory'
        battle['stars'] = 3 if all(u['hp'] > 0 for u in units if u['side'] == 'ally') else 2
    elif time >= 60 or (time >= 15 and not any(u['side'] == 'ally' and u['hp'] > 0 for u in units)):
        battle['status'] = 'defeat'
        battle['stars'] = 0


def _advance(core, battle):
    target = min(240, max(0, int((core.clock()-battle['started'])/STEP)))
    while battle['status'] == 'active' and battle['tick'] < target:
        _tick(battle)


def _reply(core, role, progress, battle=None):
    return dict(progress=progress, vitality=_vitality(core, role), stages=_stages(core), battle=battle,
                rules='native-rehearsal-v1', original_combat=False)


def handle(core, path, values):
    """Each command is serialized with its stamina, battle and reward writes."""
    uid = str(values.get('uid', ''))
    if not core.valid(uid, str(values.get('token', '')), str(values.get('p_key', ''))):
        raise PermissionError('Local credentials required')
    role = _integer(values.get('role_id'), 'role_id')
    if not core.db.execute('SELECT 1 FROM roles WHERE id=? AND uid=?', (role, uid)).fetchone():
        raise PermissionError('Role does not belong to account')
    core.db.execute('''CREATE TABLE IF NOT EXISTS native_battles (
        id TEXT PRIMARY KEY, role_id INTEGER NOT NULL, start_key TEXT NOT NULL,
        status TEXT NOT NULL, state TEXT NOT NULL, UNIQUE(role_id,start_key))''')
    core.db.execute('BEGIN IMMEDIATE')
    try:
        progress = _load(core, role, DOMAIN, dict(points=0, clears={}, victories=0))
        if path == 'state':
            row = core.db.execute("SELECT state FROM native_battles WHERE role_id=? ORDER BY rowid DESC LIMIT 1", (role,)).fetchone()
            battle = json.loads(row['state']) if row else None
            if battle:
                _advance(core, battle)
                _persist_battle(core, role, battle)
        elif path == 'start':
            stage = _integer(values.get('stage'), 'stage')
            if stage not in STAGES:
                raise ValueError('Unknown rehearsal')
            key = values.get('request_id')
            if not isinstance(key, str) or not 16 <= len(key) <= 80:
                raise ValueError('A unique request_id is required')
            old = core.db.execute('SELECT state FROM native_battles WHERE role_id=? AND start_key=?', (role, key)).fetchone()
            if old:
                battle = json.loads(old['state'])
                if battle['stage'] != stage:
                    raise ValueError('request_id already used for a different stage')
                _advance(core, battle)
                _persist_battle(core, role, battle)
            else:
                if core.db.execute("SELECT 1 FROM native_battles WHERE role_id=? AND status!='claimed'", (role,)).fetchone():
                    raise ValueError('Finish or abandon the existing battle first')
                meta = next(s for s in _stages(core) if s['id'] == stage)
                if meta['prerequisite'] and not progress['clears'].get(str(meta['prerequisite'])):
                    raise ValueError('Clear the preceding rehearsal first')
                roster = _owned_team(core, role)
                vitality = _vitality(core, role)
                if vitality['vitality'] < meta['cost']:
                    raise ValueError('Not enough stamina')
                vitality['vitality'] -= meta['cost']
                _save(core, role, 'vitality', vitality)
                battle = dict(id=secrets.token_hex(16), stage=stage, started=core.clock(), tick=0,
                              status='active', roster=roster, units=[], spawned=0, kills=0,
                              enemy_total=3+STAGES.index(stage)*2, stars=0, reward=meta['reward'])
                core.db.execute('INSERT INTO native_battles VALUES (?,?,?,?,?)',
                                (battle['id'], role, key, 'active', json.dumps(battle)))
        elif path in ('deploy', 'claim', 'abandon'):
            identity = values.get('battle_id')
            if not isinstance(identity, str):
                raise ValueError('battle_id required')
            row = core.db.execute('SELECT state FROM native_battles WHERE id=? AND role_id=?', (identity, role)).fetchone()
            if not row:
                raise PermissionError('Battle does not belong to role')
            battle = json.loads(row['state'])
            _advance(core, battle)
            if path == 'deploy':
                if battle['status'] != 'active':
                    raise ValueError('Battle has ended')
                card = next((c for c in battle['roster'] if c['id'] == str(values.get('card_id', ''))), None)
                if not card or card['deployed']:
                    raise ValueError('Choose an undeployed team member')
                x, y = _integer(values.get('x'), 'x'), _integer(values.get('y'), 'y')
                if not 0 <= x <= 5 or not 0 <= y <= 6:
                    raise ValueError('Deploy inside the allied area')
                if any(u['side'] == 'ally' and u['hp'] > 0 and math.hypot(u['x']-x, u['y']-y) < .7 for u in battle['units']):
                    raise ValueError('Position occupied')
                card['deployed'] = True
                battle['units'].append(dict(id=card['id'], sys_id=card['sys_id'], side='ally', x=float(x), y=float(y),
                                            hp=card['hp'], max_hp=card['hp'], attack=card['attack'], defense=card['defense'], cooldown=0))
            elif path == 'abandon':
                if battle['status'] != 'claimed':
                    battle.update(status='claimed', outcome='abandoned', stars=0, granted=0)
            elif battle['status'] != 'claimed':
                if battle['status'] not in ('victory', 'defeat'):
                    raise ValueError('Battle is still active')
                battle['outcome'] = battle['status']
                if battle['status'] == 'victory':
                    progress['points'] += battle['reward']
                    progress['victories'] += 1
                    progress['clears'][str(battle['stage'])] = max(battle['stars'], progress['clears'].get(str(battle['stage']), 0))
                    battle['granted'] = battle['reward']
                else:
                    battle['granted'] = 0
                battle['status'] = 'claimed'
                _save(core, role, DOMAIN, progress)
            _persist_battle(core, role, battle)
        else:
            raise ValueError('Unknown gameplay command')
        reply = _reply(core, role, progress, battle)
        core.db.commit()
        return reply
    except Exception:
        core.db.rollback()
        raise
