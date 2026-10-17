"""Recover literal attribute tables; never execute Lua calls or control flow."""
import json
import sys
from pathlib import Path
from inspect_protocol import Lua54


class Unresolved:
    def __init__(self,name):self.name=name
    def __repr__(self):return '<unresolved:'+self.name+'>'


def recover(chunk):
    code,constants=chunk.functions[0]
    registers={};environment={};stopped=None
    def get(value,key):
        return value.get(key,Unresolved(str(key))) if isinstance(value,dict) else Unresolved(str(value)+'.'+str(key))
    for pc,instruction in enumerate(code):
        op=instruction&127;a=(instruction>>7)&255;b=(instruction>>16)&255;c=instruction>>24;k=(instruction>>15)&1
        if op in (81,82):continue
        if op==0:registers[a]=registers[b]
        elif op==1:registers[a]=(instruction>>15)-65535
        elif op==3:registers[a]=constants[instruction>>15]
        elif op==5:registers[a]=False
        elif op==7:registers[a]=True
        elif op==8:
            for i in range(a,a+b+1):registers[i]=None
        elif op==11:registers[a]=get(environment,constants[c])
        elif op==12:registers[a]=get(registers[b],registers[c])
        elif op==14:registers[a]=get(registers[b],constants[c])
        elif op==15:environment[constants[b]]=constants[c] if k else registers[c]
        elif op==16:registers[a][registers[b]]=constants[c] if k else registers[c]
        elif op==17:registers[a][b]=constants[c] if k else registers[c]
        elif op==18:registers[a][constants[b]]=constants[c] if k else registers[c]
        elif op==19:registers[a]={}
        elif op==68:
            if not c:raise ValueError('dynamic return count')
            function=registers[a]
            for i in range(c-1):registers[a+i]=Unresolved(str(function)+' result')
        elif op==78:
            if not b or k:raise ValueError('dynamic SETLIST')
            for i in range(1,b+1):registers[a][c+i]=registers[a+i]
        elif op==79:registers[a]=Unresolved('closure')
        else:stopped={'pc':pc,'opcode':op};break
    return environment,stopped


def main():
    source=next(Path(r'C:\Users\USER\Desktop\assets_images_20260927_193401\text_assets\Zero\Lua\lua.ab').glob('x.Game.PlayerDefine_*'))
    chunk=Lua54(source.read_bytes());chunk.parse()
    env,stopped=recover(chunk)
    table=env['PlayerDefine']['ATTR_SERVER_DRIVEN']
    result={'source':source.name,'interpretation':'literal setup only; calls unresolved; stop before control flow',
            'stopped':stopped,'attributes':table}
    Path('analysis/player_attributes.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=repr),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True,indent=2,default=repr))


if __name__=='__main__':main()
