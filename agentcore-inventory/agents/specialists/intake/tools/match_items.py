# =============================================================================
# Match Items Tool
# =============================================================================
# Matches NF items to existing part numbers in the catalog.
# Uses multiple strategies: supplier code, description AI, NCM.
# =============================================================================

import logging
from typing import Dict, Any, List, Optional


from shared.audit_emitter import AgentAuditEmitter
from shared.xray_tracer import trace_tool_call

# Centralized model configuration (MANDATORY - Gemini 3.0 Pro + Thinking)
from agents.utils import get_model

logger = logging.getLogger(__name__)

AGENT_ID = "intake"
MODEL = get_model(AGENT_ID)  # gemini-3.0-pro (import tool with Thinking)
audit = AgentAuditEmitter(agent_id=AGENT_ID)


@trace_tool_call("sga_match_items")
async def match_items_tool(
    items: List[Dict[str, Any]],
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Match NF items to existing part numbers.

    Matching strategies (in order):
    1. Exact match on supplier code (cProd) - 95% confidence
    2. AI-assisted description matching - 70-85% confidence
    3. NCM code matching - 60% confidence

    Args:
        items: List of items from NF extraction
        session_id: Optional session ID for audit

    Returns:
        Matched and unmatched item lists
    """
    audit.working(
        message=f"Identificando {len(items)} itens...",
        session_id=session_id,
    )

    try:
        matched_items = []
        unmatched_items = []

        for item in items:
            # Try to find matching part number
            match = await _find_part_number(item)

            if match:
                matched_items.append({
                    **item,
                    "matched_pn": match["part_number"],
                    "match_confidence": match["confidence"],
                    "match_method": match["method"],
                })
            else:
                unmatched_items.append({
                    **item,
                    "suggested_pn": _suggest_part_number(item),
                })

        # Calculate overall match rate
        total = len(items)
        matched = len(matched_items)
        match_rate = matched / total if total > 0 else 0

        audit.completed(
            message=f"Identificados {matched}/{total} itens ({match_rate:.0%})",
            session_id=session_id,
            details={
                "matched": matched,
                "unmatched": len(unmatched_items),
                "match_rate": match_rate,
            },
        )

        return {
            "success": True,
            "matched_items": matched_items,
            "unmatched_items": unmatched_items,
            "match_rate": match_rate,
            "total_items": total,
        }

    except Exception as e:
        logger.error(f"[match_items] Error: {e}", exc_info=True)
        audit.error(
            message="Erro ao identificar itens",
            session_id=session_id,
            error=str(e),
        )
        return {
            "success": False,
            "error": str(e),
            "matched_items": [],
            "unmatched_items": items,
        }


async def _find_part_number(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Find matching part number for an NF item.

    Tries multiple strategies in order of confidence.
    """
    # Strategy 1: Match by supplier code (highest confidence)
    supplier_code = item.get("codigo")
    if supplier_code:
        pn = await _query_by_supplier_code(supplier_code)
        if pn:
            return {
                "part_number": pn["part_number"],
                "confidence": 0.95,
                "method": "supplier_code",
            }

    # Strategy 2: Match by description with AI
    description = item.get("descricao", "")
    if description and len(description) >= 5:
        pn = await _query_by_description(description)
        if pn:
            return {
                "part_number": pn["part_number"],
                "confidence": pn.get("match_score", 0.7),
                "method": "description_ai",
            }

    # Strategy 3: Match by NCM (lowest confidence)
    ncm = item.get("ncm")
    if ncm and len(ncm.replace(".", "")) >= 4:
        pn = await _query_by_ncm(ncm)
        if pn:
            return {
                "part_number": pn["part_number"],
                "confidence": 0.6,
                "method": "ncm_match",
            }

    return None


async def _query_by_supplier_code(supplier_code: str) -> Optional[Dict[str, Any]]:
    """
    Query part number by supplier code (cProd).

    This provides highest confidence as supplier codes are
    unique identifiers assigned by vendors.
    """
    if not supplier_code or not supplier_code.strip():
        return None

    try:
        from tools.db_client import DBClient
        db = DBClient()

        result = await db.query_pn_by_supplier_code(supplier_code.strip())
        return result

    except ImportError:
        logger.debug("[match_items] DBClient not available")
        return None
    except Exception as e:
        logger.warning(f"[match_items] Supplier code query error: {e}")
        return None


async def _query_by_description(description: str) -> Optional[Dict[str, Any]]:
    """
    Query part number by description using AI-powered matching.

    Extracts keywords and uses Gemini to rank candidate matches.
    """
    if not description:
        return None

    try:
        from tools.db_client import DBClient
        db = DBClient()

        # Extract keywords
        keywords = _extract_keywords(description)
        if not keywords:
            return None

        # Search for candidates
        candidates = await db.search_pn_by_keywords(keywords, limit=10)
        if not candidates:
            return None

        # Rank candidates using heuristic matching
        # BUG-025 FIX: Use heuristic instead of direct LLM call
        best_match = _rank_candidates_heuristic(description, candidates)
        return best_match

    except ImportError:
        logger.debug("[match_items] DBClient not available")
        return None
    except Exception as e:
        logger.warning(f"[match_items] Description query error: {e}")
        return None


async def _query_by_ncm(ncm: str) -> Optional[Dict[str, Any]]:
    """
    Query part number by NCM code.

    NCM (Nomenclatura Comum do Mercosul) is a fiscal classification.
    Items with same NCM are in the same category, so confidence is lower.
    """
    try:
        from tools.db_client import DBClient
        db = DBClient()

        matches = await db.query_pn_by_ncm(ncm, limit=5)
        return matches[0] if matches else None

    except ImportError:
        return None
    except Exception as e:
        logger.warning(f"[match_items] NCM query error: {e}")
        return None


def _extract_keywords(description: str) -> List[str]:
    """
    Extract meaningful keywords from product description.

    Filters stopwords and normalizes terms.
    """
    # Common stopwords (Portuguese and English)
    stopwords = {
        "de", "da", "do", "das", "dos", "em", "para", "com", "sem", "por",
        "uma", "uns", "the", "a", "an", "and", "or", "for", "with",
        "unidade", "peca", "item", "kit", "caixa", "pacote", "lote",
    }

    # Split and clean
    words = description.upper().replace(",", " ").replace("-", " ").split()

    # Filter and normalize
    keywords = []
    for word in words:
        clean = "".join(c for c in word if c.isalnum())
        if len(clean) >= 3 and clean.lower() not in stopwords:
            keywords.append(clean)

    # Return unique keywords, max 5
    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)
            if len(unique) >= 5:
                break

    return unique


def _rank_candidates_heuristic(
    target_description: str,
    candidates: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Rank candidate part numbers using heuristic matching.

    BUG-025 FIX: Removed direct google.genai SDK call.
    The IntakeAgent's LLM now handles complex reasoning via its system prompt.
    This function provides a fast Python heuristic for simple cases.

    For complex matching, the IntakeAgent can call this tool to get candidates,
    then reason about them using its built-in LLM capabilities.

    Args:
        target_description: Product description from NF
        candidates: List of candidate part numbers from database

    Returns:
        Best matching part number dict or None
    """
    if not candidates:
        return None

    # Single candidate - use with medium confidence
    if len(candidates) == 1:
        pn = candidates[0]
        return {
            "part_number": pn.get("part_number", pn.get("PK", "").replace("PN#", "")),
            "description": pn.get("description", ""),
            "match_score": 0.75,
        }

    # Normalize target description for comparison
    target_upper = target_description.upper()
    target_words = set(_extract_keywords(target_description))

    best_match = None
    best_score = 0.0

    for pn in candidates[:5]:
        pn_code = pn.get("part_number", pn.get("PK", "").replace("PN#", ""))
        pn_desc = pn.get("description", "")
        pn_desc_upper = pn_desc.upper()

        # Calculate match score based on keywords
        pn_words = set(_extract_keywords(pn_desc))
        common_words = target_words & pn_words

        if not pn_words:
            word_score = 0.0
        else:
            word_score = len(common_words) / max(len(target_words), len(pn_words))

        # Bonus for exact part number in description
        if pn_code.upper() in target_upper:
            word_score += 0.3

        # Bonus for manufacturer match
        manufacturers = ["CISCO", "DELL", "HP", "HPE", "IBM", "LENOVO", "JUNIPER", "ARISTA"]
        for mfr in manufacturers:
            if mfr in target_upper and mfr in pn_desc_upper:
                word_score += 0.1
                break

        # Clamp score to 0.0-0.85 (reserve higher scores for AI-validated matches)
        word_score = min(0.85, word_score)

        if word_score > best_score:
            best_score = word_score
            best_match = {
                "part_number": pn_code,
                "description": pn_desc,
                "match_score": word_score,
            }

    # Only return if score is reasonable
    if best_match and best_score >= 0.5:
        return best_match

    # Fallback: return first candidate with low confidence
    if candidates:
        pn = candidates[0]
        return {
            "part_number": pn.get("part_number", pn.get("PK", "").replace("PN#", "")),
            "description": pn.get("description", ""),
            "match_score": 0.5,
        }

    return None


def _suggest_part_number(item: Dict[str, Any]) -> str:
    """
    Suggest a part number code for an unmatched item.

    Based on description and category patterns.
    """
    desc = item.get("descricao", "").upper()

    # Category-based suggestions
    if "SWITCH" in desc:
        return f"SW-{item.get('codigo', 'NEW')[:10]}"
    elif "ROUTER" in desc or "ROTEADOR" in desc:
        return f"RT-{item.get('codigo', 'NEW')[:10]}"
    elif "ACCESS POINT" in desc or " AP " in desc:
        return f"AP-{item.get('codigo', 'NEW')[:10]}"
    elif "CABO" in desc or "CABLE" in desc:
        return f"CBL-{item.get('codigo', 'NEW')[:10]}"
    elif "SFP" in desc:
        return f"SFP-{item.get('codigo', 'NEW')[:10]}"
    elif "SERVER" in desc or "SERVIDOR" in desc:
        return f"SRV-{item.get('codigo', 'NEW')[:10]}"
    else:
        return f"MISC-{item.get('codigo', 'NEW')[:10]}"
