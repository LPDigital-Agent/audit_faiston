# =============================================================================
# VisionAnalyzer A2A Agent - Strands A2AServer Entry Point
# =============================================================================
# BUG-025 FIX: Specialist agent for vision/document analysis with Pydantic
# structured output.
#
# Architecture:
# - Uses Strands Agent with GeminiModel (Gemini 2.5 Pro + Thinking)
# - A2A Protocol for inter-agent communication
# - Pydantic schemas for structured output enforcement
# - Tools for S3 document loading and vision analysis (Python = Hands)
#
# Reference:
# - https://strandsagents.com/latest/
# - https://strandsagents.com/latest/documentation/docs/user-guide/concepts/structured-output/
# =============================================================================

import os
import sys
import logging
import json
import time
from typing import Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from strands import Agent, tool
from strands.multiagent.a2a import A2AServer
from fastapi import FastAPI, Request
import uvicorn

# A2A Protocol Types for Agent Card Discovery (100% A2A Architecture)
from a2a.types import AgentSkill

# Centralized model configuration (MANDATORY - Gemini 2.5 Pro + Thinking)
from agents.utils import AGENT_VERSION, create_gemini_model

# BUG-027 FIX: Import hooks for error enrichment
from shared.hooks import LoggingHook, MetricsHook, DebugHook

# Local imports (ABSOLUTE - required for AgentCore direct execution)
# BUG-028 FIX: Relative imports fail when AgentCore runs main.py directly
from agents.specialists.vision_analyzer.schemas import VisionAnalysisResponse
from agents.specialists.vision_analyzer.prompts import get_system_prompt, build_analysis_request
from agents.specialists.vision_analyzer.tools.image_processor import (
    load_document_from_s3,
    prepare_for_vision_api,
    is_pdf,
)
from agents.specialists.vision_analyzer.tools.nf_parser import (
    validate_cnpj,
    validate_access_key,
    parse_brazilian_date,
    parse_brazilian_currency,
)
from shared.debug_utils import debug_error

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

AGENT_ID = "vision_analyzer"
AGENT_NAME = "VisionAnalyzer"
AGENT_DESCRIPTION = """VisionAnalyzer A2A Agent - Maximum Scope Vision Document Analysis.

BUG-025 FIX: This agent provides structured vision/document analysis with Pydantic
enforcement, using Gemini's multimodal capabilities.

Capabilities:
1. ANALYZE: Parse NF-e, tables, equipment photos from S3
2. DETECT: Document type, layout, and content structure
3. EXTRACT: OCR text, table data, NF-e fields with validation
4. VALIDATE: CNPJ, access key, Brazilian date/currency formats
5. CLASSIFY: Document confidence and recommended actions

Follows CLAUDE.md principles:
- LLM = Brain (vision reasoning, OCR, document understanding)
- Python = Hands (S3 I/O, validation, format parsing)
"""

# Default S3 bucket
DEFAULT_BUCKET = "faiston-one-sga-documents-prod"

# =============================================================================
# A2A Agent Skills (100% A2A Architecture - Agent Card Discovery)
# =============================================================================

AGENT_SKILLS = [
    AgentSkill(
        id="analyze_document",
        name="Analyze Document",
        description="Analyze document images from S3 (NF-e, tables, equipment photos) "
                    "and extract structured data with confidence scoring.",
        tags=["vision_analyzer", "ocr", "document", "nf-e"],
    ),
    AgentSkill(
        id="validate_nf_data",
        name="Validate NF Data",
        description="Validate extracted NF-e fields (CNPJ, access key, dates, values) "
                    "using Brazilian fiscal rules.",
        tags=["vision_analyzer", "validation", "nf-e", "fiscal"],
    ),
    AgentSkill(
        id="health_check",
        name="Health Check",
        description="Health check endpoint returning agent status and version.",
        tags=["vision_analyzer", "monitoring", "health"],
    ),
]

# =============================================================================
# System Prompt
# =============================================================================

SYSTEM_PROMPT = get_system_prompt("universal")

# =============================================================================
# Tools (Strands @tool decorator)
# =============================================================================


@tool
def analyze_document(
    s3_key: str,
    document_type_hint: str = "unknown",
    bucket: str = DEFAULT_BUCKET,
) -> Dict[str, Any]:
    """
    Analyze a document from S3 and extract structured data.

    This is the primary tool for vision analysis. It loads the document,
    prepares it for the Vision API, and returns analysis results.

    Args:
        s3_key: S3 object key for the document
        document_type_hint: Hint about document type (nf-e, table, equipment_photo, etc.)
        bucket: S3 bucket name (defaults to production bucket)

    Returns:
        Dict with document content prepared for LLM analysis:
        - images: List of base64-encoded images
        - page_count: Number of pages/images
        - file_type: pdf or image
        - metadata: File metadata from S3
    """
    logger.info(f"[{AGENT_NAME}] Analyzing document from S3: {s3_key}")

    try:
        # Load document from S3
        content, metadata = load_document_from_s3(s3_key, bucket)

        # Determine file type
        file_type = "pdf" if is_pdf(content) else "image"
        if file_type == "pdf" and len(content) > 1000000:  # > 1MB PDF
            file_type = "multi-page-pdf"

        # Prepare images for Vision API
        images = prepare_for_vision_api(content, s3_key)

        logger.info(
            f"[{AGENT_NAME}] Document prepared: {s3_key} ({file_type}, {len(images)} images)"
        )

        return {
            "success": True,
            "images": images,
            "page_count": len(images),
            "file_type": file_type,
            "metadata": metadata,
            "document_type_hint": document_type_hint,
            "filename": s3_key.split("/")[-1] if "/" in s3_key else s3_key,
        }

    except Exception as e:
        debug_error(e, "vision_analyzer_analyze_document", {"s3_key": s3_key})
        return {
            "success": False,
            "error": str(e),
            "s3_key": s3_key,
        }


@tool
def validate_nf_data(
    nf_number: str,
    supplier_cnpj: str,
    access_key: Optional[str] = None,
    emission_date: Optional[str] = None,
    total_value: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate extracted NF-e data fields.

    Performs validation on CNPJ, access key, and other NF-e fields
    using Brazilian fiscal rules.

    Args:
        nf_number: NF-e number
        supplier_cnpj: Supplier's CNPJ
        access_key: 44-digit access key (optional)
        emission_date: Emission date string (optional)
        total_value: Total value string (optional)

    Returns:
        Dict with validation results for each field
    """
    results = {
        "nf_number": {
            "value": nf_number,
            "valid": bool(nf_number and nf_number.isdigit()),
        },
    }

    # Validate CNPJ
    cnpj_valid, cnpj_formatted = validate_cnpj(supplier_cnpj)
    results["supplier_cnpj"] = {
        "value": supplier_cnpj,
        "valid": cnpj_valid,
        "formatted": cnpj_formatted,
    }

    # Validate access key if provided
    if access_key:
        key_valid, key_normalized = validate_access_key(access_key)
        results["access_key"] = {
            "value": access_key,
            "valid": key_valid,
            "normalized": key_normalized,
        }

    # Parse date if provided
    if emission_date:
        parsed_date = parse_brazilian_date(emission_date)
        results["emission_date"] = {
            "value": emission_date,
            "valid": parsed_date is not None,
            "parsed": str(parsed_date) if parsed_date else None,
        }

    # Parse total value if provided
    if total_value:
        parsed_value = parse_brazilian_currency(total_value)
        results["total_value"] = {
            "value": total_value,
            "valid": parsed_value is not None,
            "parsed": float(parsed_value) if parsed_value else None,
        }

    return results


@tool
def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for monitoring.

    Returns:
        Health status with agent info
    """
    return {
        "status": "healthy",
        "agent_id": AGENT_ID,
        "agent_name": AGENT_NAME,
        "version": AGENT_VERSION,
        "protocol": "A2A",
        "port": 9000,  # A2A standard port (BUG-029 FIX)
    }


# =============================================================================
# Strands Agent Configuration with Structured Output
# =============================================================================

def create_agent() -> Agent:
    """
    Create Strands Agent with structured output enforcement.

    BUG-025 FIX: Uses structured_output_model to ensure Pydantic validation
    of all responses.

    Returns:
        Configured Strands Agent with structured output
    """
    return Agent(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        model=create_gemini_model(AGENT_ID),  # GeminiModel via Google AI Studio
        tools=[
            analyze_document,
            validate_nf_data,
            health_check,
        ],
        system_prompt=SYSTEM_PROMPT,
        # BUG-025 FIX: Enforce Pydantic structured output
        structured_output_model=VisionAnalysisResponse,
        # BUG-027 FIX: Add hooks for logging, metrics, and error enrichment
        hooks=[LoggingHook(), MetricsHook(), DebugHook(timeout_seconds=30.0)],
    )


# =============================================================================
# A2A Request Processing
# =============================================================================


def process_vision_request(
    agent: Agent,
    request: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Process a vision analysis request and return structured JSON output.

    Args:
        agent: The Strands Agent instance
        request: A2A request with action and parameters

    Returns:
        VisionAnalysisResponse as dict (clean JSON)
    """
    start_time = time.time()
    action = request.get("action", "analyze")
    s3_key = request.get("s3_key")
    bucket = request.get("bucket", DEFAULT_BUCKET)
    document_type_hint = request.get("document_type", "unknown")

    logger.info(
        f"[{AGENT_NAME}] Processing request: action={action}, "
        f"s3_key={s3_key}, document_type={document_type_hint}"
    )

    # Validate required parameters
    if not s3_key and action != "health_check":
        debug_error(ValueError("Missing required parameter: s3_key"), "vision_analyzer_validate", {"action": action})
        return {
            "success": False,
            "document_type": "unknown",
            "file_type": "image",
            "page_count": 0,
            "analysis_confidence": 0.0,
            "warnings": ["No s3_key provided in request"],
            "needs_human_review": True,
            "recommended_action": "reject",
        }

    # Handle health check
    if action == "health_check":
        return health_check()

    try:
        # Load and prepare document
        content, metadata = load_document_from_s3(s3_key, bucket)
        images = prepare_for_vision_api(content, s3_key)

        # Determine file type
        file_type = "pdf" if is_pdf(content) else "image"
        if file_type == "pdf" and len(images) > 1:
            file_type = "multi-page-pdf"

        # Build analysis prompt
        filename = s3_key.split("/")[-1] if "/" in s3_key else s3_key
        analysis_prompt = build_analysis_request(
            document_type_hint=document_type_hint,
            filename=filename,
            page_count=len(images),
        )

        prompt_with_context = f"""
{analysis_prompt}

Document metadata:
- Filename: {filename}
- File type: {file_type}
- Page count: {len(images)}
- S3 location: s3://{bucket}/{s3_key}

Please analyze the document image(s) provided and return a VisionAnalysisResponse.
"""

        logger.info(f"[{AGENT_NAME}] Invoking agent for vision analysis...")

        # Invoke agent with multimodal content
        result = agent(
            prompt_with_context,
            images=images,  # Pass images for multimodal processing
        )

        # Extract structured output
        if hasattr(result, "structured_output") and result.structured_output:
            response = result.structured_output.model_dump()
            response["processing_time_ms"] = int((time.time() - start_time) * 1000)

            logger.info(
                f"[{AGENT_NAME}] Analysis complete: confidence={response.get('analysis_confidence', 0):.2f}, "
                f"time={response.get('processing_time_ms')}ms"
            )
            return response

        # Fallback response
        logger.warning(f"[{AGENT_NAME}] No structured_output, using fallback response")
        return {
            "success": True,
            "document_type": document_type_hint,
            "file_type": file_type,
            "page_count": len(images),
            "analysis_confidence": 0.5,
            "warnings": ["Structured output not available, using text response"],
            "needs_human_review": True,
            "recommended_action": "needs_review",
            "raw_text_preview": str(result)[:500] if result else None,
            "processing_time_ms": int((time.time() - start_time) * 1000),
        }

    except Exception as e:
        debug_error(e, "vision_analyzer_request_processing", {"s3_key": s3_key, "action": action})
        return {
            "success": False,
            "document_type": "unknown",
            "file_type": "image",
            "page_count": 0,
            "analysis_confidence": 0.0,
            "warnings": [f"Analysis failed: {str(e)}"],
            "needs_human_review": True,
            "recommended_action": "reject",
            "processing_time_ms": int((time.time() - start_time) * 1000),
        }


# =============================================================================
# A2A Server Entry Point
# =============================================================================

def main():
    """
    Start the Strands A2AServer with 100% A2A Architecture.

    Port 9000 is the A2A standard port (BUG-029 FIX).
    Agent Card is served at /.well-known/agent-card.json for discovery.
    """
    logger.info(f"[{AGENT_NAME}] Starting Strands A2AServer on port 9000...")
    logger.info(f"[{AGENT_NAME}] Version: {AGENT_VERSION}")
    logger.info(f"[{AGENT_NAME}] Skills: {[s.id for s in AGENT_SKILLS]}")
    logger.info(f"[{AGENT_NAME}] Agent Card: GET /.well-known/agent-card.json")

    # Create FastAPI app FIRST for immediate health check response
    app = FastAPI(title=AGENT_NAME, version=AGENT_VERSION)

    @app.get("/ping")
    def ping():
        """Health check endpoint - responds immediately for AgentCore cold start."""
        return {"status": "healthy", "agent": AGENT_ID, "version": AGENT_VERSION}

    logger.info(f"[{AGENT_NAME}] Health check endpoint ready: GET /ping")

    # Create agent (uses LazyGeminiModel for deferred initialization)
    agent = create_agent()

    # Custom A2A message handler with structured output extraction
    @app.post("/")
    async def handle_a2a_message(request: Request):
        """
        Custom A2A message handler with structured output extraction.
        """
        try:
            body = await request.json()
            logger.info(f"[{AGENT_NAME}] Received A2A request: {json.dumps(body)[:500]}")

            # Validate JSON-RPC 2.0 format
            if body.get("jsonrpc") != "2.0":
                return {
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "error": {"code": -32600, "message": "Invalid Request: not JSON-RPC 2.0"},
                }

            method = body.get("method", "")
            request_id = body.get("id", "unknown")

            # Handle message/send method (A2A Protocol)
            if method == "message/send":
                params = body.get("params", {})
                message = params.get("message", {})
                parts = message.get("parts", [])

                # Extract text from message parts
                text_content = ""
                for part in parts:
                    if part.get("kind") == "text":
                        text_content += part.get("text", "")

                # Try to parse as JSON payload
                payload = {}
                if text_content:
                    try:
                        payload = json.loads(text_content)
                    except json.JSONDecodeError:
                        payload = {"prompt": text_content}

                # Process the vision request
                result = process_vision_request(agent, payload)

                # Return A2A JSON-RPC response
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "message": {
                            "role": "assistant",
                            "parts": [
                                {
                                    "kind": "text",
                                    "text": json.dumps(result, ensure_ascii=False),
                                }
                            ],
                        },
                    },
                }

            # Unknown method
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        except Exception as e:
            debug_error(e, "vision_analyzer_a2a_handler", {})
            return {
                "jsonrpc": "2.0",
                "id": body.get("id") if "body" in dir() else "unknown",
                "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
            }

    # Create A2A server for Agent Card discovery only
    a2a_server = A2AServer(
        agent=agent,
        host="0.0.0.0",
        port=9000,  # A2A standard port (BUG-029 FIX)
        version=AGENT_VERSION,
        skills=AGENT_SKILLS,
        serve_at_root=True,  # Serve at root for A2A compatibility
    )

    # Mount A2A server for /.well-known/agent-card.json discovery
    a2a_app = a2a_server.to_fastapi_app()
    app.mount("/.well-known", a2a_app)

    logger.info(f"[{AGENT_NAME}] A2A server mounted, starting uvicorn...")

    # Start uvicorn server
    uvicorn.run(app, host="0.0.0.0", port=9000)  # A2A standard port


if __name__ == "__main__":
    main()
