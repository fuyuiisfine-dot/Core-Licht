"""Generate non-private cross-language vectors, never actual account credentials."""
import base64
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from google.protobuf.json_format import MessageToDict
from game_server.protocol import Protocol


def initialize(message):
    for field in message.DESCRIPTOR.fields:
        if field.label!=field.LABEL_REQUIRED:continue
        if field.message_type:initialize(getattr(message,field.name))
        elif field.type==field.TYPE_STRING:setattr(message,field.name,'Native test')
        elif field.type==field.TYPE_BYTES:setattr(message,field.name,b'')
        elif field.type==field.TYPE_ENUM:setattr(message,field.name,field.enum_type.values[0].number)
        elif field.type==field.TYPE_BOOL:setattr(message,field.name,False)
        else:setattr(message,field.name,0)
    return message


if __name__=='__main__':
    protocol=Protocol();cases=[]
    for direction,mapping in protocol.ids.items():
        for key in mapping:
            message=initialize(protocol.make(direction,key))
            cases.append({'direction':direction,'id':key,
                'values':MessageToDict(message,preserving_proto_field_name=True,use_integers_for_enums=True),
                'bytes':base64.b64encode(message.SerializeToString()).decode()})
    path=Path('client-work/windows-client/wire-tests.json')
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps({'cases':cases}),encoding='utf-8')
    print('Generated cross-language cases:',len(cases))
