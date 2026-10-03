"""Unit and integration tests for ESP-IDF firmware stub and host-side harness."""

from firmware.host_stub import HostFirmwareNode, HostRingBuffer, HostTelemetryPacket


def test_firmware_binary_packing_roundtrip():
    """Verify binary serialization and deserialization of 1 Hz telemetry packet."""
    sig = b"\xaa" * 32
    pkt = HostTelemetryPacket(
        pump_id="PUMP-FIRMWARE-01",
        timestamp_ms=1700000000123,
        v_rms=412.5,
        i_rms=8.45,
        pf=0.835,
        p_kw=4.125,
        freq_hz=49.95,
        signature_bytes=sig,
    )

    packed = pkt.pack()
    assert len(packed) == 92, f"Expected 92 bytes, got {len(packed)}"

    unpacked = HostTelemetryPacket.unpack(packed)
    assert unpacked.pump_id == "PUMP-FIRMWARE-01"
    assert unpacked.timestamp_ms == 1700000000123
    assert abs(unpacked.v_rms - 412.5) < 0.01
    assert abs(unpacked.i_rms - 8.45) < 0.01
    assert abs(unpacked.pf - 0.835) < 0.001
    assert abs(unpacked.p_kw - 4.125) < 0.001
    assert abs(unpacked.freq_hz - 49.95) < 0.01
    assert unpacked.signature_bytes == sig


def test_firmware_ring_buffer_fifo_and_overwrite():
    """Verify circular flash ring buffer overwrites oldest records when full."""
    rb = HostRingBuffer(capacity=5)

    packets = []
    for i in range(10):
        p = HostTelemetryPacket(
            pump_id=f"PUMP-{i}",
            timestamp_ms=1000 + i,
            v_rms=415.0,
            i_rms=5.0,
            pf=0.8,
            p_kw=3.0,
            freq_hz=50.0,
            signature_bytes=b"\x00" * 32,
        )
        rb.push(p)
        packets.append(p)

    assert rb.count() == 5

    # Should pop packets 5, 6, 7, 8, 9 (oldest 0..4 overwritten)
    first_popped = rb.pop()
    assert first_popped is not None
    assert first_popped.pump_id == "PUMP-5"


def test_firmware_with_recorded_waveform():
    """Simulate streaming recorded pump start waveform into firmware node."""
    key = b"secret_firmware_test_key_1234567"
    node = HostFirmwareNode("PUMP-WAVE-01", secret_key=key)

    # 1. Idle state (0 Amps)
    idle_pkt = node.process_second(1000, v=415.0, i=0.0, pf=1.0, p=0.0)
    assert idle_pkt.i_rms == 0.0

    # 2. Pump starts: current steps to 8.2 A
    assert node.detect_start_burst_trigger(current_rms=8.2) is True

    # 3. Steady pumping
    for s in range(10):
        pkt = node.process_second(2000 + s * 1000, v=410.0, i=8.1, pf=0.84, p=4.2)
        assert len(pkt.signature_bytes) == 32

    assert node.ring_buffer.count() == 11
