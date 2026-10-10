"""AWS IoT Core Integration & Message Routing Bridge for AquiPulse.

Routes 1 Hz electrical telemetry packets and 4 kHz startup bursts from edge Node G units
through AWS IoT Core topic rules to AWS Lambda, Amazon Timestream, and S3.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from aws.config import AWS_REGION, get_boto3_kwargs
from ise.physics_checks import TelemetryValidator

logger = logging.getLogger("AquiPulseAWSIoT")


class AwsIotBridge:
    """Manages AWS IoT Core publishing, topic routing, and Device Shadow state."""

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        validator: Optional[TelemetryValidator] = None,
    ) -> None:
        kwargs = get_boto3_kwargs("iot-data")
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        self._kwargs = kwargs
        self._validator = validator or TelemetryValidator(secret_keys={})
        self._client: Optional[Any] = None

    @property
    def client(self) -> Any:
        """Lazily initialize boto3 iot-data client."""
        if self._client is None:
            try:
                self._client = boto3.client("iot-data", **self._kwargs)
            except Exception as e:
                logger.warning(f"Could not connect to live AWS IoT Data endpoint: {e}")
                self._client = None
        return self._client

    @staticmethod
    def format_telemetry_topic(feeder_id: str, pump_id: str) -> str:
        """Standard AWS IoT Core topic for 1 Hz pump electrical telemetry."""
        return f"aquipulse/feeder/{feeder_id}/well/{pump_id}/telemetry"

    @staticmethod
    def format_burst_topic(feeder_id: str, pump_id: str) -> str:
        """Standard AWS IoT Core topic for 4 kHz startup burst transient."""
        return f"aquipulse/feeder/{feeder_id}/well/{pump_id}/burst"

    @staticmethod
    def format_shadow_topic(pump_id: str) -> str:
        """Standard AWS IoT Device Shadow update topic."""
        return f"$aws/things/{pump_id}/shadow/update"

    def publish_telemetry(
        self,
        feeder_id: str,
        pump_id: str,
        v_rms: float,
        i_rms: float,
        pf: float,
        p_kw: float,
        freq_hz: float = 50.0,
        signature: str = "",
        timestamp_s: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Validate and publish a 1 Hz electrical telemetry packet to AWS IoT Core."""
        ts = timestamp_s or time.time()
        topic = self.format_telemetry_topic(feeder_id, pump_id)

        # Validate physics integrity before publishing
        check = self._validator.verify_telemetry(
            pump_id=pump_id,
            timestamp_s=ts,
            v_rms=v_rms,
            i_rms=i_rms,
            pf=pf,
            p_kw=p_kw,
            signature=signature,
        )

        payload = {
            "pump_id": pump_id,
            "feeder_id": feeder_id,
            "ts": ts,
            "v_rms": round(v_rms, 2),
            "i_rms": round(i_rms, 2),
            "pf": round(pf, 3),
            "p_kw": round(p_kw, 3),
            "freq_hz": round(freq_hz, 2),
            "signature": signature,
            "validation": {
                "is_valid": check.is_valid,
                "flags": check.flags,
            },
        }

        published = False
        if check.is_valid and self.client:
            try:
                self.client.publish(
                    topic=topic,
                    qos=1,
                    payload=json.dumps(payload).encode("utf-8"),
                )
                published = True
            except (BotoCoreError, ClientError) as e:
                logger.error(f"AWS IoT publish failed: {e}")

        return {
            "topic": topic,
            "published": published,
            "payload": payload,
            "valid": check.is_valid,
            "flags": check.flags,
        }

    def update_device_shadow(
        self,
        pump_id: str,
        flow_lps: float,
        dynamic_head_m: float,
        static_depth_m: float,
        is_running: bool,
        cone_stress: str = "Normal",
    ) -> Dict[str, Any]:
        """Update AWS IoT Device Shadow with latest inferred state."""
        shadow_payload = {
            "state": {
                "reported": {
                    "pump_id": pump_id,
                    "flow_lps": round(flow_lps, 2),
                    "dynamic_head_m": round(dynamic_head_m, 2),
                    "static_depth_m": round(static_depth_m, 2),
                    "is_running": is_running,
                    "cone_stress": cone_stress,
                    "last_updated": int(time.time()),
                }
            }
        }
        topic = self.format_shadow_topic(pump_id)
        published = False

        if self.client:
            try:
                self.client.publish(
                    topic=topic,
                    qos=1,
                    payload=json.dumps(shadow_payload).encode("utf-8"),
                )
                published = True
            except Exception as e:
                logger.warning(f"Failed to update shadow on AWS IoT Core: {e}")

        return {
            "topic": topic,
            "published": published,
            "shadow": shadow_payload,
        }
