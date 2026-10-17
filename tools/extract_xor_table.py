"""Extract the exact private field referenced by SNPacketData..cctor."""
import hashlib
import json
import struct
from pathlib import Path

raw=Path('analysis/native/global-metadata.dat').read_bytes()
header=struct.unpack('<66I',raw[:264])
if header[:2] != (0xfab11baf,24):raise ValueError('unsupported metadata format')
string_offset=header[6]
field_offset,field_size=header[24:26]
default_offset,default_size=header[16:18]
data_offset=header[18]
sha1='AFDB694BFA892BC872A116B516A86C3A8C1C83EE'
name_index=raw.index(sha1.encode(),string_offset)-string_offset
found=[]
for index in range(field_size//12):
    if struct.unpack_from('<I',raw,field_offset+index*12)[0]!=name_index:continue
    for offset in range(default_offset,default_offset+default_size,12):
        field,type_index,data_index=struct.unpack_from('<iii',raw,offset)
        if field!=index:continue
        start=data_offset+data_index
        table=raw[start:start+256]
        if hashlib.sha1(table).hexdigest().upper()!=sha1:raise ValueError('field hash mismatch')
        Path('analysis/packet_xor_table.bin').write_bytes(table)
        found.append({'metadata_offset':hex(start),'length':256,'sha1':sha1,
                      'cctor_rva':'0x1586334','field_handle_got':'0x2cabfd0',
                      'field_handle_relocation':'0x2eb2368'})
if len(found)!=1:raise ValueError('ambiguous or missing table')
Path('analysis/packet_xor_provenance.json').write_text(json.dumps(found[0],indent=2))
print(json.dumps(found[0],indent=2))
