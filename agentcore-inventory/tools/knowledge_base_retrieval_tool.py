# =============================================================================
# Knowledge Base Retrieval Tool
# =============================================================================
# Tool for querying the Bedrock Knowledge Base containing equipment documentation.
# Returns answers with citations to source documents.
#
# Uses AWS Bedrock's RetrieveAndGenerate API for RAG (Retrieval Augmented Generation).
#
# CRITICAL: Lazy imports for cold start optimization (<30s limit)
#
# Security: OWASP-compliant input validation, no PII in queries
# =============================================================================

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging
import os

logger = logging.getLogger(__name__)

# Module version for deployment tracking
_MODULE_VERSION = "2026-01-07T00:00:00Z"
logger.info("[KBRetrievalTool] Module loaded - version %s", _MODULE_VERSION)


# =============================================================================
# Constants
# =============================================================================

# Knowledge Base ID (set via environment or use default)
KNOWLEDGE_BASE_ID = os.environ.get(
    "EQUIPMENT_KB_ID",
    ""  # Will be populated after KB creation in AWS Console
)

# Region for Bedrock
AWS_REGION = os.environ.get("AWS_REGION", "us-east-2")

# Model for generation (Titan or Claude)
GENERATION_MODEL_ARN = os.environ.get(
    "KB_GENERATION_MODEL_ARN",
    f"arn:aws:bedrock:{AWS_REGION}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"
)


# =============================================================================
# Types
# =============================================================================


@dataclass
class Citation:
    """A citation from a KB document."""
    document_id: str
    s3_uri: str
    part_number: Optional[str]
    document_type: Optional[str]
    title: Optional[str]
    excerpt: str
    score: float


@dataclass
class KBQueryResult:
    """Result from a Knowledge Base query."""
    success: bool
    answer: str
    citations: List[Citation]
    query: str
    error: Optional[str] = None


# =============================================================================
# Knowledge Base Query
# =============================================================================


async def query_knowledge_base(
    query: str,
    part_number_filter: Optional[str] = None,
    max_results: int = 5,
) -> Dict[str, Any]:
    """
    Query the equipment documentation Knowledge Base.

    Uses Bedrock's RetrieveAndGenerate API for RAG:
    1. Retrieves relevant document chunks from KB
    2. Generates an answer using the retrieved context
    3. Returns answer with citations

    Args:
        query: Natural language question
        part_number_filter: Optional filter by part number
        max_results: Maximum number of citations to return

    Returns:
        Dict with answer, citations, and metadata
    """
    logger.info("[KBRetrievalTool] Query: '%s...'", query[:50])

    # Validate inputs
    if not query or len(query) > 1000:
        return {
            "success": False,
            "error": "Query must be 1-1000 characters",
        }

    # Check if KB is configured
    if not KNOWLEDGE_BASE_ID:
        return {
            "success": False,
            "error": "Knowledge Base not configured. Set EQUIPMENT_KB_ID environment variable.",
            "answer": "",
            "citations": [],
        }

    try:
        # Lazy import
        import boto3
        from botocore.config import Config

        # BUG-022 v9 FIX: Add timeout config (prevents hangs)
        timeout_config = Config(
            connect_timeout=5,
            read_timeout=60,  # Longer timeout for RAG generation
            retries={"max_attempts": 2}
        )

        # Create Bedrock Agent Runtime client
        client = boto3.client(
            "bedrock-agent-runtime",
            region_name=AWS_REGION,
            config=timeout_config,
        )

        # Build retrieval configuration
        retrieval_config = {
            "vectorSearchConfiguration": {
                "numberOfResults": max_results,
            }
        }

        # Add filter if part number specified
        if part_number_filter:
            retrieval_config["vectorSearchConfiguration"]["filter"] = {
                "equals": {
                    "key": "part_number",
                    "value": part_number_filter,
                }
            }

        # Build generation configuration
        generation_config = {
            "inferenceConfig": {
                "textInferenceConfig": {
                    "temperature": 0.2,
                    "topP": 0.9,
                    "maxTokens": 1024,
                }
            },
            "additionalModelRequestFields": {},
        }

        # Call RetrieveAndGenerate
        response = client.retrieve_and_generate(
            input={
                "text": query,
            },
            retrieveAndGenerateConfiguration={
                "type": "KNOWLEDGE_BASE",
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": KNOWLEDGE_BASE_ID,
                    "modelArn": GENERATION_MODEL_ARN,
                    "retrievalConfiguration": retrieval_config,
                    "generationConfiguration": generation_config,
                },
            },
        )

        # Extract answer
        answer = response.get("output", {}).get("text", "")

        # Extract citations
        citations = []
        for citation_data in response.get("citations", []):
            for ref in citation_data.get("retrievedReferences", []):
                location = ref.get("location", {})
                s3_location = location.get("s3Location", {})
                metadata = ref.get("metadata", {})

                citation = Citation(
                    document_id=ref.get("documentId", ""),
                    s3_uri=s3_location.get("uri", ""),
                    part_number=metadata.get("part_number"),
                    document_type=metadata.get("document_type"),
                    title=metadata.get("title"),
                    excerpt=ref.get("content", {}).get("text", "")[:500],
                    score=ref.get("score", 0.0),
                )
                citations.append(citation)

        logger.info("[KBRetrievalTool] Found %d citations", len(citations))

        return {
            "success": True,
            "answer": answer,
            "citations": [
                {
                    "document_id": c.document_id,
                    "s3_uri": c.s3_uri,
                    "part_number": c.part_number,
                    "document_type": c.document_type,
                    "title": c.title,
                    "excerpt": c.excerpt,
                    "score": c.score,
                }
                for c in citations
            ],
            "query": query,
        }

    except client.exceptions.ResourceNotFoundException:
        return {
            "success": False,
            "error": f"Knowledge Base not found: {KNOWLEDGE_BASE_ID}",
            "answer": "",
            "citations": [],
        }

    except client.exceptions.ValidationException as e:
        return {
            "success": False,
            "error": f"Validation error: {str(e)}",
            "answer": "",
            "citations": [],
        }

    except Exception as e:
        logger.error("[KBRetrievalTool] Error: %s", e)
        return {
            "success": False,
            "error": str(e)[:200],
            "answer": "",
            "citations": [],
        }


async def retrieve_only(
    query: str,
    part_number_filter: Optional[str] = None,
    max_results: int = 10,
) -> Dict[str, Any]:
    """
    Retrieve relevant documents without generation.

    Useful for browsing documentation or when you want to
    process the results yourself.

    Args:
        query: Search query
        part_number_filter: Optional filter by part number
        max_results: Maximum results

    Returns:
        Dict with retrieved chunks
    """
    logger.info("[KBRetrievalTool] Retrieve: '%s...'", query[:50])

    if not KNOWLEDGE_BASE_ID:
        return {
            "success": False,
            "error": "Knowledge Base not configured",
            "results": [],
        }

    try:
        import boto3
        from botocore.config import Config

        # BUG-022 v9 FIX: Add timeout config (prevents hangs)
        timeout_config = Config(
            connect_timeout=5,
            read_timeout=30,
            retries={"max_attempts": 2}
        )

        client = boto3.client(
            "bedrock-agent-runtime",
            region_name=AWS_REGION,
            config=timeout_config,
        )

        # Build retrieval config
        retrieval_config = {
            "vectorSearchConfiguration": {
                "numberOfResults": max_results,
            }
        }

        if part_number_filter:
            retrieval_config["vectorSearchConfiguration"]["filter"] = {
                "equals": {
                    "key": "part_number",
                    "value": part_number_filter,
                }
            }

        # Call Retrieve
        response = client.retrieve(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            retrievalQuery={
                "text": query,
            },
            retrievalConfiguration=retrieval_config,
        )

        results = []
        for result in response.get("retrievalResults", []):
            location = result.get("location", {})
            s3_location = location.get("s3Location", {})
            metadata = result.get("metadata", {})

            results.append({
                "s3_uri": s3_location.get("uri", ""),
                "part_number": metadata.get("part_number"),
                "document_type": metadata.get("document_type"),
                "title": metadata.get("title"),
                "content": result.get("content", {}).get("text", ""),
                "score": result.get("score", 0.0),
            })

        return {
            "success": True,
            "results": results,
            "query": query,
        }

    except Exception as e:
        logger.error("[KBRetrievalTool] Retrieve error: %s", e)
        return {
            "success": False,
            "error": str(e)[:200],
            "results": [],
        }


# =============================================================================
# Utility Functions
# =============================================================================


def generate_download_url(s3_uri: str, expires_in: int = 3600) -> Optional[str]:
    """
    Generate a presigned URL for downloading a KB document.

    Args:
        s3_uri: S3 URI from citation (s3://bucket/key)
        expires_in: URL expiration in seconds

    Returns:
        Presigned download URL or None
    """
    try:
        import boto3
        from botocore.config import Config

        # Parse S3 URI
        if not s3_uri.startswith("s3://"):
            return None

        parts = s3_uri[5:].split("/", 1)
        if len(parts) != 2:
            return None

        bucket, key = parts

        # Generate presigned URL
        # BUG-022 v9 FIX: Add timeout config (prevents hangs)
        config = Config(
            signature_version='s3v4',
            connect_timeout=5,
            read_timeout=30,
            retries={"max_attempts": 2}
        )
        s3_client = boto3.client(
            's3',
            region_name=AWS_REGION,
            config=config,
        )

        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )

        return url

    except Exception as e:
        logger.error("[KBRetrievalTool] URL generation error: %s", e)
        return None


def format_citations_markdown(citations: List[Dict[str, Any]]) -> str:
    """
    Format citations as markdown for display.

    Args:
        citations: List of citation dicts

    Returns:
        Markdown-formatted string
    """
    if not citations:
        return ""

    lines = ["\n---\n**Fontes:**\n"]

    for i, citation in enumerate(citations, 1):
        title = citation.get("title") or citation.get("document_type") or "Documento"
        pn = citation.get("part_number", "")
        doc_type = citation.get("document_type", "")

        line = f"{i}. **{title}**"
        if pn:
            line += f" (PN: {pn})"
        if doc_type:
            line += f" - {doc_type}"

        lines.append(line)

    return "\n".join(lines)
