#!/usr/bin/env python3
"""
Deploy Chronos-2 model to Amazon SageMaker for crash prediction.

This script creates a SageMaker endpoint running the Chronos-2 time series
forecasting model. The endpoint accepts JSON payloads with historical crash
time series and returns probabilistic forecasts.

Usage:
    python scripts/deploy_chronos_endpoint.py --action deploy
    python scripts/deploy_chronos_endpoint.py --action status
    python scripts/deploy_chronos_endpoint.py --action delete

Environment Variables (or GitHub Secrets):
    AWS_ACCESS_KEY_ID       - IAM user access key
    AWS_SECRET_ACCESS_KEY   - IAM user secret key
    AWS_REGION              - AWS region (default: us-east-1)
"""

import argparse
import json
import os
import sys
import time

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("ERROR: boto3 is required. Install with: pip install boto3")
    sys.exit(1)

# ============================================================
# Configuration
# ============================================================

ENDPOINT_NAME = "crashlens-chronos2-endpoint"
MODEL_NAME = "crashlens-chronos2-model"
ENDPOINT_CONFIG_NAME = "crashlens-chronos2-config"

# Use CPU instance for cost efficiency (serverless-like usage pattern)
# ml.m5.xlarge: 4 vCPU, 16 GB RAM — sufficient for Chronos-2 (120M params)
INSTANCE_TYPE = "ml.m5.xlarge"
INITIAL_INSTANCE_COUNT = 1

# Chronos-2 model from HuggingFace via SageMaker JumpStart
MODEL_ID = "pytorch-forecasting-chronos-2"

# Timeout settings
DEPLOY_WAIT_MINUTES = 15
POLL_INTERVAL_SECONDS = 30


def get_boto_session():
    """Create boto3 session from environment variables."""
    region = os.environ.get("AWS_REGION", "us-east-1")
    access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")

    if not access_key or not secret_key:
        print("ERROR: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set.")
        print("Set them as environment variables or GitHub repository secrets.")
        sys.exit(1)

    return boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )


def deploy_endpoint(session):
    """Deploy Chronos-2 model to SageMaker endpoint."""
    region = session.region_name
    sm_client = session.client("sagemaker")
    print(f"\n{'='*60}")
    print(f"  Deploying Chronos-2 to SageMaker")
    print(f"  Region: {region}")
    print(f"  Endpoint: {ENDPOINT_NAME}")
    print(f"  Instance: {INSTANCE_TYPE}")
    print(f"{'='*60}\n")

    # Check if endpoint already exists
    try:
        status = sm_client.describe_endpoint(EndpointName=ENDPOINT_NAME)
        current_status = status["EndpointStatus"]
        if current_status == "InService":
            print(f"Endpoint '{ENDPOINT_NAME}' is already InService.")
            print("Use --action delete first if you want to redeploy.")
            return True
        elif current_status in ("Creating", "Updating"):
            print(f"Endpoint is currently {current_status}. Wait for it to finish.")
            return wait_for_endpoint(sm_client)
        else:
            print(f"Endpoint exists with status: {current_status}. Cleaning up...")
            delete_endpoint(session)
            time.sleep(10)
    except ClientError as e:
        if "Could not find endpoint" in str(e):
            print("No existing endpoint found. Creating new one...")
        else:
            raise

    # Try JumpStart deployment first
    try:
        from sagemaker.jumpstart.model import JumpStartModel
        from sagemaker import Session as SageMakerSession

        sm_session = SageMakerSession(boto_session=session)
        print(f"[1/3] Loading JumpStart model: {MODEL_ID}...")

        model = JumpStartModel(
            model_id=MODEL_ID,
            instance_type=INSTANCE_TYPE,
            sagemaker_session=sm_session,
        )

        print(f"[2/3] Deploying to endpoint: {ENDPOINT_NAME}...")
        predictor = model.deploy(
            endpoint_name=ENDPOINT_NAME,
            initial_instance_count=INITIAL_INSTANCE_COUNT,
            wait=False,  # Don't block — we'll poll ourselves
        )

        print(f"[3/3] Deployment initiated. Waiting for InService status...")
        return wait_for_endpoint(sm_client)

    except ImportError as e:
        print(f"WARNING: sagemaker JumpStart SDK not available: {e}")
        print("Ensure sagemaker v2 is installed: pip install \"sagemaker>=2.200,<3\"")
        return deploy_with_boto3(session)
    except Exception as e:
        print(f"JumpStart deployment failed: {e}")
        print("Trying boto3-only deployment as fallback...")
        return deploy_with_boto3(session)


def deploy_with_boto3(session):
    """Fallback deployment using raw boto3 (no SageMaker SDK).

    NOTE: Chronos-2 deployment requires the SageMaker JumpStart SDK (sagemaker v2)
    which automatically resolves container images and model artifacts. The boto3-only
    fallback cannot deploy Chronos-2 because the model artifacts and container URIs
    are managed internally by JumpStart. Install sagemaker v2:
        pip install "sagemaker>=2.200,<3"
    """
    print("ERROR: boto3-only deployment is not supported for Chronos-2.")
    print("Chronos-2 requires the SageMaker JumpStart SDK (sagemaker v2) which")
    print("automatically resolves container images and model artifact locations.")
    print("")
    print("Fix: Install sagemaker SDK v2:")
    print('  pip install "sagemaker>=2.200,<3"')
    print("")
    print("Then re-run with --action deploy.")
    return False


def get_or_create_sagemaker_role(iam_client):
    """Get or create a SageMaker execution role."""
    role_name = "CrashLensSageMakerRole"
    try:
        role = iam_client.get_role(RoleName=role_name)
        print(f"  Using existing role: {role_name}")
        return role["Role"]["Arn"]
    except ClientError:
        pass

    print(f"  Creating IAM role: {role_name}")
    trust_policy = json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "sagemaker.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    })

    role = iam_client.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=trust_policy,
        Description="Execution role for CrashLens Chronos-2 endpoint",
    )

    # Attach required policies
    for policy_arn in [
        "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess",
        "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess",
    ]:
        iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)

    # Wait for role propagation
    time.sleep(10)
    return role["Role"]["Arn"]


def wait_for_endpoint(sm_client):
    """Poll endpoint status until InService or failure."""
    max_polls = (DEPLOY_WAIT_MINUTES * 60) // POLL_INTERVAL_SECONDS
    for i in range(max_polls):
        try:
            resp = sm_client.describe_endpoint(EndpointName=ENDPOINT_NAME)
            status = resp["EndpointStatus"]
            elapsed = (i + 1) * POLL_INTERVAL_SECONDS
            print(f"  [{elapsed}s] Status: {status}")

            if status == "InService":
                print(f"\n  Endpoint is LIVE and ready for predictions!")
                print(f"  Endpoint Name: {ENDPOINT_NAME}")
                return True
            elif status in ("Failed", "RollbackComplete"):
                reason = resp.get("FailureReason", "Unknown")
                print(f"\n  Deployment FAILED: {reason}")
                return False
        except ClientError as e:
            print(f"  Poll error: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)

    print(f"\n  Timed out after {DEPLOY_WAIT_MINUTES} minutes.")
    return False


def check_status(session):
    """Check the current status of the endpoint."""
    sm_client = session.client("sagemaker")
    try:
        resp = sm_client.describe_endpoint(EndpointName=ENDPOINT_NAME)
        status = resp["EndpointStatus"]
        creation = resp.get("CreationTime", "N/A")
        last_mod = resp.get("LastModifiedTime", "N/A")

        print(f"\n{'='*60}")
        print(f"  Endpoint: {ENDPOINT_NAME}")
        print(f"  Status:   {status}")
        print(f"  Created:  {creation}")
        print(f"  Modified: {last_mod}")
        print(f"{'='*60}\n")

        if status == "InService":
            # Test with a minimal payload
            print("Testing endpoint with sample data...")
            runtime = session.client("sagemaker-runtime")
            test_payload = {
                "inputs": [{"target": [100, 110, 105, 115, 108, 120, 112, 125]}],
                "parameters": {
                    "prediction_length": 3,
                    "quantile_levels": [0.1, 0.5, 0.9],
                },
            }
            try:
                response = runtime.invoke_endpoint(
                    EndpointName=ENDPOINT_NAME,
                    ContentType="application/json",
                    Body=json.dumps(test_payload),
                )
                result = json.loads(response["Body"].read().decode("utf-8"))
                print(f"  Test prediction successful!")
                print(f"  Sample output keys: {list(result.get('predictions', {}).keys())}")
            except Exception as e:
                print(f"  Test prediction failed: {e}")

        return status
    except ClientError as e:
        if "Could not find endpoint" in str(e):
            print(f"\nEndpoint '{ENDPOINT_NAME}' does not exist.")
            print("Run with --action deploy to create it.")
            return None
        raise


def delete_endpoint(session):
    """Delete the endpoint, config, and model."""
    sm_client = session.client("sagemaker")

    print(f"\nDeleting endpoint resources...")

    for resource, func, name in [
        ("Endpoint", sm_client.delete_endpoint, ENDPOINT_NAME),
        ("Config", sm_client.delete_endpoint_config, ENDPOINT_CONFIG_NAME),
        ("Model", sm_client.delete_model, MODEL_NAME),
    ]:
        try:
            if resource == "Endpoint":
                func(EndpointName=name)
            elif resource == "Config":
                func(EndpointConfigName=name)
            else:
                func(ModelName=name)
            print(f"  Deleted {resource}: {name}")
        except ClientError as e:
            if "Could not find" in str(e) or "does not exist" in str(e):
                print(f"  {resource} '{name}' not found (already deleted).")
            else:
                print(f"  Error deleting {resource}: {e}")

    print("Cleanup complete.")


def main():
    parser = argparse.ArgumentParser(
        description="Deploy Chronos-2 to SageMaker for crash prediction"
    )
    parser.add_argument(
        "--action",
        choices=["deploy", "status", "delete"],
        required=True,
        help="Action to perform",
    )
    args = parser.parse_args()

    session = get_boto_session()

    if args.action == "deploy":
        success = deploy_endpoint(session)
        sys.exit(0 if success else 1)
    elif args.action == "status":
        check_status(session)
    elif args.action == "delete":
        delete_endpoint(session)


if __name__ == "__main__":
    main()
