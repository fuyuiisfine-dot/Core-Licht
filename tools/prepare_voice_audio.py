"""Export private FMOD voice samples from an owned OBB for the Windows preview.

Only voice IDs present in the private Windows catalog are exported. No audio is
placed in the source tree or Git; the default output is client-work/windows-client.
"""
import argparse
import json
import struct
import sys
import wave
import zipfile
from pathlib import Path


def fsbs(bank):
    """Yield embedded FSB5 files and their subsound names in decoding order."""
    start = 0
    while True:
        start = bank.find(b'FSB5', start)
        if start < 0:
            return
        if start + 60 > len(bank):
            raise ValueError('truncated FSB header')
        version, count, sample_headers, names_size, data_size = struct.unpack_from('<5I', bank, start + 4)
        size = 60 + sample_headers + names_size + data_size
        if version != 1 or not 0 < count < 10000 or size > len(bank) - start:
            raise ValueError('invalid FSB5 in bank')
        table = start + 60 + sample_headers
        names = []
        for index in range(count):
            offset = struct.unpack_from('<I', bank, table + 4 * index)[0]
            if offset >= names_size:
                raise ValueError('invalid FSB5 name offset')
            end = bank.find(b'\0', table + offset, table + names_size)
            if end < 0:
                raise ValueError('unterminated FSB5 name')
            names.append(bank[table + offset:end].decode('utf-8'))
        yield bank[start:start + size], names
        start += size


def export(backup, analysis, output, only_bank=None):
    backup, analysis, output = backup.resolve(), analysis.resolve(), output.resolve()
    if backup == output or backup in output.parents:
        raise ValueError('output must be outside the original backup')
    catalog = json.loads((output / 'data/catalog.json').read_text(encoding='utf-8'))['characters']
    config = json.loads((analysis / 'config/children_doc_voice.json').read_text(encoding='utf-8'))['data']
    wanted = {}
    for character in catalog.values():
        for voice in character['voices']:
            voice_id = str(voice['id'])
            event = config[voice_id].get('voice_name', '').rsplit('/', 1)[-1]
            if event:
                wanted.setdefault(event.casefold(), []).append(voice_id)
    audio = output / 'data/voices'
    audio.mkdir(parents=True, exist_ok=True)
    for parent in Path(__file__).resolve().parents[1:3]:
        dependencies = parent / '.dependencies/python'
        if dependencies.is_dir():
            sys.path.insert(0, str(dependencies))
            break
    from fmod_toolkit import raw_to_wav

    archives = [zipfile.ZipFile(path) for path in sorted(backup.glob('*.obb'), reverse=True)]
    if not archives:
        raise FileNotFoundError('No OBB files in ' + str(backup))
    banks = {}
    for archive in archives:
        for member in archive.namelist():
            if member.startswith('assets/FMOD/') and member.endswith('.assets.bank'):
                banks.setdefault(member, archive)
    exported = set()
    failures = []
    try:
        for member, archive in banks.items():
            if only_bank and Path(member).name.casefold() != (only_bank + '.assets.bank').casefold():
                continue
            try:
                for fsb, names in fsbs(archive.read(member)):
                    matched = []
                    for index, name in enumerate(names):
                        key = name.casefold()
                        if key not in wanted and key.endswith(('_a', '_b')):
                            key = key[:-2]
                        elif key not in wanted and key.endswith(('a', 'b')):
                            key = key[:-1]
                        if key in wanted:
                            pending = [voice_id for voice_id in wanted[key]
                                       if not (audio / (voice_id + '.wav')).is_file()]
                            if pending:
                                matched.append((index, pending))
                    if not matched:
                        continue
                    decoded = raw_to_wav(fsb, 'sample', 2, 44100)
                    for index, ids in matched:
                        filename = 'sample' + (('-' + str(index)) if index else '') + '.wav'
                        body = decoded[filename]
                        for voice_id in ids:
                            target = audio / (voice_id + '.wav')
                            target.write_bytes(body)
                            with wave.open(str(target), 'rb') as sample:
                                if sample.getnframes() == 0:
                                    raise ValueError('empty WAV: ' + str(target))
                            exported.add(voice_id)
            except Exception as exc:
                failures.append({'bank': member, 'error': str(exc)})
    finally:
        for archive in archives:
            archive.close()
    available = sum((audio / (voice_id + '.wav')).is_file() for ids in wanted.values() for voice_id in ids)
    result = {'available': available, 'wanted': sum(map(len, wanted.values())),
              'newly_exported': len(exported), 'failures': failures, 'directory': str(audio)}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', type=Path, default=Path(r'D:\tool\platform-tools-latest-windows\platform-tools\game_backup\obb'))
    parser.add_argument('--analysis', type=Path, default=Path('analysis'))
    parser.add_argument('--output', type=Path, default=Path('client-work/windows-client'))
    parser.add_argument('--bank', help='Extract one bank, for example Gabi')
    args = parser.parse_args()
    print(json.dumps(export(args.backup, args.analysis, args.output, args.bank), ensure_ascii=False, indent=2))
