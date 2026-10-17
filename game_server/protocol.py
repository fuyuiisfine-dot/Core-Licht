import json
from pathlib import Path
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory, json_format


class Protocol:
    def __init__(self, directory=Path('analysis')):
        directory = Path(directory)
        self.directory=directory.resolve()
        self.ids = json.loads((directory/'message_ids.json').read_text())
        descriptors = descriptor_pb2.FileDescriptorSet.FromString((directory/'protocol.desc').read_bytes())
        active = set(json.loads((directory/'active_protocol_files.json').read_text()))
        self.pool = descriptor_pool.DescriptorPool()
        # Five shipped descriptors are absent from ProtoMap.pbs and reference
        # missing types. Load only the same files enabled by the client.
        self.files = {f.name for f in descriptors.file if f.name in active}
        self.inactive_files = {f.name for f in descriptors.file if f.name not in active}
        pending = {f.name:f for f in descriptors.file if f.name in active}
        loaded = set()
        while pending:
            ready = [f for f in pending.values() if set(f.dependency)<=loaded]
            if not ready:raise ValueError('unresolved descriptor dependencies')
            for file in ready:
                self.pool.Add(file)
                loaded.add(file.name)
                del pending[file.name]
        for mapping in self.ids.values():
            for name in mapping.values(): self.pool.FindMessageTypeByName(name)

    def make(self, direction, message_id, values=None):
        name = self.ids[direction][message_id]
        message = message_factory.GetMessageClass(self.pool.FindMessageTypeByName(name))()
        if values is not None: json_format.ParseDict(values, message)
        return message

    def decode(self, direction, message_id, payload):
        message = self.make(direction, message_id)
        message.ParseFromString(payload)
        if not message.IsInitialized():
            raise ValueError('missing required fields: ' + ', '.join(message.FindInitializationErrors()))
        return message

    def encode(self, direction, message_id, values):
        return self.make(direction, message_id, values).SerializeToString()
