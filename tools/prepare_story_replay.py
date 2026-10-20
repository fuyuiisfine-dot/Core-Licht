"""Extract chapter dialogue from a local game backup into private Windows data.

Only the named Lua bytecode and generated config tables are run in a Lua
environment without filesystem, network, package, OS, or host API access.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / '.dependencies/python', ROOT.parent / '.dependencies/python'):
    if candidate.exists():
        sys.path.insert(0, str(candidate))
        break

from lupa.lua54 import LuaRuntime, lua_type
from extract_config_tables import extract


def load_scenario_data(source_root):
    source = next(source_root.glob('x.Module.Scenario.ScenarioData_TextAsset_*.bin'))
    lua = LuaRuntime(encoding=None, max_memory=512 * 1024 * 1024,
                     register_eval=False, register_builtins=False)
    environment = lua.eval(b'''function()
      local e={}
      for _,k in ipairs({'assert','error','pairs','ipairs','next','type','tonumber',
        'tostring','setmetatable','getmetatable','rawget','rawset','select','table','string','math'}) do e[k]=_G[k] end
      e.GetTranslation=function(id) return id end
      e._G=e;return e end''')()
    runner = lua.eval(b'''function(e,bytes)
      local n=0
      debug.sethook(function() n=n+1000;if n>100000000 then error('instruction budget exceeded') end end,'',1000)
      assert(load(bytes,'scenario-data','b',e))()
      debug.sethook()
    end''')
    raw = source.read_bytes()
    runner(environment, raw)
    data = environment[b'ScenarioData']
    if lua_type(data) != 'table':
        raise ValueError('ScenarioData did not contain a table')
    return data, hashlib.sha256(raw).hexdigest()


def translated(value, translations):
    if value is None:
        return ''
    if isinstance(value, bytes):
        value = value.decode('utf-8')
    try:
        number = int(value)
    except (TypeError, ValueError):
        return str(value).strip()
    return translations.get(number, '')


def dialogue_params(node, depth=0):
    if lua_type(node) != 'table' or depth > 5:
        return
    if b'content' in node:
        yield node
    else:
        for _, child in sorted(node.items(), key=lambda pair: (0, pair[0]) if isinstance(pair[0], int) else (1, str(pair[0]))):
            yield from dialogue_params(child, depth + 1)


def scene_lines(scene_data, translations):
    lines = []
    if lua_type(scene_data) != 'table':
        return lines
    for step_number, step in sorted(scene_data.items()):
        if lua_type(step) != 'table':
            continue
        for _, event in sorted((pair for pair in step.items() if isinstance(pair[0], int))):
            if lua_type(event) != 'table' or event[b'sub_type'] != b'dialog':
                continue
            for params in dialogue_params(event[b'params']):
                content = translated(params[b'content'], translations)
                if not content:
                    continue
                speaker = translated(params[b'name'], translations) if b'name' in params else ''
                lines.append(dict(step=step_number, speaker=speaker, text=content))
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(r'C:\Users\USER\Desktop\assets_images_20260927_193401\text_assets\Zero\Lua\lua.ab'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source_root = args.source.resolve()
    output = args.output.resolve()
    if source_root == output or source_root in output.parents:
        raise ValueError('Output must be outside the original backup')

    story_data, story_hash = load_scenario_data(source_root)
    book = extract(source_root, 'illustratedbook')
    chapter_rows = extract(source_root, 'illustratedbook_chapter')
    scenarios = extract(source_root, 'scenario')
    translation_rows = extract(source_root, 'scenario_translation')
    translations = {row['id']: row['content'] for row in translation_rows['data']}

    chapters = []
    line_count = 0
    missing_scenes = []
    book_ids = set()
    for chapter_id, chapter in sorted(book['data'].items(), key=lambda pair: pair[1]['sort']):
        scenes = []
        rows = sorted((row for row in chapter_rows['data'].values()
                       if row['chapter_id'] == int(chapter_id)), key=lambda row: row['sort'])
        for row in rows:
            scene_id = row['scenario_id']
            book_ids.add(scene_id)
            metadata = scenarios['data'].get(str(scene_id), {})
            lines = scene_lines(story_data[scene_id], translations)
            if not lines:
                missing_scenes.append(scene_id)
            line_count += len(lines)
            scenes.append(dict(id=scene_id, title=row['title'], name=row['name'],
                               subtitle=metadata.get('introduction_title', ''),
                               summary='\n'.join(metadata.get('introduction', [])), lines=lines))
        chapters.append(dict(id=int(chapter_id), title=chapter['title'],
                             name=chapter['name'], scenes=scenes))

    other_scenes = []
    for scene_id in sorted(int(key) for key in scenarios['data'] if int(key) not in book_ids):
        metadata = scenarios['data'][str(scene_id)]
        name = metadata.get('desc') or f'劇情 {scene_id}'
        if '測試' in name or '示例' in name:
            continue
        lines = scene_lines(story_data[scene_id], translations)
        if not lines:
            continue
        other_scenes.append(dict(id=scene_id, title=str(scene_id),
                                 name=name,
                                 subtitle=metadata.get('introduction_title', ''),
                                 summary='\n'.join(metadata.get('introduction', [])), lines=lines))
        line_count += len(lines)
    if other_scenes:
        chapters.append(dict(id=0, title='其他', name='其他劇情', scenes=other_scenes))

    result = dict(format='corelicht-story-replay-v1', chapters=chapters,
                  provenance=dict(scenario_data_sha256=story_hash,
                                  illustratedbook_sha256=book['sha256'],
                                  illustratedbook_chapter_sha256=chapter_rows['sha256'],
                                  scenario_sha256=scenarios['sha256'],
                                  scenario_translation_sha256=translation_rows['sha256']))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(json.dumps(dict(chapters=len(chapters), scenes=sum(len(ch['scenes']) for ch in chapters),
                          lines=line_count, other_scenes=len(other_scenes),
                          scenes_without_dialogue=missing_scenes,
                          output=str(output)), ensure_ascii=False))


if __name__ == '__main__':
    main()
