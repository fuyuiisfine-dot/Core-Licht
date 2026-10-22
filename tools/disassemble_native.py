"""Disassemble a bounded address range in a copied ELF; never executes it."""
import argparse
import io
import json
import re
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.dependencies/python'))
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
from elftools.elf.elffile import ELFFile


def main():
    p=argparse.ArgumentParser()
    p.add_argument('start',type=lambda s:int(s,0))
    p.add_argument('end',type=lambda s:int(s,0))
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    raw=Path('analysis/native/libil2cpp.so').read_bytes()
    elf=ELFFile(io.BytesIO(raw))
    lines=Path('analysis/il2cpp/dump.cs').read_text(encoding='utf-8-sig').splitlines()
    names={}
    for index,line in enumerate(lines[:-1]):
        match=re.search(r'RVA: 0x([0-9A-F]+)',line)
        if match:names[int(match[1],16)]=lines[index+1].strip()
    for seg in elf.iter_segments():
        if seg['p_vaddr']<=args.start<args.end<=seg['p_vaddr']+seg['p_filesz']:
            offset=args.start-seg['p_vaddr']+seg['p_offset']
            code=raw[offset:offset+args.end-args.start]
            break
    else:raise ValueError('range outside mapped file')
    output=[]
    annotations={}
    script_path=Path('analysis/il2cpp/script.json')
    if script_path.exists():
        script=json.loads(script_path.read_text(encoding='utf-8-sig'))
        for key in ('ScriptString','ScriptMetadata','ScriptMetadataMethod'):
            for item in script.get(key,[]):
                annotations[item['Address']]=item.get('Value',item.get('Name',''))
    relocations={}
    for section in elf.iter_sections():
        if section['sh_type']=='SHT_RELA':
            for relocation in section.iter_relocations():
                relocations[relocation['r_offset']]=relocation['r_addend']
    registers={}
    for ins in Cs(CS_ARCH_ARM64,CS_MODE_ARM).disasm(code,args.start):
        if ins.address in names:output.append('\n'+names[ins.address])
        note=names.get(int(ins.op_str[1:],16),'') if ins.mnemonic=='bl' else ''
        page=re.fullmatch(r'(x\d+), #(0x[0-9a-f]+)',ins.op_str)
        load=re.fullmatch(r'(x\d+), \[(x\d+)(?:, #(0x[0-9a-f]+))?\]',ins.op_str)
        if ins.mnemonic=='adrp' and page:registers[page[1]]=int(page[2],16)
        elif ins.mnemonic=='ldr' and load:
            address=registers.get(load[2])
            if address is not None:
                address+=int(load[3] or '0',16)
                target=relocations.get(address)
                note=annotations.get(target,annotations.get(address,''))
                if target is not None:registers[load[1]]=target
                else:registers.pop(load[1],None)
            else:registers.pop(load[1],None)
        elif ins.mnemonic=='bl':
            for index in range(19):registers.pop('x'+str(index),None)
        output.append(f'{ins.address:x}: {ins.mnemonic:8} {ins.op_str} {note}')
    args.output.write_text('\n'.join(output),encoding='utf-8')
    print('\n'.join(output))


if __name__=='__main__':main()
