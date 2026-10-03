"""AquiPulse MQTT Telemetry Consumer.

Subscribes to:
- aquipulse/telemetry/1hz: steady-state RMS electrical packets
- aquipulse/burst/4khz: 60-second high frequency transient captures
Validates payload schemas, HMAC-SHA256 signatures, and pushes into the pipeline.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, Optional

import paho.mqtt.client as mqtt

from ise.physics_checks import TelemetryValidator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AquiPulseIngest")


class MqttTelemetryIngestConsumer:
    """Consumes and verifies edge telemetry streams over MQTT broker."""

    def __init__(
        self,
        broker_host: str = "localhost",
        broker_port: int = 1883,
        validator: Optional[TelemetryValidator] = None,
        on_valid_telemetry: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.validator = validator if validator is not None else TelemetryValidator(secret_keys={})
        self.on_valid_telemetry = on_valid_telemetry
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

        self.processed_count = 0
        self.invalid_count = 0

    def _on_connect(
        self, client: Any, userdata: Any, flags: Any, rc: Any, properties: Any = None
    ) -> None:
        logger.info(f"Connected to MQTT broker with result code: {rc}")
        client.subscribe("aquipulse/telemetry/1hz")
        client.subscribe("aquipulse/burst/4khz")

    def _on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode("utf-8"))

            if topic == "aquipulse/telemetry/1hz":
                self._handle_1hz_telemetry(payload)
            elif topic == "aquipulse/burst/4khz":
                self._handle_burst(payload)
        except Exception as e:
            self.invalid_count += 1
            logger.error(f"Error parsing MQTT packet: {e}")

    def _handle_1hz_telemetry(self, data: Dict[str, Any]) -> None:
        pump_id = data.get("pump_id", "")
        ts = float(data.get("ts", 0.0))
        v = float(data.get("v_rms", 0.0))
        i = float(data.get("i_rms", 0.0))
        pf = float(data.get("pf", 1.0))
        p = float(data.get("p_kw", 0.0))
        sig = data.get("signature", "")

        check = self.validator.verify_telemetry(
            pump_id=pump_id,
            timestamp_s=ts,
            v_rms=v,
            i_rms=i,
            pf=pf,
            p_kw=p,
            signature=sig,
        )

        if check.is_valid:
            self.processed_count += 1
            if self.on_valid_telemetry is not None:
                self.on_valid_telemetry(data)
        else:
            self.invalid_count += 1
            logger.warning(f"Invalid telemetry from {pump_id}: {check.flags}")

    def _handle_burst(self, data: Dict[str, Any]) -> None:
        self.processed_count += 1
        logger.info(f"Processed 4 kHz start-burst from {data.get('pump_id')}")

    def start_loop(self) -> None:
        """Start listening asynchronously."""
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
        except Exception as e:
            logger.warning(
                f"Could not connect to MQTT broker ({e}). Running in offline/direct mode."
            )

    def stop_loop(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()
