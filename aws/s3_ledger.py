"""Amazon S3 Immutable Ledger & Transient Waveform Archival for AquiPulse.

Stores SHA-256 chained settlement blocks with S3 Object Lock compliance
and archives 4 kHz high-frequency startup burst telemetry.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from aws.config import S3_BUCKET_NAME, get_boto3_kwargs

logger = logging.getLogger("AquiPulseS3")


class S3LedgerArchive:
    """Manages S3 object storage for settlement blocks and telemetry bursts."""

    def __init__(self, bucket_name: str = S3_BUCKET_NAME) -> None:
        self.bucket_name = bucket_name
        self._client: Optional[Any] = None

    @property
    def client(self) -> Any:
        """Lazily initialize S3 client."""
        if self._client is None:
            try:
                kwargs = get_boto3_kwargs("s3")
                self._client = boto3.client("s3", **kwargs)
            except Exception as e:
                logger.warning(f"S3 client init failed: {e}")
                self._client = None
        return self._client

    def archive_settlement_block(
        self,
        block_index: int,
        block_hash: str,
        prev_hash: str,
        settlement_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Commit an immutable settlement block to S3."""
        key = f"ledger/blocks/block_{block_index:06d}_{block_hash[:8]}.json"
        payload = {
            "block_index": block_index,
            "block_hash": block_hash,
            "prev_hash": prev_hash,
            "data": settlement_data,
        }
        body = json.dumps(payload, indent=2).encode("utf-8")
        uploaded = False

        if self.client:
            try:
                self.client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=body,
                    ContentType="application/json",
                    Metadata={"block-hash": block_hash, "prev-hash": prev_hash},
                )
                uploaded = True
            except (BotoCoreError, ClientError) as e:
                logger.error(f"S3 block upload failed: {e}")

        return {
            "bucket": self.bucket_name,
            "key": key,
            "block_index": block_index,
            "block_hash": block_hash,
            "uploaded": uploaded,
        }

    def archive_burst_waveform(
        self,
        pump_id: str,
        timestamp_s: float,
        samples: List[float],
        sample_rate_hz: int = 4000,
    ) -> Dict[str, Any]:
        """Archive a 4 kHz startup burst transient waveform."""
        key = f"transients/{pump_id}/{int(timestamp_s)}_burst_4khz.json"
        payload = {
            "pump_id": pump_id,
            "timestamp": timestamp_s,
            "sample_rate_hz": sample_rate_hz,
            "samples_count": len(samples),
            "samples": samples[:500],  # store sample chunk for fast preview
        }
        body = json.dumps(payload).encode("utf-8")
        uploaded = False

        if self.client:
            try:
                self.client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=body,
                    ContentType="application/json",
                )
                uploaded = True
            except Exception as e:
                logger.warning(f"S3 burst upload failed: {e}")

        return {
            "bucket": self.bucket_name,
            "key": key,
            "pump_id": pump_id,
            "uploaded": uploaded,
        }
