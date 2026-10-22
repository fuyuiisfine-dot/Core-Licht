"""Explicit frame profiles. No profile is claimed compatible until observed."""
from dataclasses import dataclass


@dataclass(frozen=True)
class FrameProfile:
    length_bytes: int
    id_bytes: int
    byteorder: str
    length_includes_prefix: bool
    max_frame: int = 1024*1024

    def __post_init__(self):
        if self.length_bytes not in (2,4) or self.id_bytes not in (1,2,4):
            raise ValueError('unsupported field width')
        if self.byteorder not in ('little','big'): raise ValueError('invalid byte order')
        if self.max_frame < self.id_bytes*2: raise ValueError('invalid maximum')

    def encode(self, message_id, payload):
        group, number = map(int, message_id.split('_'))
        body = group.to_bytes(self.id_bytes,self.byteorder)+number.to_bytes(self.id_bytes,self.byteorder)+payload
        if len(body) > self.max_frame: raise ValueError('frame too large')
        length = len(body)+(self.length_bytes if self.length_includes_prefix else 0)
        return length.to_bytes(self.length_bytes,self.byteorder)+body

    def pop(self, buffer):
        if len(buffer) < self.length_bytes: return None
        length = int.from_bytes(buffer[:self.length_bytes],self.byteorder)
        size = length-(self.length_bytes if self.length_includes_prefix else 0)
        if size < self.id_bytes*2 or size > self.max_frame: raise ValueError('invalid frame length')
        total = size+self.length_bytes
        if len(buffer) < total: return None
        body = bytes(buffer[self.length_bytes:total])
        del buffer[:total]
        group = int.from_bytes(body[:self.id_bytes],self.byteorder)
        number = int.from_bytes(body[self.id_bytes:2*self.id_bytes],self.byteorder)
        return f'{group}_{number}',body[2*self.id_bytes:]
