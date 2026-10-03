"""AquiPulse Host-Side Python Stub for Edge Node Firmware Testing.

Emulates the C firmware structs, circular ring buffer, 4 kHz burst packaging,
and cryptographic signing for host-side verification with recorded waveforms.
"""

from __future__ import annotations

import hashlib
import hmac
import struct
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional


@dataclass
class HostTelemetryPacket:
    pump_id: str
    timestamp_ms: int
    v_rms: float
    i_rms: float
    pf: float
    p_kw: float
    freq_hz: float
    signature_bytes: bytes

    def pack(self) -> bytes:
        """Pack telemetry into 64-byte binary frame."""
        p_id_bytes = self.pump_id.encode("utf-8")[:32].ljust(32, b"\x00")
        header = struct.pack(
            "<32sQfffff",
            p_id_bytes,
            self.timestamp_ms,
            self.v_rms,
            self.i_rms,
            self.pf,
            self.p_kw,
            self.freq_hz,
        )
        return header + self.signature_bytes[:32].ljust(32, b"\x00")

    @classmethod
    def unpack(cls, raw: bytes) -> HostTelemetryPacket:
        """Unpack 64-byte binary frame."""
        p_id_bytes, ts, v, i, pf, p, f = struct.unpack("<32sQfffff", raw[:60])
        sig = raw[60:92]
        pump_id = p_id_bytes.rstrip(b"\x00").decode("utf-8")
        return cls(
            pump_id=pump_id,
            timestamp_ms=ts,
            v_rms=v,
            i_rms=i,
            pf=pf,
            p_kw=p,
            freq_hz=f,
            signature_bytes=sig,
        )


class HostRingBuffer:
    """Emulates ESP-IDF flash circular ring buffer (FIFO with overwrite)."""

    def __init__(self, capacity: int = 2048) -> None:
        self.capacity = capacity
        self.buffer: Deque[HostTelemetryPacket] = deque(maxlen=capacity)

    def push(self, packet: HostTelemetryPacket) -> bool:
        self.buffer.append(packet)
        return True

    def pop(self) -> Optional[HostTelemetryPacket]:
        if not self.buffer:
            return None
        return self.buffer.popleft()

    def count(self) -> int:
        return len(self.buffer)


class HostFirmwareNode:
    """Host-side firmware testing controller."""

    def __init__(self, pump_id: str, secret_key: bytes) -> None:
        self.pump_id = pump_id
        self.secret_key = secret_key
        self.ring_buffer = HostRingBuffer(capacity=500)
        self.last_current_rms = 0.0

    def sign_telemetry(
        self, ts_ms: int, v: float, i: float, pf: float, p: float, f: float
    ) -> bytes:
        payload = f"{self.pump_id}:{ts_ms}:{v:.2f}:{i:.2f}:{pf:.3f}:{p:.3f}:{f:.2f}".encode("utf-8")
        return hmac.new(self.secret_key, payload, hashlib.sha256).digest()

    def process_second(
        self, ts_ms: int, v: float, i: float, pf: float, p: float, f: float = 50.0
    ) -> HostTelemetryPacket:
        sig = self.sign_telemetry(ts_ms, v, i, pf, p, f)
        pkt = HostTelemetryPacket(
            pump_id=self.pump_id,
            timestamp_ms=ts_ms,
            v_rms=round(v, 2),
            i_rms=round(i, 2),
            pf=round(pf, 3),
            p_kw=round(p, 3),
            freq_hz=round(f, 2),
            signature_bytes=sig,
        )
        self.ring_buffer.push(pkt)
        self.last_current_rms = i
        return pkt

    def detect_start_burst_trigger(self, current_rms: float, threshold_ratio: float = 2.5) -> bool:
        prev = self.last_current_rms
        if prev < 0.5 and current_rms >= 1.5:
            return True
        if prev > 0.0 and (current_rms / prev) >= threshold_ratio:
            return True
        return False
