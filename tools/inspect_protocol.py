"""Read-only asset inspection; writes derived reports only to the chosen output."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from google.protobuf import descriptor_pb2


class Lua54:
    def __init__(self, data):
        self.data, self.pos, self.constants, self.functions = data, 0, [], []

    def take(self, n):
        if n < 0 or self.pos + n > len(self.data):
            raise ValueError('truncated Lua chunk')
        result = self.data[self.pos:self.pos+n]
        self.pos += n
        return result

    def size(self):
        value = 0
        for _ in range(10):
            byte = self.take(1)[0]
            value = (value << 7) | (byte & 127)
            if byte & 128:
                return value
        raise ValueError('invalid Lua size')

    def string(self):
        size = self.size()
        return self.take(size-1).decode('utf-8', errors='replace') if size else None

    def function(self):
        self.string()
        self.size()
        self.size()
        self.take(3)
        count = self.size()
        code = struct.unpack('<' + 'I'*count, self.take(count*4))
        constants = []
        for _ in range(self.size()):
            tag = self.take(1)[0]
            if tag == 0: value = None
            elif tag == 1: value = False
            elif tag == 17: value = True
            elif tag == 3: value = struct.unpack('<q', self.take(8))[0]
            elif tag == 19: value = struct.unpack('<d', self.take(8))[0]
            elif tag in (4, 20): value = self.string()
            else: raise ValueError(f'unknown constant tag {tag}')
            constants.append(value)
        self.constants.append(constants)
        self.functions.append((code, constants))
        self.take(self.size()*3)
        for _ in range(self.size()): self.function()
        self.take(self.size())
        for _ in range(self.size()): self.size(); self.size()
        for _ in range(self.size()): self.string(); self.size(); self.size()
        for _ in range(self.size()): self.string()

    def parse(self):
        if self.take(12) != b'\x1bLua\x54\x00\x19\x93\r\n\x1a\n':
            raise ValueError('unsupported Lua header')
        if self.take(3) != b'\x04\x08\x08': raise ValueError('unsupported sizes')
        if struct.unpack('<q', self.take(8))[0] != 0x5678: raise ValueError('endianness')
        if struct.unpack('<d', self.take(8))[0] != 370.5: raise ValueError('number format')
        self.take(1)
        self.function()
        if self.pos != len(self.data): raise ValueError('trailing bytes')
        return self.constants


def read_static_table(chunk):
    """Interpret only literal table construction; reject calls and control flow.

    Opcode layout: https://www.lua.org/source/5.4/lopcodes.h.html
    This is deliberately not a general Lua interpreter and cannot call game code.
    """
    code, constants = chunk.functions[0]
    registers = {}
    for instruction in code:
        op = instruction & 127
        a, b, c = (instruction >> 7) & 255, (instruction >> 16) & 255, instruction >> 24
        k = (instruction >> 15) & 1
        if op in (81, 82): continue  # VARARGPREP, EXTRAARG
        if op == 19: registers[a] = {}  # NEWTABLE
        elif op == 3: registers[a] = constants[instruction >> 15]  # LOADK
        elif op == 16: registers[a][registers[b]] = constants[c] if k else registers[c]
        elif op == 18: registers[a][constants[b]] = constants[c] if k else registers[c]
        elif op == 78:
            if not b or k: raise ValueError('unsupported dynamic SETLIST')
            for i in range(1, b+1): registers[a][c+i] = registers[a+i]
        elif op == 70:
            if b != 2: raise ValueError('unsupported RETURN')
            return registers[a]
        else: raise ValueError(f'nonliteral opcode {op}')
    raise ValueError('no static table return')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.assets.resolve()
    output = args.output.resolve()
    if output == root or root in output.parents:
        raise ValueError('output must be outside original assets')
    output.mkdir(parents=True, exist_ok=True)
    combined = descriptor_pb2.FileDescriptorSet()
    schemas, failures = [], []
    for path in sorted((root/'text_assets/Zero/PB/pb.ab').glob('*.bin')):
        try:
            desc = descriptor_pb2.FileDescriptorSet.FromString(path.read_bytes())
            if not desc.file: raise ValueError('no file descriptors')
            for file in desc.file:
                combined.file.add().CopyFrom(file)
                schemas.append({'file': file.name, 'package': file.package,
                    'dependencies': list(file.dependency), 'messages': [
                        {'name': m.name, 'fields': [
                            {'name': f.name, 'number': f.number,
                             'type': descriptor_pb2.FieldDescriptorProto.Type.Name(f.type),
                             'label': descriptor_pb2.FieldDescriptorProto.Label.Name(f.label),
                             'type_name': f.type_name} for f in m.field]} for m in file.message_type]})
        except Exception as error:
            failures.append({'file': str(path.relative_to(root)), 'error': str(error)})
    (output/'protocol.desc').write_bytes(combined.SerializeToString())
    (output/'schemas.json').write_text(json.dumps(schemas, ensure_ascii=False, indent=2), encoding='utf-8')
    lua_results = {}
    for path in sorted((root/'text_assets/Zero/Lua/lua.ab').glob('*.bin')):
        name = path.name.split('_TextAsset_')[0]
        if not (name.startswith(('x.Core.Net.', 'x.Proto.', 'x.Module.Login.'))): continue
        data = path.read_bytes()
        try:
            lua_results[name] = {'sha256': hashlib.sha256(data).hexdigest(),
                                 'functions_constants': Lua54(data).parse()}
        except Exception as error:
            failures.append({'file': str(path.relative_to(root)), 'error': str(error)})
    (output/'lua_constants.json').write_text(json.dumps(lua_results, ensure_ascii=False, indent=2), encoding='utf-8')
    map_path = next((root/'text_assets/Zero/Lua/lua.ab').glob('x.Proto.ProtoMap_*'))
    map_chunk = Lua54(map_path.read_bytes())
    map_chunk.parse()
    table = read_static_table(map_chunk)
    (output/'active_protocol_files.json').write_text(json.dumps(
        [name+'.proto' for name in table['pbs'].values()], indent=2), encoding='utf-8')
    mappings = {direction: {key: table['packagename']+value for key,value in table[direction].items()}
                for direction in ('c2s','s2c')}
    known = {f.package+'.'+m.name for f in combined.file for m in f.message_type}
    for direction, mapping in mappings.items():
        for key, value in mapping.items():
            if value not in known: raise ValueError(f'unknown mapped message: {direction} {key} {value}')
    (output/'message_ids.json').write_text(json.dumps(mappings, indent=2), encoding='utf-8')
    summary = {'descriptor_files': len(combined.file),
               'messages': sum(len(f.message_type) for f in combined.file),
               'lua_chunks_parsed': len(lua_results),
               'mapped_messages': {k: len(v) for k,v in mappings.items()}, 'failures': failures}
    (output/'inspection.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__': main()
