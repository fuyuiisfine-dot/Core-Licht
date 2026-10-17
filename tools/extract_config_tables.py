"""Read generated config chunks in a Lua-only environment without host access.

Only the requested DataTable, its numbered parts and DataBase helper are loaded. No host require,
filesystem, networking, OS, debug, Python, or client-native APIs are exposed.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.dependencies/python'))
from lupa.lua54 import LuaRuntime, lua_type
from inspect_protocol import Lua54


def plain(value,stack=()):
    kind=lua_type(value)
    if kind=='table':
        identity=repr(value)
        if identity in stack or len(stack)>30:raise ValueError('cyclic or excessively nested config')
        items=list(value.items());keys={k for k,v in items}
        if keys==set(range(1,len(items)+1)):
            return [plain(value[i],stack+(identity,)) for i in range(1,len(items)+1)]
        return {(k.decode('utf-8') if isinstance(k,bytes) else str(k)):plain(v,stack+(identity,)) for k,v in items}
    if kind is not None:raise ValueError('non-data Lua value: '+kind)
    if isinstance(value,bytes):return value.decode('utf-8')
    if value is None or isinstance(value,(int,float,bool,str)):return value
    raise ValueError('non-data value')


def extract(source_root,name):
    if not re.fullmatch(r'[a-zA-Z0-9_]+',name):raise ValueError('invalid table name')
    helper=next(source_root.glob('x.Config.DataBase_*'))
    source=next(source_root.glob('x.Config.Excel.tw.DataTable_'+name+'_TextAsset*'))
    chunk=Lua54(source.read_bytes());chunk.parse()
    getter=next(v for v in chunk.constants[0] if isinstance(v,str) and re.fullmatch('GetSys'+re.escape(name),v))
    lua=LuaRuntime(encoding=None,max_memory=64*1024*1024,register_eval=False,register_builtins=False)
    environment=lua.eval(b'''function()
      local e={GameDefine={UNITY_EDITOR=false}}
      for _,k in ipairs({'assert','error','pairs','ipairs','next','type','tonumber',
        'tostring','setmetatable','getmetatable','rawget','rawset','select','table','string','math'}) do e[k]=_G[k] end
      e._G=e;return e end''')()
    # Some large generated tables chain numbered parts. Resolve only exact
    # same-table part names into an in-memory Lua bytecode map; no host loader.
    module_bytes={};provenance={}
    for part in source_root.glob('x.Config.Excel.tw.DataTable_'+name+'_*_TextAsset*'):
        module_name=part.name.split('_TextAsset')[0]
        if not re.fullmatch(r'x\.Config\.Excel\.tw\.DataTable_'+re.escape(name)+r'_\d+',module_name):continue
        raw=part.read_bytes();Lua54(raw).parse()
        module_bytes[module_name.encode()]=raw
        provenance[part.name]=hashlib.sha256(raw).hexdigest()
    environment[b'require']=lua.eval(b'''function(e,modules)
      local loaded={}
      return function(name)
        if loaded[name] then return loaded[name] end
        local bytes=assert(modules[name],'config dependency is outside allowlist')
        loaded[name]=true
        local result=assert(load(bytes,'config-part','b',e))()
        loaded[name]=result or true;return loaded[name]
      end
    end''')(environment,lua.table_from(module_bytes))
    runner=lua.eval(b'''function(e,bytes)
      local n=0
      debug.sethook(function() n=n+1000;if n>20000000 then error('instruction budget exceeded') end end,'',1000)
      local f=assert(load(bytes,'config-data','b',e));local r=f();debug.sethook();return r end''')
    runner(environment,helper.read_bytes())
    runner(environment,source.read_bytes())
    result=plain(environment[b'DataBase'][getter.encode()]())
    return {'source':source.name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'numbered_parts':provenance,'getter':getter,'data':result}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('tables',nargs='+')
    p.add_argument('--source',type=Path,default=Path(r'C:\Users\USER\Desktop\assets_images_20260927_193401\text_assets\Zero\Lua\lua.ab'))
    p.add_argument('--output',type=Path,default=Path('analysis/config'))
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    for name in args.tables:
        result=extract(args.source,name)
        (args.output/(name+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(name,'records',len(result['data']))


if __name__=='__main__':main()
