#!/usr/bin/env bash
# AquiPulse LocalStack Initializer
# Automatically initializes S3, DynamoDB, SNS, and IoT resources for offline local execution.

set -euo pipefail

echo "=========================================================="
echo "Initializing AquiPulse AWS LocalStack Resources (ap-south-1)"
echo "=========================================================="

REGION="ap-south-1"
ENDPOINT="http://localhost:4566"

export AWS_ACCESS_KEY_ID="test"
export AWS_SECRET_ACCESS_KEY="test"
export AWS_DEFAULT_REGION="$REGION"

# 1. Create S3 Bucket for bursts and immutable ledger
echo "Creating S3 Bucket: aquipulse-groundwater-telemetry-prod..."
aws --endpoint-url="$ENDPOINT" s3api create-bucket \
    --bucket aquipulse-groundwater-telemetry-prod \
    --region "$REGION" \
    --create-bucket-configuration LocationConstraint="$REGION" || true

# 2. Create DynamoDB Table for Pump Registry and telemetry state
echo "Creating DynamoDB Table: AquiPulsePumpRegistry..."
aws --endpoint-url="$ENDPOINT" dynamodb create-table \
    --table-name AquiPulsePumpRegistry \
    --attribute-definitions \
        AttributeName=pump_id,AttributeType=S \
        AttributeName=timestamp,AttributeType=N \
    --key-schema \
        AttributeName=pump_id,KeyType=HASH \
        AttributeName=timestamp,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --region "$REGION" || true

# 3. Create SNS Alerts Topic for Critical Cone Dewatering
echo "Creating SNS Alerts Topic: AquiPulseAquiferAlerts..."
aws --endpoint-url="$ENDPOINT" sns create-topic \
    --name AquiPulseAquiferAlerts \
    --region "$REGION" || true

echo "=========================================================="
echo "AquiPulse LocalStack AWS environment ready for testing!"
echo "=========================================================="
