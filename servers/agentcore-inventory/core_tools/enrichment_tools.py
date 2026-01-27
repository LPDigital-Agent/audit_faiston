# =============================================================================
# Equipment Enrichment Tools
# =============================================================================
# High-level tools for equipment data enrichment using Tavily AI search.
#
# Architecture:
#     EnrichmentAgent -> enrichment_tools -> TavilyGatewayAdapter -> Gateway -> Tavily
#                     -> EquipmentDocsS3Client -> S3 Knowledge Repository
#                     -> BedrockKBSync -> Bedrock Knowledge Base
#
# Tools:
#     - enrich_equipment(): Full enrichment workflow for single equipment
#     - enrich_batch(): Batch enrichment for multiple items
#     - validate_part_number(): Validate PN via web search
#     - trigger_kb_sync(): Trigger Bedrock Knowledge Base sync
#
# Reference:
#     - PRD: product-development/current-feature/PRD-tavily-enrichment.md
#     - Tavily Gateway: tools/tavily_gateway.py
#     - S3 Client: tools/s3_client.py
#
# CRITICAL: Lazy imports for cold start optimization (<30s limit)
#
# Author: Faiston NEXO Team
# Date: January 2026
# =============================================================================

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from shared.debug_utils import debug_error

logger = logging.getLogger(__name__)

# Module version for deployment tracking
_MODULE_VERSION = "2026-01-13T00:00:00Z"
logger.info("[EnrichmentTools] Module loaded - version %s", _MODULE_VERSION)


# =============================================================================
# Types and Enums
# =============================================================================


class EnrichmentStatus(str, Enum):
    """Status of enrichment operation."""
    SUCCESS = "success"
    PARTIAL = "partial"  # Some data found, but incomplete
    NOT_FOUND = "not_found"  # No relevant data found
    ERROR = "error"


class DocumentType(str, Enum):
    """Types of equipment documentation."""
    DATASHEET = "datasheet"
    MANUAL = "manual"
    SPECIFICATIONS = "specifications"
    QUICK_START = "quick_start"
    FIRMWARE = "firmware"
    DRIVER = "driver"


@dataclass
class EnrichmentResult:
    """Result of a single equipment enrichment."""
    part_number: str
    serial_number: Optional[str]
    status: EnrichmentStatus
    manufacturer: Optional[str] = None
    description: Optional[str] = None
    specifications: Dict[str, Any] = field(default_factory=dict)
    documents: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
    error_message: Optional[str] = None
    enrichment_timestamp: str = field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "part_number": self.part_number,
            "serial_number": self.serial_number,
            "status": self.status.value,
            "manufacturer": self.manufacturer,
            "description": self.description,
            "specifications": self.specifications,
            "documents": self.documents,
            "sources": self.sources,
            "confidence_score": self.confidence_score,
            "error_message": self.error_message,
            "enrichment_timestamp": self.enrichment_timestamp,
        }


@dataclass
class BatchEnrichmentResult:
    """Result of batch enrichment operation."""
    import_id: str
    total_items: int
    successful: int
    partial: int
    not_found: int
    errors: int
    results: List[EnrichmentResult] = field(default_factory=list)
    duration_seconds: float = 0.0
    kb_sync_triggered: bool = False


# =============================================================================
# Enrichment Tools
# =============================================================================


def enrich_equipment(
    part_number: str,
    serial_number: Optional[str] = None,
    manufacturer_hint: Optional[str] = None,
    store_to_s3: bool = True,
    download_documents: bool = False,
) -> EnrichmentResult:
    """
    Enrich a single equipment item with documentation and specifications.

    This is the main enrichment function that:
    1. Searches Tavily for equipment documentation
    2. Extracts specifications from found pages
    3. Optionally downloads datasheets/manuals
    4. Stores results in S3 Knowledge Repository

    Args:
        part_number: Equipment part number (e.g., "C9200-24P")
        serial_number: Optional serial number for tracking
        manufacturer_hint: Optional manufacturer name to improve search
        store_to_s3: Store enrichment results to S3 (default True)
        download_documents: Download PDF documents (default False)

    Returns:
        EnrichmentResult with found data and sources

    Example:
        ```python
        result = enrich_equipment(
            part_number="C9200-24P",
            manufacturer_hint="Cisco",
            store_to_s3=True,
        )
        logger.info("Status: %s, Sources: %d", result.status, len(result.sources))
        ```
    """
    logger.info(
        f"[EnrichmentTools] enrich_equipment: "
        f"part_number={part_number}, manufacturer={manufacturer_hint}"
    )

    try:
        # Lazy imports
        from core_tools.tavily_gateway import (
            TavilyGatewayAdapterFactory,
        )
        from core_tools.s3_client import EquipmentDocsS3Client

        # Initialize clients
        tavily = TavilyGatewayAdapterFactory.create_from_env()
        s3_client = EquipmentDocsS3Client()

        # Step 1: Research equipment via Tavily
        research = tavily.research_equipment(
            part_number=part_number,
            manufacturer=manufacturer_hint,
            search_types=["datasheet", "specifications", "manual"],
        )

        # Collect sources
        sources = research.get("sources", [])
        manufacturer = research.get("manufacturer", manufacturer_hint or "Unknown")

        # Initialize result
        result = EnrichmentResult(
            part_number=part_number,
            serial_number=serial_number,
            status=EnrichmentStatus.NOT_FOUND,
            manufacturer=manufacturer,
            sources=sources,
        )

        # Step 2: Process datasheet if found
        datasheet = research.get("datasheet")
        if datasheet:
            result.documents.append({
                "type": DocumentType.DATASHEET.value,
                "url": datasheet.url,
                "title": datasheet.title,
                "content_preview": datasheet.content[:500] if datasheet.content else "",
            })

            # Extract specifications from datasheet content
            specs = _extract_specifications(
                datasheet.content or "",
                datasheet.raw_content or "",
            )
            if specs:
                result.specifications.update(specs)
                result.status = EnrichmentStatus.PARTIAL

        # Step 3: Process manual if found
        manual = research.get("manual")
        if manual:
            result.documents.append({
                "type": DocumentType.MANUAL.value,
                "url": manual.url,
                "title": manual.title,
            })

        # Step 4: Process specifications page
        spec_data = research.get("specifications", {})
        if spec_data.get("content"):
            additional_specs = _extract_specifications(
                spec_data.get("content", ""),
                spec_data.get("raw_content", ""),
            )
            if additional_specs:
                result.specifications.update(additional_specs)

        # Determine final status
        if result.documents or result.specifications:
            if len(result.documents) >= 2 and result.specifications:
                result.status = EnrichmentStatus.SUCCESS
                result.confidence_score = 0.9
            else:
                result.status = EnrichmentStatus.PARTIAL
                result.confidence_score = 0.6
        else:
            result.status = EnrichmentStatus.NOT_FOUND
            result.confidence_score = 0.0

        # Generate description from specs
        if result.specifications:
            result.description = _generate_description(
                part_number,
                manufacturer,
                result.specifications,
            )

        # Step 5: Store to S3 Knowledge Repository
        if store_to_s3 and result.status != EnrichmentStatus.NOT_FOUND:
            _store_enrichment_result(s3_client, result)

        # Step 6: Download documents if requested
        if download_documents and result.documents:
            _download_documents(tavily, s3_client, result)

        logger.info(
            f"[EnrichmentTools] enrich_equipment completed: "
            f"status={result.status.value}, sources={len(result.sources)}"
        )

        return result

    except Exception as e:
        debug_error(e, "enrichment_enrich_equipment", {"part_number": part_number, "manufacturer_hint": manufacturer_hint})
        return EnrichmentResult(
            part_number=part_number,
            serial_number=serial_number,
            status=EnrichmentStatus.ERROR,
            error_message=str(e),
        )


def enrich_batch(
    items: List[Dict[str, Any]],
    import_id: str,
    tenant_id: str,
    store_to_s3: bool = True,
    trigger_kb_sync: bool = True,
    max_concurrent: int = 5,
) -> BatchEnrichmentResult:
    """
    Batch enrichment for multiple equipment items.

    Processes items sequentially (or with limited concurrency) to
    respect Tavily rate limits. Aggregates results and optionally
    triggers Bedrock Knowledge Base sync after completion.

    Args:
        items: List of dicts with part_number, serial_number, manufacturer
        import_id: Import transaction ID for tracking
        tenant_id: Tenant identifier
        store_to_s3: Store results to S3
        trigger_kb_sync: Trigger KB sync after completion
        max_concurrent: Maximum concurrent enrichments (unused for now)

    Returns:
        BatchEnrichmentResult with aggregated statistics

    Example:
        ```python
        items = [
            {"part_number": "C9200-24P", "manufacturer": "Cisco"},
            {"part_number": "DL380-G10", "manufacturer": "HP"},
        ]
        batch_result = enrich_batch(
            items=items,
            import_id="import-uuid",
            tenant_id="faiston",
        )
        logger.info("Successful: %d/%d", batch_result.successful, batch_result.total_items)
        ```
    """
    logger.info(
        f"[EnrichmentTools] enrich_batch: "
        f"import_id={import_id}, items={len(items)}"
    )

    start_time = datetime.utcnow()

    batch_result = BatchEnrichmentResult(
        import_id=import_id,
        total_items=len(items),
        successful=0,
        partial=0,
        not_found=0,
        errors=0,
    )

    # Process each item
    for item in items:
        part_number = item.get("part_number", "")
        if not part_number:
            continue

        result = enrich_equipment(
            part_number=part_number,
            serial_number=item.get("serial_number"),
            manufacturer_hint=item.get("manufacturer"),
            store_to_s3=store_to_s3,
            download_documents=False,  # Batch mode doesn't download docs
        )

        batch_result.results.append(result)

        # Update counters
        if result.status == EnrichmentStatus.SUCCESS:
            batch_result.successful += 1
        elif result.status == EnrichmentStatus.PARTIAL:
            batch_result.partial += 1
        elif result.status == EnrichmentStatus.NOT_FOUND:
            batch_result.not_found += 1
        else:
            batch_result.errors += 1

    # Calculate duration
    end_time = datetime.utcnow()
    batch_result.duration_seconds = (end_time - start_time).total_seconds()

    # Trigger KB sync if requested
    if trigger_kb_sync and (batch_result.successful > 0 or batch_result.partial > 0):
        try:
            sync_result = trigger_knowledge_base_sync()
            batch_result.kb_sync_triggered = sync_result.get("triggered", False)
        except Exception as e:
            debug_error(e, "enrichment_kb_sync", {"import_id": import_id})
            batch_result.kb_sync_triggered = False

    logger.info(
        f"[EnrichmentTools] enrich_batch completed: "
        f"success={batch_result.successful}, partial={batch_result.partial}, "
        f"not_found={batch_result.not_found}, errors={batch_result.errors}, "
        f"duration={batch_result.duration_seconds:.1f}s"
    )

    return batch_result


def validate_part_number(
    part_number: str,
    manufacturer_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate a part number by searching for its existence online.

    Useful for detecting typos or invalid part numbers before import.

    Args:
        part_number: Part number to validate
        manufacturer_hint: Optional manufacturer name

    Returns:
        Dict with:
        - valid: bool (True if found online)
        - confidence: float (0-1)
        - manufacturer: str (detected or confirmed)
        - suggestions: List[str] (alternative PNs if invalid)

    Example:
        ```python
        validation = validate_part_number("C9200-24P", "Cisco")
        if validation["valid"]:
            logger.info("Valid PN, manufacturer: %s", validation['manufacturer'])
        ```
    """
    logger.info(f"[EnrichmentTools] validate_part_number: {part_number}")

    try:
        from core_tools.tavily_gateway import TavilyGatewayAdapterFactory, SearchDepth

        tavily = TavilyGatewayAdapterFactory.create_from_env()

        # Search for part number
        query = f'"{part_number}"'
        if manufacturer_hint:
            query = f'{manufacturer_hint} {query}'

        results = tavily.search(
            query=query,
            search_depth=SearchDepth.BASIC,
            max_results=5,
        )

        if not results:
            return {
                "valid": False,
                "confidence": 0.0,
                "manufacturer": None,
                "suggestions": [],
                "reason": "No search results found",
            }

        # Check if part number appears in results
        pn_found = False
        detected_manufacturer = None

        for result in results:
            content = f"{result.title} {result.content}".lower()
            if part_number.lower() in content:
                pn_found = True
                # Try to detect manufacturer from URL
                url = result.url.lower()
                detected_manufacturer = _detect_manufacturer_from_url(url)
                break

        return {
            "valid": pn_found,
            "confidence": 0.85 if pn_found else 0.2,
            "manufacturer": detected_manufacturer or manufacturer_hint,
            "suggestions": [],
            "top_result": {
                "url": results[0].url,
                "title": results[0].title,
            } if results else None,
        }

    except Exception as e:
        debug_error(e, "enrichment_validate_part_number", {"part_number": part_number})
        return {
            "valid": False,
            "confidence": 0.0,
            "manufacturer": None,
            "suggestions": [],
            "error": str(e),
        }


def trigger_knowledge_base_sync(
    knowledge_base_id: Optional[str] = None,
    data_source_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Trigger Bedrock Knowledge Base sync to index new documents.

    Starts an ingestion job to process documents added to S3.
    Uses SSM parameters to get KB configuration if not provided.

    Args:
        knowledge_base_id: Optional KB ID (default from SSM)
        data_source_id: Optional data source ID (default from SSM)

    Returns:
        Dict with ingestion job details

    Example:
        ```python
        result = trigger_knowledge_base_sync()
        if result["triggered"]:
            logger.info("Job started: %s", result['ingestion_job_id'])
        ```
    """
    logger.info("[EnrichmentTools] trigger_knowledge_base_sync")

    try:
        import boto3

        # Get KB config from SSM if not provided
        if not knowledge_base_id or not data_source_id:
            ssm = boto3.client("ssm", region_name="us-east-2")
            param_name = os.environ.get(
                "KB_CONFIG_SSM_PARAM",
                "/faiston-one/sga/knowledge-base/config"
            )

            try:
                response = ssm.get_parameter(Name=param_name)
                config = json.loads(response["Parameter"]["Value"])
                knowledge_base_id = knowledge_base_id or config.get("knowledge_base_id")
                data_source_id = data_source_id or config.get("data_source_id")
            except Exception as e:
                logger.warning(f"[EnrichmentTools] Could not get KB config from SSM: {e}")

        if not knowledge_base_id or not data_source_id:
            return {
                "triggered": False,
                "error": "Missing knowledge_base_id or data_source_id",
            }

        # Start ingestion job
        bedrock = boto3.client("bedrock-agent", region_name="us-east-2")

        response = bedrock.start_ingestion_job(
            knowledgeBaseId=knowledge_base_id,
            dataSourceId=data_source_id,
        )

        job_id = response.get("ingestionJob", {}).get("ingestionJobId")

        logger.info(f"[EnrichmentTools] KB sync triggered: job_id={job_id}")

        return {
            "triggered": True,
            "ingestion_job_id": job_id,
            "knowledge_base_id": knowledge_base_id,
            "data_source_id": data_source_id,
            "status": response.get("ingestionJob", {}).get("status"),
        }

    except Exception as e:
        debug_error(e, "enrichment_trigger_kb_sync", {"knowledge_base_id": knowledge_base_id})
        return {
            "triggered": False,
            "error": str(e),
        }


def get_enrichment_status(
    part_number: str,
) -> Dict[str, Any]:
    """
    Check if a part number has already been enriched.

    Args:
        part_number: Part number to check

    Returns:
        Dict with enrichment status and metadata
    """
    logger.info(f"[EnrichmentTools] get_enrichment_status: {part_number}")

    try:
        from core_tools.s3_client import EquipmentDocsS3Client

        s3_client = EquipmentDocsS3Client()
        docs = s3_client.list_documents_for_part(part_number)

        if not docs:
            return {
                "enriched": False,
                "part_number": part_number,
                "documents": [],
            }

        # Get metadata from first document
        metadata = None
        for doc in docs:
            meta = s3_client.get_document_metadata(doc["key"])
            if meta:
                metadata = meta
                break

        return {
            "enriched": True,
            "part_number": part_number,
            "document_count": len(docs),
            "documents": docs,
            "last_enriched": metadata.get("upload_timestamp") if metadata else None,
            "manufacturer": metadata.get("manufacturer") if metadata else None,
        }

    except Exception as e:
        debug_error(e, "enrichment_get_status", {"part_number": part_number})
        return {
            "enriched": False,
            "part_number": part_number,
            "error": str(e),
        }


# =============================================================================
# Helper Functions
# =============================================================================


def _extract_specifications(
    content: str,
    raw_content: str = "",
) -> Dict[str, Any]:
    """
    Extract technical specifications from content.

    Uses pattern matching to find common spec formats.
    """
    specs = {}

    # Combine content
    full_content = f"{content} {raw_content}".lower()

    # Common spec patterns
    patterns = {
        "ports": r"(\d+)\s*(?:port|porta)",
        "power": r"(\d+)\s*(?:watt|w)\s*(?:poe|power)",
        "voltage": r"(\d+)\s*(?:volt|v)\s*(?:ac|dc)?",
        "weight": r"(\d+\.?\d*)\s*(?:kg|lb)",
        "dimensions": r"(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*x\s*(\d+\.?\d*)",
        "temperature": r"(\d+)\s*(?:to|-)\s*(\d+)\s*(?:°?c|celsius)",
    }

    import re

    for spec_name, pattern in patterns.items():
        match = re.search(pattern, full_content)
        if match:
            specs[spec_name] = match.group(0)

    return specs


def _generate_description(
    part_number: str,
    manufacturer: str,
    specifications: Dict[str, Any],
) -> str:
    """Generate human-readable description from specs."""
    desc_parts = [f"{manufacturer} {part_number}"]

    if "ports" in specifications:
        desc_parts.append(f"with {specifications['ports']}")

    if "power" in specifications:
        desc_parts.append(f"({specifications['power']})")

    return " ".join(desc_parts)


def _detect_manufacturer_from_url(url: str) -> Optional[str]:
    """Detect manufacturer from URL domain."""
    url_lower = url.lower()

    manufacturers = {
        "cisco.com": "Cisco",
        "dell.com": "Dell",
        "hp.com": "HP",
        "hpe.com": "HPE",
        "lenovo.com": "Lenovo",
        "ibm.com": "IBM",
        "juniper.net": "Juniper",
        "arista.com": "Arista",
        "netgear.com": "Netgear",
        "ui.com": "Ubiquiti",
        "fortinet.com": "Fortinet",
        "paloaltonetworks.com": "Palo Alto",
    }

    for domain, manufacturer in manufacturers.items():
        if domain in url_lower:
            return manufacturer

    return None


def _store_enrichment_result(
    s3_client,
    result: EnrichmentResult,
) -> bool:
    """Store enrichment result to S3 Knowledge Repository."""
    try:
        # Store metadata JSON
        metadata_content = json.dumps(
            result.to_dict(),
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")

        upload_result = s3_client.upload_equipment_document(
            part_number=result.part_number,
            document_type="enrichment_metadata",
            filename="enrichment_result.json",
            content=metadata_content,
            metadata={
                "manufacturer": result.manufacturer or "Unknown",
                "enrichment_status": result.status.value,
                "confidence_score": str(result.confidence_score),
            },
        )

        return upload_result.get("success", False)

    except Exception as e:
        debug_error(e, "enrichment_store_result", {"part_number": result.part_number})
        return False


def _download_documents(
    tavily,
    s3_client,
    result: EnrichmentResult,
) -> None:
    """Download and store documents from URLs."""
    try:
        from core_tools.tavily_gateway import ExtractFormat

        for doc in result.documents:
            url = doc.get("url", "")
            if not url:
                continue

            # Check if URL is a direct PDF link
            if url.lower().endswith(".pdf"):
                # Download via HTTP
                _download_pdf(url, s3_client, result.part_number, doc["type"])
            else:
                # Extract content via Tavily
                extracted = tavily.extract(
                    urls=[url],
                    extract_depth="advanced",
                    format=ExtractFormat.MARKDOWN,
                )

                if extracted:
                    content = extracted[0].content
                    # Store as markdown
                    s3_client.upload_equipment_document(
                        part_number=result.part_number,
                        document_type=doc["type"],
                        filename=f"{doc['type']}.md",
                        content=content.encode("utf-8"),
                        metadata={
                            "source_url": url,
                            "manufacturer": result.manufacturer or "Unknown",
                        },
                    )

    except Exception as e:
        debug_error(e, "enrichment_download_documents", {"part_number": result.part_number})


def _download_pdf(
    url: str,
    s3_client,
    part_number: str,
    doc_type: str,
) -> bool:
    """Download PDF from URL and store to S3."""
    try:
        import urllib.request

        # Download PDF
        with urllib.request.urlopen(url, timeout=30) as response:
            content = response.read()

        # Extract filename from URL
        parsed = urlparse(url)
        filename = parsed.path.split("/")[-1] or f"{doc_type}.pdf"

        # Upload to S3
        result = s3_client.upload_equipment_document(
            part_number=part_number,
            document_type=doc_type,
            filename=filename,
            content=content,
            metadata={"source_url": url},
        )

        return result.get("success", False)

    except Exception as e:
        debug_error(e, "enrichment_download_pdf", {"url": url, "part_number": part_number})
        return False


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Types
    "EnrichmentStatus",
    "DocumentType",
    "EnrichmentResult",
    "BatchEnrichmentResult",
    # Tools
    "enrich_equipment",
    "enrich_batch",
    "validate_part_number",
    "trigger_knowledge_base_sync",
    "get_enrichment_status",
]
