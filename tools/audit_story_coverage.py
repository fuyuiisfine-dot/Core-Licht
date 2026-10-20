"""Read-only audit of visible dialogue coverage in the private story export."""
import argparse
import json
from pathlib import Path

from prepare_story_replay import dialogue_params, load_scenario_data, lua_type, translated
from extract_config_tables import extract


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(
        r'C:\Users\USER\Desktop\assets_images_20260927_193401\text_assets\Zero\Lua\lua.ab'))
    args = parser.parse_args()
    source = args.source.resolve()
    story, _ = load_scenario_data(source)
    scenarios = extract(source, 'scenario')['data']
    book = extract(source, 'illustratedbook_chapter')['data']
    book_ids = {row['scenario_id'] for row in book.values()}
    translations = {row['id']: row['content'] for row in extract(source, 'scenario_translation')['data']}
    covered = missing = total = 0
    missing_ids = set()
    for scene_id, metadata in ((int(key), value) for key, value in scenarios.items()):
        name = metadata.get('desc', '')
        if scene_id not in book_ids and ('測試' in name or '示例' in name):
            continue
        scene = story[scene_id]
        if lua_type(scene) != 'table':
            continue
        for _, step in scene.items():
            if lua_type(step) != 'table':
                continue
            for _, event in step.items():
                if lua_type(event) != 'table' or event[b'sub_type'] != b'dialog':
                    continue
                for params in dialogue_params(event[b'params']):
                    total += 1
                    raw = params[b'content']
                    if translated(raw, translations):
                        covered += 1
                    else:
                        missing += 1
                        missing_ids.add(str(raw))
    print(json.dumps(dict(dialogue_fields=total, translated=covered,
                          missing_translation=missing,
                          missing_ids=sorted(missing_ids)), ensure_ascii=False))


if __name__ == '__main__':
    main()
