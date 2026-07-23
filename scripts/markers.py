from __future__ import annotations
import uuid
from dataclasses import dataclass
from typing import Optional
from pylsl import StreamInfo, StreamOutlet, local_clock

@dataclass
class MarkerOutlet:
    outlet: StreamOutlet
    name: str
    source_id: str

    def send(self, marker: str) -> float:
        ts = local_clock()
        self.outlet.push_sample([marker], ts)
        return ts

def create_marker_outlet(name: str = "Markers", stream_type: str = "Markers",
                         source_id: Optional[str] = None) -> MarkerOutlet:
    sid = source_id or f"{name}-{uuid.uuid4()}"
    info = StreamInfo(name=name, type=stream_type, channel_count=1,
                      nominal_srate=0.0, channel_format="string", source_id=sid)
    return MarkerOutlet(StreamOutlet(info), name, sid)
