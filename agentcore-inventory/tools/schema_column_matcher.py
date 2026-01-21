"""
Schema Column Matcher for SGA Inventory.

Dynamic column matcher that replaces hardcoded COLUMN_PATTERNS with
schema-aware matching. Uses PostgreSQL schema + built-in aliases +
learned aliases from AgentCore Memory.

Philosophy:
1. First, check exact match against schema columns
2. Then, check built-in aliases (Portuguese → English)
3. Then, check learned aliases (from user corrections)
4. Finally, fuzzy match with Levenshtein distance

Confidence Levels:
- Exact match to schema column: 0.98
- Built-in alias match: 0.85
- Learned alias match: 0.90 (higher trust in user-provided)
- Fuzzy match: 0.60-0.80 (based on similarity)

Author: Faiston NEXO Team
Date: January 2026
"""

import logging
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Built-in Aliases (Portuguese → PostgreSQL column names)
# =============================================================================

# These are common column name variations in Brazilian logistics/inventory
# Migrated from sheet_analyzer.py COLUMN_PATTERNS for continuity
BUILTIN_ALIASES: Dict[str, List[str]] = {
    # Part number / Material code
    "part_number": [
        "pn", "partnumber", "part_number", "codigo", "código",
        "cod_material", "codigo_material", "código_material",
        "material", "item", "sku", "codigo_item", "código_item",
        "equipamento", "equipment", "cod_equip", "código_equip",
        "cod", "codproduto", "cod_produto", "produto_codigo",
        "mat", "matl", "materialcode", "itemcode",
    ],

    # Description
    "description": [
        "desc", "descricao", "descrição", "descr",
        "nome", "nome_material", "desc_material",
        "produto", "produto_nome", "nome_produto",
        "item_desc", "item_description", "material_desc",
        "name", "product_name", "product_description",
    ],

    # Quantity
    "quantity": [
        "qty", "quantidade", "qtd", "quant",
        "quantity", "qtde", "qtdade",
        "total_qty", "total_quantidade",
        "unit_qty", "unidades",
    ],

    # Serial number
    "serial_number": [
        "serial", "sn", "serie", "série",
        "serial_number", "serialnumber",
        "num_serie", "número_série", "numero_serie",
        "ns", "serials", "asset_serial",
    ],

    # Serial numbers (array)
    "serial_numbers": [
        "seriais", "series", "séries",
        "numeros_serie", "números_série",
        "lista_seriais", "serial_list",
    ],

    # Location
    "location_code": [
        "loc", "local", "localizacao", "localização",
        "deposito", "depósito", "armazem", "armazém",
        "warehouse", "wh", "location", "location_code",
        "cod_local", "codigo_local", "código_local",
        "endereço", "endereco", "posicao", "posição",
    ],

    # Destination location
    "destination_location_id": [
        "destino", "loc_destino", "local_destino",
        "destination", "dest", "to_location",
        "deposito_destino", "armazem_destino",
    ],

    # Source location
    "source_location_id": [
        "origem", "loc_origem", "local_origem",
        "source", "from_location", "from",
        "deposito_origem", "armazem_origem",
    ],

    # Project
    "project_code": [
        "projeto", "project", "proj",
        "cod_projeto", "codigo_projeto", "código_projeto",
        "contrato", "contract", "cliente", "client",
        "obra", "site", "project_code",
    ],

    # NF Number
    "nf_number": [
        "nf", "nota_fiscal", "nf_number",
        "num_nf", "numero_nf", "número_nf",
        "invoice", "invoice_number",
        "danfe", "chave_nf",
    ],

    # NF Date
    "nf_date": [
        "data_nf", "dt_nf", "nf_date",
        "data_nota", "invoice_date",
        "data_emissao", "dt_emissao",
    ],

    # Supplier
    "supplier_name": [
        "fornecedor", "supplier", "vendor",
        "nome_fornecedor", "supplier_name",
        "razao_social", "razão_social",
        "emit", "emitente",
    ],

    # Unit cost / Value
    "unit_value": [
        "valor", "value", "preco", "preço",
        "unit_cost", "custo", "cost",
        "valor_unit", "valor_unitario", "valor_unitário",
        "price", "unit_price",
    ],

    # Total value
    "total_value": [
        "valor_total", "total", "total_value",
        "vl_total", "subtotal",
    ],

    # Unit of measure
    "unit_of_measure": [
        "unidade", "unit", "un", "uom",
        "unit_of_measure", "medida",
        "unid", "unidade_medida",
    ],

    # NCM (Brazilian product code)
    "ncm": [
        "ncm", "ncm_code", "codigo_ncm",
    ],

    # Status
    "status": [
        "status", "situacao", "situação",
        "estado", "state",
    ],

    # Movement type
    "movement_type": [
        "tipo", "type", "movimento", "movement",
        "tipo_mov", "tipo_movimento", "movement_type",
        "operacao", "operação", "operation",
    ],

    # Date (generic)
    "movement_date": [
        "data", "date", "dt",
        "data_mov", "data_movimento",
        "movement_date", "transaction_date",
    ],

    # Reason
    "reason": [
        "motivo", "reason", "justificativa",
        "observacao", "observação", "obs",
        "comments", "notes", "notas",
    ],

    # Condition
    "condition": [
        "condicao", "condição", "condition",
        "estado_conservacao", "estado",
    ],

    # Line number
    "line_number": [
        "linha", "line", "item_num",
        "seq", "sequencia", "sequência",
        "nitem", "num_item",
    ],
}


# =============================================================================
# Schema Column Matcher
# =============================================================================


class SchemaColumnMatcher:
    """
    Dynamic column matcher using schema + aliases.

    Replaces hardcoded COLUMN_PATTERNS with schema-aware matching.
    Supports learned aliases from user corrections.
    """

    def __init__(self, schema_provider=None):
        """
        Initialize the column matcher.

        Args:
            schema_provider: Optional SchemaProvider instance (lazy loaded if None)
        """
        self._schema_provider = schema_provider
        self._learned_aliases: Dict[str, str] = {}  # file_col → target_col
        logger.info("[SchemaColumnMatcher] Initialized")

    def _get_schema_provider(self):
        """Get or create SchemaProvider (lazy initialization)."""
        if self._schema_provider is None:
            from tools.schema_provider import get_schema_provider
            self._schema_provider = get_schema_provider()
        return self._schema_provider

    def _normalize(self, text: str) -> str:
        """
        Normalize text for matching.

        - Convert to lowercase
        - Remove accents
        - Replace special characters with underscore
        - Strip whitespace
        """
        if not text:
            return ""

        # Lowercase
        text = text.lower().strip()

        # Remove accents
        text = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in text if not unicodedata.combining(c))

        # Replace special characters
        text = re.sub(r"[^a-z0-9]", "_", text)
        text = re.sub(r"_+", "_", text)  # Collapse multiple underscores
        text = text.strip("_")

        return text

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)

        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # j+1 instead of j since previous_row and current_row are one character longer
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def _similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity ratio between two strings (0.0 to 1.0)."""
        if not s1 or not s2:
            return 0.0

        s1 = self._normalize(s1)
        s2 = self._normalize(s2)

        if s1 == s2:
            return 1.0

        max_len = max(len(s1), len(s2))
        if max_len == 0:
            return 0.0

        distance = self._levenshtein_distance(s1, s2)
        return 1.0 - (distance / max_len)

    def match_column(
        self,
        file_column: str,
        target_table: str = "pending_entry_items"
    ) -> Tuple[Optional[str], float]:
        """
        Match a file column to a schema column.

        Algorithm:
        1. Exact match to schema column → 0.98
        2. Built-in alias match → 0.85
        3. Learned alias match → 0.90
        4. Fuzzy match → 0.60-0.80

        Args:
            file_column: Column name from import file
            target_table: Target PostgreSQL table

        Returns:
            Tuple of (matched_column or None, confidence)
        """
        provider = self._get_schema_provider()
        schema = provider.get_table_schema(target_table)

        if not schema:
            logger.warning(f"[Matcher] Table '{target_table}' not found in schema")
            return None, 0.0

        normalized = self._normalize(file_column)
        schema_columns = schema.get_column_names()

        # 1. Exact match to schema column
        for col in schema_columns:
            if self._normalize(col) == normalized:
                logger.debug(f"[Matcher] Exact match: {file_column} → {col}")
                return col, 0.98

        # 2. Built-in alias match
        for target_col, aliases in BUILTIN_ALIASES.items():
            if target_col in schema_columns:
                for alias in aliases:
                    if self._normalize(alias) == normalized:
                        logger.debug(f"[Matcher] Alias match: {file_column} → {target_col}")
                        return target_col, 0.85

        # 3. Learned alias match
        if normalized in self._learned_aliases:
            learned_target = self._learned_aliases[normalized]
            if learned_target in schema_columns:
                logger.debug(f"[Matcher] Learned alias: {file_column} → {learned_target}")
                return learned_target, 0.90

        # 4. Fuzzy match
        best_match = None
        best_score = 0.0

        for col in schema_columns:
            sim = self._similarity(file_column, col)
            if sim > best_score and sim >= 0.60:
                best_score = sim
                best_match = col

        # Also check aliases for fuzzy match
        for target_col, aliases in BUILTIN_ALIASES.items():
            if target_col in schema_columns:
                for alias in aliases:
                    sim = self._similarity(file_column, alias)
                    if sim > best_score and sim >= 0.60:
                        best_score = sim
                        best_match = target_col

        if best_match:
            # Scale fuzzy confidence to 0.60-0.80 range
            confidence = 0.60 + (best_score - 0.60) * (0.20 / 0.40)
            confidence = min(confidence, 0.80)
            logger.debug(f"[Matcher] Fuzzy match: {file_column} → {best_match} ({confidence:.2f})")
            return best_match, confidence

        # No match found
        logger.debug(f"[Matcher] No match for: {file_column}")
        return None, 0.0

    def match_all_columns(
        self,
        file_columns: List[str],
        target_table: str = "pending_entry_items"
    ) -> Dict[str, Tuple[Optional[str], float]]:
        """
        Match multiple file columns to schema columns.

        Args:
            file_columns: List of column names from import file
            target_table: Target PostgreSQL table

        Returns:
            Dictionary mapping file_column → (target_column, confidence)
        """
        results = {}
        for col in file_columns:
            results[col] = self.match_column(col, target_table)
        return results

    def add_learned_alias(self, file_column: str, target_column: str) -> None:
        """
        Add a learned alias from user correction.

        Args:
            file_column: Original column name from file
            target_column: Correct target column
        """
        normalized = self._normalize(file_column)
        self._learned_aliases[normalized] = target_column
        logger.info(f"[Matcher] Learned alias: {file_column} → {target_column}")

    def load_learned_aliases(self, aliases: Dict[str, str]) -> None:
        """
        Load learned aliases from AgentCore Memory.

        Args:
            aliases: Dictionary of file_column → target_column
        """
        for file_col, target_col in aliases.items():
            self.add_learned_alias(file_col, target_col)
        logger.info(f"[Matcher] Loaded {len(aliases)} learned aliases")

    def get_unmapped_columns(
        self,
        file_columns: List[str],
        target_table: str = "pending_entry_items"
    ) -> List[str]:
        """
        Get columns that couldn't be matched to schema.

        Args:
            file_columns: List of column names from import file
            target_table: Target PostgreSQL table

        Returns:
            List of unmapped column names
        """
        unmapped = []
        for col in file_columns:
            target, confidence = self.match_column(col, target_table)
            if target is None or confidence < 0.60:
                unmapped.append(col)
        return unmapped

    def validate_mapping(
        self,
        mapping: Dict[str, str],
        target_table: str = "pending_entry_items"
    ) -> List[str]:
        """
        Validate that all target columns in mapping exist in schema.

        Args:
            mapping: Dictionary of file_column → target_column
            target_table: Target PostgreSQL table

        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        provider = self._get_schema_provider()
        schema = provider.get_table_schema(target_table)

        if not schema:
            return [f"Tabela '{target_table}' não encontrada no schema"]

        valid_columns = set(schema.get_column_names())

        for file_col, target_col in mapping.items():
            if target_col and target_col not in valid_columns:
                errors.append(
                    f"Coluna mapeada '{target_col}' (de '{file_col}') "
                    f"não existe em sga.{target_table}"
                )

        return errors

    def suggest_mappings(
        self,
        file_columns: List[str],
        target_table: str = "pending_entry_items",
        min_confidence: float = 0.60
    ) -> Dict[str, Dict[str, any]]:
        """
        Suggest column mappings with confidence scores.

        Returns a detailed suggestion dict for each column.

        Args:
            file_columns: List of column names from import file
            target_table: Target PostgreSQL table
            min_confidence: Minimum confidence threshold

        Returns:
            Dictionary with mapping suggestions:
            {
                "file_column": {
                    "target": "schema_column" or None,
                    "confidence": 0.0-1.0,
                    "match_type": "exact" | "alias" | "learned" | "fuzzy" | "none",
                    "needs_review": bool
                }
            }
        """
        suggestions = {}

        for col in file_columns:
            target, confidence = self.match_column(col, target_table)

            # Determine match type
            if confidence >= 0.98:
                match_type = "exact"
            elif confidence >= 0.90:
                match_type = "learned"
            elif confidence >= 0.85:
                match_type = "alias"
            elif confidence >= 0.60:
                match_type = "fuzzy"
            else:
                match_type = "none"

            suggestions[col] = {
                "target": target if confidence >= min_confidence else None,
                "confidence": round(confidence, 3),
                "match_type": match_type,
                "needs_review": confidence < 0.85 and confidence > 0.0,
            }

        return suggestions


# =============================================================================
# Helper Functions
# =============================================================================


def get_column_matcher(schema_provider=None) -> SchemaColumnMatcher:
    """
    Get a SchemaColumnMatcher instance.

    Args:
        schema_provider: Optional SchemaProvider instance

    Returns:
        SchemaColumnMatcher instance
    """
    return SchemaColumnMatcher(schema_provider)
