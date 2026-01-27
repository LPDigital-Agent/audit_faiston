#!/usr/bin/env python3
"""
E2E Test: NEXO Import Pipeline - Phase 2→3 Validation
=====================================================
Tests if column_mappings comes through after BUG-028/029 fixes.

This script validates the NEXO Import Pipeline by:
1. Uploading a test CSV via presigned URL (directly to S3)
2. Calling nexo_analyze_file via inventory_hub (triggers Phase 2+3)
3. Validating the response structure

Key Validation Points:
- BUG-028 Check: Does 'column_mappings' key exist?
- BUG-029 Check: Is column_mappings non-empty? (If empty, Phase 3 failed)
- HIL Check: If status='needs_input', are questions present?

Auth: IAM SigV4 (faiston-aio profile) via boto3 - bypasses Cognito JWT
Target: inventory_hub (A2A protocol, IAM auth)

Author: Claude Code E2E Test
Date: January 2026
"""

import json
import logging
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import boto3
import requests
import urllib.parse
from botocore.config import Config
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

# =============================================================================
# Configuration
# =============================================================================

AWS_REGION = "us-east-2"
AWS_ACCOUNT_ID = "377311924364"
AWS_PROFILE = "faiston-aio"
S3_BUCKET = "faiston-one-sga-documents-prod"
S3_PREFIX = "tmp"

# inventory_hub agent (A2A protocol, IAM auth - NOT JWT)
# This is the internal orchestrator that routes to specialists
INVENTORY_HUB_RUNTIME_ID = "faiston_sga_inventory_hub-Rl6ek6Ev3l"
INVENTORY_HUB_ARN = f"arn:aws:bedrock-agentcore:{AWS_REGION}:{AWS_ACCOUNT_ID}:runtime/{INVENTORY_HUB_RUNTIME_ID}"

# Test data - Use real business CSV for realistic testing
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
# Real business file: "SOLICITAÇÕES DE EXPEDIÇÃO.csv" (shipping requests)
TEST_CSV_PATH = REPO_ROOT / "data" / "SOLICITAÇÕES DE EXPEDIÇÃO.csv"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# AWS Clients
# =============================================================================


def get_session():
    """Get boto3 session with correct profile."""
    return boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)


def get_s3_client():
    """Get S3 client with regional config."""
    session = get_session()
    return session.client(
        's3',
        region_name=AWS_REGION,
        config=Config(
            signature_version='s3v4',
            s3={'addressing_style': 'virtual'}
        )
    )


def get_agentcore_client():
    """Get AgentCore client for IAM-authenticated invocations."""
    session = get_session()
    return session.client('bedrock-agentcore', region_name=AWS_REGION)


# =============================================================================
# AgentCore Invocation (using boto3)
# =============================================================================


def invoke_agent(
    client,
    action: str,
    payload: dict,
    session_id: str | None = None
) -> tuple[dict, str]:
    """
    Invokes the agent using the strict Strands A2A JSON-RPC 2.0 protocol.

    Uses HTTP requests with SigV4 signing instead of boto3 client.

    Args:
        client: boto3 session (used for credentials)
        action: Action name (e.g., 'nexo_analyze_file')
        payload: Action payload dict
        session_id: Optional session ID (auto-generated if not provided)

    Returns:
        Tuple of (response_dict, session_id)
    """
    # Session ID for AgentCore (must be >= 33 characters)
    if not session_id:
        session_id = f"e2e-nexo-flow-{uuid.uuid4().hex}"

    # Build URL for AgentCore Runtime invocation
    encoded_arn = urllib.parse.quote(INVENTORY_HUB_ARN, safe='')
    url = f"https://bedrock-agentcore.{AWS_REGION}.amazonaws.com/runtimes/{encoded_arn}/invocations/"

    # 1. Construir o Payload de Negócio (Ação Mode 2.5)
    business_payload = {"action": action, **payload}
    business_payload_str = json.dumps(business_payload)

    # 2. Construir o Envelope de Transporte (A2A JSON-RPC)
    message_id = str(uuid.uuid4())

    rpc_payload = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "id": message_id,
        "params": {
            "message": {
                "role": "user",
                "parts": [
                    {
                        "kind": "text",
                        "text": business_payload_str  # O JSON de ação vai aqui dentro como string
                    }
                ],
                "messageId": message_id,
                "sessionId": session_id
            }
        }
    }

    logger.info(f"  📤 Sending A2A Action: {action}")
    logger.info(f"  [DEBUG] URL: {url}")
    logger.info(f"  [DEBUG] RPC message_id: {message_id}")
    logger.info(f"  [DEBUG] Business payload: {business_payload}")

    # Assinatura AWS SigV4
    session = get_session()
    credentials = session.get_credentials()
    request_body = json.dumps(rpc_payload)

    aws_request = AWSRequest(method="POST", url=url, data=request_body)
    SigV4Auth(credentials, "bedrock-agentcore", AWS_REGION).add_auth(aws_request)

    headers = dict(aws_request.headers)
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "application/json"

    try:
        response = requests.post(url, headers=headers, data=request_body, timeout=120)

        # 3. Tratamento Robusto de Erros HTTP
        logger.info(f"  [DEBUG] HTTP Status: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"  ❌ HTTP Error {response.status_code}: {response.text[:500]}")
            return {"error": f"HTTP {response.status_code}", "success": False, "raw": response.text}, session_id

        # 4. Desembrulhar a Resposta (Unwrapping)
        rpc_response = response.json()
        logger.info(f"  [DEBUG] RPC response keys: {list(rpc_response.keys())}")

        # Verifica erro no nível do protocolo RPC
        if "error" in rpc_response:
            error_msg = rpc_response["error"]
            logger.error(f"  ❌ A2A Protocol Error: {error_msg}")
            return {"error": f"Agent Protocol Error: {error_msg}", "success": False, "rpc_error": error_msg}, session_id

        # Navega a estrutura do Strands: result -> message -> parts -> text
        try:
            rpc_result = rpc_response.get("result", {})

            # Tenta pegar o texto da primeira parte da mensagem
            message = rpc_result.get("message", {})
            parts = message.get("parts", [])

            result_text = ""
            for part in parts:
                if part.get("kind") == "text":
                    result_text += part.get("text", "")

            # Fallback: check artifacts
            if not result_text:
                artifacts = rpc_result.get("artifacts", [])
                for artifact in artifacts:
                    for part in artifact.get("parts", []):
                        if part.get("kind") == "text":
                            result_text = part.get("text", "")
                            break
                    if result_text:
                        break

            # Tenta converter o texto de volta para JSON (Resposta de Negócio)
            if result_text:
                try:
                    business_result = json.loads(result_text)
                    logger.info(f"  ✅ Action {action} success")
                    logger.info(f"  [DEBUG] Business result keys: {list(business_result.keys()) if isinstance(business_result, dict) else type(business_result)}")
                    return business_result, session_id
                except json.JSONDecodeError:
                    # Se o agente respondeu texto natural (ex: erro amigável), retorna envelopado
                    logger.warning(f"  ⚠️ Agent returned raw text (not JSON): {result_text[:100]}...")
                    return {"success": False, "response": result_text, "error": "Agent returned text, expected JSON"}, session_id
            else:
                # Fallback: Procura em artifacts ou outros campos
                logger.warning("  ⚠️ Empty text in response parts. Dumping full RPC result.")
                return {"success": True, "raw_rpc": rpc_result}, session_id

        except (IndexError, AttributeError) as e:
            logger.error(f"  ❌ Failed to parse A2A response structure: {e}")
            logger.debug(f"  Full Response: {rpc_response}")
            return {"error": f"Parse error: {e}", "success": False, "raw_rpc": rpc_response}, session_id

    except requests.exceptions.Timeout:
        logger.error(f"  💥 Request timeout (120s)")
        return {"error": "Request timeout", "success": False}, session_id
    except Exception as e:
        logger.error(f"  💥 Exception invoking agent: {type(e).__name__}: {e}")
        return {"error": str(e), "error_type": type(e).__name__, "success": False}, session_id


# =============================================================================
# E2E Test Steps
# =============================================================================


def step1_upload_file_to_s3(s3_client, file_path: Path) -> str | None:
    """Step 1: Upload test file directly to S3."""
    print("\n" + "=" * 60)
    print("📤 STEP 1: Upload Test File to S3")
    print("=" * 60)

    # Generate unique S3 key
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    s3_key = f"{S3_PREFIX}/e2e_test_{timestamp}_{file_path.name}"

    try:
        with open(file_path, 'rb') as f:
            file_content = f.read()

        file_size = len(file_content)
        logger.info(f"  File size: {file_size:,} bytes")

        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType='text/csv'
        )

        logger.info(f"  ✓ Uploaded to s3://{S3_BUCKET}/{s3_key}")
        return s3_key

    except Exception as e:
        logger.error(f"  ✗ Upload failed: {e}")
        return None


def step2_analyze_file(
    agentcore_client,
    s3_key: str,
    filename: str,
    session_id: str
) -> dict[str, Any]:
    """
    Step 2: Trigger NEXO file analysis (Phase 2 + Phase 3).

    This is the CRITICAL step for BUG-028/029 validation.
    """
    print("\n" + "=" * 60)
    print("🤖 STEP 2: NEXO File Analysis (Phase 2 + Phase 3)")
    print("=" * 60)

    result, _ = invoke_agent(
        agentcore_client,
        'nexo_analyze_file',
        {
            's3_key': s3_key,
            'filename': filename,
        },
        session_id
    )

    return result


def validate_response(result: dict[str, Any]) -> dict[str, Any]:
    """
    Validate response structure for BUG-028 and BUG-029.

    Returns validation report dict.
    """
    print("\n" + "=" * 60)
    print("🔍 VALIDATION: BUG-028/029 Checks")
    print("=" * 60)

    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": {},
        "verdict": None,
        "raw_response": result,
    }

    # Check 0: Error check
    if "error" in result and not result.get("success", True):
        report["checks"]["invocation_success"] = {
            "passed": False,
            "value": result.get("error"),
            "description": "Agent invocation succeeded"
        }
        report["verdict"] = f"FAIL: Agent invocation error - {result.get('error')}"
        print(f"  ✗ Invocation ERROR: {result.get('error')}")
        return report

    # Check 1: Basic success
    success = result.get('success', False)
    report["checks"]["basic_success"] = {
        "passed": success,
        "value": success,
        "description": "Agent returned success=True"
    }
    print(f"  {'✓' if success else '✗'} Basic success: {success}")

    # Check 2: BUG-028 - column_mappings KEY exists
    has_column_mappings_key = 'column_mappings' in result
    report["checks"]["bug028_key_exists"] = {
        "passed": has_column_mappings_key,
        "value": has_column_mappings_key,
        "description": "Response contains 'column_mappings' key (BUG-028 fix)"
    }
    if has_column_mappings_key:
        print(f"  ✓ BUG-028 CHECK PASSED: 'column_mappings' key EXISTS")
    else:
        print(f"  ✗ BUG-028 CHECK FAILED: 'column_mappings' key MISSING")
        print(f"    Available keys: {list(result.keys())}")

    # Check 3: BUG-029 - column_mappings is non-empty
    column_mappings = result.get('column_mappings', None)
    mappings_non_empty = bool(column_mappings)
    report["checks"]["bug029_mappings_populated"] = {
        "passed": mappings_non_empty,
        "value": len(column_mappings) if isinstance(column_mappings, list) else None,
        "description": "column_mappings has actual mappings (Phase 3 succeeded)"
    }
    if column_mappings:
        print(f"  ✓ BUG-029 CHECK PASSED: column_mappings has {len(column_mappings)} entries")
        for m in column_mappings[:3]:
            src = m.get('source_column') or m.get('file_column') or '?'
            tgt = m.get('target_column') or m.get('target_field') or '?'
            conf = m.get('confidence', 0)
            if isinstance(conf, (int, float)):
                print(f"    - {src} → {tgt} (confidence: {conf:.0%})")
            else:
                print(f"    - {src} → {tgt}")
    elif column_mappings == []:
        print(f"  ⚠️ BUG-029 CHECK WARNING: column_mappings is EMPTY []")
        print(f"    This means Phase 3 (SchemaMapper) likely FAILED")
    else:
        print(f"  ✗ BUG-029 CHECK: column_mappings is {type(column_mappings).__name__}: {column_mappings}")

    # Check 4: Phase 3 status
    phase3_status = result.get('phase3_status')
    report["checks"]["phase3_status"] = {
        "passed": phase3_status in ('success', 'needs_input'),
        "value": phase3_status,
        "description": "Phase 3 executed (status is 'success' or 'needs_input')"
    }
    if phase3_status:
        print(f"  → Phase 3 status: {phase3_status}")
    else:
        print(f"  ⚠️ Phase 3 status not present in response")

    # Check 5: Questions for HIL
    questions = result.get('questions', [])
    report["checks"]["questions_present"] = {
        "passed": True,  # Questions are optional
        "value": len(questions),
        "description": "HIL questions for user confirmation"
    }
    if questions:
        print(f"  → HIL Questions: {len(questions)}")
        for q in questions[:2]:
            q_text = q.get('question_text') or q.get('question') or '?'
            print(f"    - {q_text[:60]}...")

    # Check 6: Overall confidence
    confidence = result.get('overall_confidence') or result.get('mapping_confidence')
    report["checks"]["confidence"] = {
        "passed": confidence is not None,
        "value": confidence,
        "description": "Mapping confidence score"
    }
    if confidence is not None:
        if isinstance(confidence, (int, float)):
            print(f"  → Confidence: {confidence:.1%}")
        else:
            print(f"  → Confidence: {confidence}")

    # Check 7: Errors
    phase3_error = result.get('phase3_error')
    if phase3_error:
        report["checks"]["phase3_error"] = {
            "passed": False,
            "value": phase3_error,
            "description": "Phase 3 returned an error"
        }
        print(f"  ✗ Phase 3 ERROR: {phase3_error}")

    # Determine overall verdict
    if not has_column_mappings_key:
        report["verdict"] = "FAIL: BUG-028 not fixed - column_mappings key missing"
    elif not mappings_non_empty:
        report["verdict"] = "PARTIAL: BUG-028 fixed (key exists), but BUG-029 likely present (mappings empty - Phase 3 failed)"
    else:
        report["verdict"] = "SUCCESS: Both BUG-028 and BUG-029 appear to be fixed"

    print("\n" + "-" * 60)
    print(f"📋 VERDICT: {report['verdict']}")
    print("-" * 60)

    return report


# =============================================================================
# Main
# =============================================================================


def main():
    print("\n" + "=" * 70)
    print("🚀 E2E TEST: NEXO Import Pipeline - Phase 2→3 Validation")
    print("=" * 70)
    print(f"Purpose: Validate BUG-028 and BUG-029 fixes")
    print(f"Test CSV: {TEST_CSV_PATH}")
    print(f"Target Agent: inventory_hub ({INVENTORY_HUB_RUNTIME_ID})")
    print(f"AWS Profile: {AWS_PROFILE}")
    print(f"Auth: IAM (boto3) - bypasses Cognito JWT")
    print()

    # Check test file exists
    if not TEST_CSV_PATH.exists():
        print(f"❌ Test file not found: {TEST_CSV_PATH}")
        sys.exit(1)

    # Count lines in CSV
    with open(TEST_CSV_PATH, 'r', encoding='utf-8') as f:
        line_count = sum(1 for _ in f) - 1  # Subtract header
    print(f"CSV lines (excluding header): {line_count:,}")

    errors = []
    session_id = f"e2e-nexo-flow-{uuid.uuid4().hex}"

    try:
        # Get clients
        s3_client = get_s3_client()
        agentcore_client = get_agentcore_client()

        # Step 1: Upload file directly to S3
        s3_key = step1_upload_file_to_s3(s3_client, TEST_CSV_PATH)

        if not s3_key:
            errors.append("Step 1 FAILED: Could not upload file to S3")
            raise Exception("Step 1 failed")

        # Step 2: Analyze file (triggers Phase 2 + Phase 3)
        analysis_result = step2_analyze_file(
            agentcore_client,
            s3_key,
            TEST_CSV_PATH.name,
            session_id
        )

        # Print full response for debugging
        print("\n" + "=" * 60)
        print("📄 FULL RESPONSE (for debugging)")
        print("=" * 60)
        print(json.dumps(analysis_result, indent=2, default=str))

        # Validate response
        validation_report = validate_response(analysis_result)

        # Summary
        print("\n" + "=" * 70)
        print("📊 E2E TEST SUMMARY")
        print("=" * 70)

        print(f"\n🔑 Session ID: {session_id}")
        print(f"📁 S3 Key: {s3_key}")
        print(f"\n{validation_report['verdict']}")

        # Check results
        checks = validation_report["checks"]
        passed = sum(1 for c in checks.values() if c.get("passed"))
        total = len(checks)
        print(f"\nChecks passed: {passed}/{total}")

        for name, check in checks.items():
            status = "✓" if check["passed"] else "✗"
            print(f"  {status} {name}: {check['value']}")

        print("\n" + "=" * 70)

        # Return exit code based on critical checks
        if "FAIL: BUG-028" in validation_report["verdict"]:
            return 2  # BUG-028 not fixed
        elif "BUG-029" in validation_report["verdict"]:
            return 1  # BUG-028 fixed, BUG-029 present
        else:
            return 0  # All good

    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()

        if errors:
            print("\n📋 Accumulated errors:")
            for err in errors:
                print(f"  - {err}")

        return 99  # General error


if __name__ == '__main__':
    exit_code = main()
    print(f"\n🏁 Exit code: {exit_code}")
    sys.exit(exit_code)
