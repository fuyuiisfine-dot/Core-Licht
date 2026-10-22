"""SNPacketData wire format reconstructed from APK ARM64 implementation.

Evidence: analysis/packet_disassembly.txt, buffer_packet.txt, buffer_uint16.txt.
This codec still requires observation against the real client.
"""
import zlib
from pathlib import Path


class SNPacket:
    def __init__(self, table=Path('analysis/packet_xor_table.bin'),expect_preface=False):
        self.table = Path(table).read_bytes()
        if len(self.table) != 256: raise ValueError('XOR table must have 256 bytes')
        self.expect_preface=expect_preface

    def xor(self, payload, start):
        return bytes(value ^ self.table[(start+i)&255] for i,value in enumerate(payload))

    @staticmethod
    def frame(body):
        return len(body).to_bytes(2,'big')+body

    @staticmethod
    def pop_body(buffer,minimum):
        if len(buffer)<2: return None
        size=int.from_bytes(buffer[:2],'big')
        if size<minimum: raise ValueError('invalid SNPacket size')
        if len(buffer)<size+2: return None
        body=bytes(buffer[2:size+2])
        del buffer[:size+2]
        return body

    def pop(self, buffer):
        if self.expect_preface:
            if len(buffer)<2:return None
            if buffer[:2]!=b'\x01\x02':raise ValueError('invalid SN connection preface')
            del buffer[:2]
            self.expect_preface=False
        body=self.pop_body(buffer,4)
        if body is None: return None
        unique=int.from_bytes(body[:2],'big')
        section,method=body[2:4]
        return f'{section}_{method}',self.xor(body[4:],unique&255)

    def encode(self,message_id,payload):
        section,method=map(int,message_id.split('_'))
        # Server may leave compression disabled; client tests flag != 0.
        return self.frame(bytes((section,method,0))+self.xor(payload,((section<<4)+method)&255))

    def encode_c2s(self,message_id,payload,unique):
        section,method=map(int,message_id.split('_'))
        return self.frame(unique.to_bytes(2,'big')+bytes((section,method))+self.xor(payload,unique&255))

    def pop_s2c(self,buffer):
        body=self.pop_body(buffer,3)
        if body is None:return None
        section,method,compressed=body[:3]
        payload=self.xor(body[3:],((section<<4)+method)&255)
        if compressed:
            decompressor=zlib.decompressobj()
            payload=decompressor.decompress(payload,1024*1024+1)
            if len(payload)>1024*1024 or not decompressor.eof:raise ValueError('invalid/oversized compressed body')
        return f'{section}_{method}',payload
