"""AWS Configuration & Client Factory for AquiPulse.

Designed for AWS Free Tier deployment in ap-south-1 (Mumbai, India)
with seamless LocalStack fallback for offline local testing.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

# AWS Region (Default to AWS Mumbai - ap-south-1 for Bharat Builds Tour)
AWS_REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "ap-south-1"))

# Resource Identifiers
S3_BUCKET_NAME = os.getenv("AQUIPULSE_S3_BUCKET", "aquipulse-groundwater-telemetry-prod")
DYNAMODB_PUMP_TABLE = os.getenv("AQUIPULSE_DYNAMO_TABLE", "AquiPulsePumpRegistry")
TIMESTREAM_DATABASE = os.getenv("AQUIPULSE_TIMESTREAM_DB", "AquiPulseTelemetryDB")
TIMESTREAM_TABLE = os.getenv("AQUIPULSE_TIMESTREAM_TABLE", "PumpElectrical1Hz")
SNS_ALERTS_TOPIC_ARN = os.getenv("AQUIPULSE_SNS_TOPIC_ARN", "arn:aws:sns:ap-south-1:123456789012:AquiPulseAquiferAlerts")
BEDROCK_MODEL_ID = os.getenv("AQUIPULSE_BEDROCK_MODEL", "anthropic.claude-3-5-sonnet-20241022-v2:0")

# LocalStack endpoint (if set, directs boto3 to LocalStack for 100% free offline dev)
LOCALSTACK_ENDPOINT = os.getenv("LOCALSTACK_ENDPOINT", os.getenv("AWS_ENDPOINT_URL", ""))


def get_boto3_kwargs(service_name: str) -> Dict[str, Any]:
    """Return kwargs for boto3 client creation, enabling LocalStack if specified."""
    kwargs: Dict[str, Any] = {"region_name": AWS_REGION}
    endpoint = LOCALSTACK_ENDPOINT
    if endpoint:
        kwargs["endpoint_url"] = endpoint
        kwargs["aws_access_key_id"] = os.getenv("AWS_ACCESS_KEY_ID", "test")
        kwargs["aws_secret_access_key"] = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
    return kwargs


def is_localstack_mode() -> bool:
    """Return True if currently pointed at LocalStack."""
    return bool(LOCALSTACK_ENDPOINT)


def get_aws_status() -> Dict[str, Any]:
    """Return a diagnostic snapshot of current AWS connectivity configuration."""
    return {
        "region": AWS_REGION,
        "localstack_mode": is_localstack_mode(),
        "localstack_endpoint": LOCALSTACK_ENDPOINT or None,
        "s3_bucket": S3_BUCKET_NAME,
        "dynamodb_table": DYNAMODB_PUMP_TABLE,
        "timestream_db": TIMESTREAM_DATABASE,
        "bedrock_model": BEDROCK_MODEL_ID,
        "status": "Configured for AWS Bharat Builds Tour (Track 02: Heat & Water)",
    }
