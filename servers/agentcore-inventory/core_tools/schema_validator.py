"""
Schema Validator for SGA Inventory.

Pre-execution validation layer that ensures all column mappings are valid
against the PostgreSQL schema before import execution. Catches errors
BEFORE they hit the database, providing clear feedback to users.

Philosophy: VALIDATE BEFORE ACT
1. Check target columns exist in schema
2. Check required columns (NOT NULL) are mapped
3. Check ENUM values in sample data are valid
4. Check data types are compatible
5. Check FK references can be resolved

Validation Levels:
- ERRORS: Fatal - will fail on INSERT (must be fixed)
- WARNINGS: Non-fatal - may cause data issues (should be reviewed)
- SUGGESTIONS: AI recommendations for improvement

Author: Faiston NEXO Team
Date: January 2026
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Validation Result Data Classes
# =============================================================================


@dataclass
class ValidationIssue:
    """
    Single validation issue with context.

    Used for detailed error/warning reporting.
    """
    field: str              # Column or field name
    issue_type: str         # e.g., "missing_column", "invalid_enum"
    message: str            # Human-readable message (Portuguese)
    severity: str           # "error", "warning", "suggestion"
    sample_value: Optional[str] = None  # Problematic value if applicable
    expected: Optional[str] = None      # Expected value/format


@dataclass
class ValidationResult:
    """
    Complete validation result for a mapping configuration.

    Aggregates all errors, warnings, and suggestions.
    """
    is_valid: bool                              # True if no errors (warnings ok)
    errors: List[ValidationIssue] = field(default_factory=list)     # Fatal
    warnings: List[ValidationIssue] = field(default_factory=list)   # Non-fatal
    suggestions: List[ValidationIssue] = field(default_factory=list)  # Recommendations
    validated_mappings: Dict[str, str] = field(default_factory=dict)  # Clean mappings
    coverage_score: float = 0.0                 # % of file columns mapped
    required_coverage: float = 0.0              # % of required columns mapped

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_valid": self.is_valid,
            "errors": [self._issue_to_dict(e) for e in self.errors],
            "warnings": [self._issue_to_dict(w) for w in self.warnings],
            "suggestions": [self._issue_to_dict(s) for s in self.suggestions],
            "validated_mappings": self.validated_mappings,
            "coverage_score": round(self.coverage_score, 2),
            "required_coverage": round(self.required_coverage, 2),
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }

    def _issue_to_dict(self, issue: ValidationIssue) -> Dict[str, Any]:
        """Convert ValidationIssue to dict."""
        return {
            "field": issue.field,
            "issue_type": issue.issue_type,
            "message": issue.message,
            "severity": issue.severity,
            "sample_value": issue.sample_value,
            "expected": issue.expected,
        }


# =============================================================================
# Schema Validator
# =============================================================================


class SchemaValidator:
    """
    Pre-execution validator against PostgreSQL schema.

    Validates column mappings, data types, ENUM values, and FK references
    before import execution. Catches errors BEFORE they hit the database.

    Usage:
        validator = SchemaValidator()
        result = validator.validate_mappings(
            column_mappings={"Código": "part_number", "Qtd": "quantity"},
            target_table="pending_entry_items",
            sample_data=[{"Código": "ABC123", "Qtd": "10"}]
        )
        if not result.is_valid:
            for error in result.errors:
                logger.error("ERRO: %s", error.message)
    """

    def __init__(self, schema_provider=None):
        """
        Initialize the validator.

        Args:
            schema_provider: Optional SchemaProvider instance (lazy loaded if None)
        """
        self._schema_provider = schema_provider
        logger.info("[SchemaValidator] Initialized")

    def _get_schema_provider(self):
        """Get or create SchemaProvider (lazy initialization)."""
        if self._schema_provider is None:
            from core_tools.schema_provider import get_schema_provider
            self._schema_provider = get_schema_provider()
        return self._schema_provider

    def validate_mappings(
        self,
        column_mappings: Dict[str, str],
        target_table: str = "pending_entry_items",
        sample_data: Optional[List[Dict[str, Any]]] = None,
        required_fields_override: Optional[List[str]] = None,
    ) -> ValidationResult:
        """
        Comprehensive validation of column mappings against schema.

        Performs 5 validation checks:
        1. Target columns exist in schema
        2. Required columns (NOT NULL) are mapped
        3. ENUM values in sample data are valid
        4. Data types are compatible
        5. FK references can be resolved (basic check)

        Args:
            column_mappings: Dict mapping file_column → target_column
            target_table: PostgreSQL target table name
            sample_data: Optional list of sample rows for value validation
            required_fields_override: Optional list to override required columns

        Returns:
            ValidationResult with errors, warnings, and suggestions
        """
        errors: List[ValidationIssue] = []
        warnings: List[ValidationIssue] = []
        suggestions: List[ValidationIssue] = []
        validated_mappings: Dict[str, str] = {}

        provider = self._get_schema_provider()
        schema = provider.get_table_schema(target_table)

        if not schema:
            errors.append(ValidationIssue(
                field=target_table,
                issue_type="table_not_found",
                message=f"Tabela '{target_table}' não encontrada no schema PostgreSQL",
                severity="error",
            ))
            return ValidationResult(
                is_valid=False,
                errors=errors,
            )

        schema_columns = set(schema.get_column_names())
        required_columns = set(
            required_fields_override
            if required_fields_override
            else schema.required_columns
        )

        # Get ENUM info for validation
        all_enums = provider.get_all_enums()

        # Track which schema columns are mapped
        mapped_schema_columns: Set[str] = set()

        # =================================================================
        # 0. Filter out placeholder values (defense-in-depth)
        # =================================================================
        # FIX (January 2026): "__other__" is a frontend placeholder for the "Outros"
        # radio option. It should be replaced with actual text before reaching backend.
        # This check catches any that slip through due to race conditions.
        INVALID_PLACEHOLDERS = {"__other__", "_other_", "OTHER", "__skip__", "__none__"}

        for file_col, target_col in list(column_mappings.items()):
            if target_col in INVALID_PLACEHOLDERS:
                errors.append(ValidationIssue(
                    field=file_col,
                    issue_type="invalid_placeholder",
                    message=(
                        f"Coluna '{file_col}' não existe em sga.{target_table}"
                    ),
                    severity="error",
                    sample_value=target_col,
                    expected="Nome válido de coluna PostgreSQL",
                ))
                # Remove from mappings to prevent further validation errors
                del column_mappings[file_col]
                logger.warning(
                    f"[SchemaValidator] Filtered invalid placeholder '{target_col}' "
                    f"for file column '{file_col}'"
                )

        # =================================================================
        # 0.5 Handle NEXO special markers (FIX January 2026)
        # =================================================================
        # These are special values used by NEXO import flow that should NOT be
        # validated against PostgreSQL schema - they have special meaning:
        # - "_ignore" → User explicitly chose to skip this column
        # - "__new_column__:xxx" → Pending column creation (needs HIL approval)
        # - "__create_column__:xxx" → Approved column creation (create during import)
        # - "__custom_fields__" → Store in JSONB custom_fields column (legacy)
        # - "__metadata__" → Store in JSONB metadata column (new schema evolution)
        # - "__ai_pending__:xxx" → Waiting for AI interpretation (should be resolved)
        pending_new_columns = []  # Track columns pending creation

        for file_col, target_col in list(column_mappings.items()):
            # Skip ignored columns - remove from mappings entirely
            if target_col == "_ignore":
                del column_mappings[file_col]
                logger.info(f"[SchemaValidator] Ignoring column '{file_col}' per user request")
                continue

            # Handle pending column creation - these need HIL approval first!
            if target_col.startswith("__new_column__:"):
                new_col_name = target_col.split(":", 1)[1]
                pending_new_columns.append({
                    "file_column": file_col,
                    "suggested_name": new_col_name,
                    "marker": target_col,
                })
                del column_mappings[file_col]
                logger.warning(
                    f"[SchemaValidator] Column '{file_col}' pending creation as '{new_col_name}' "
                    f"- requires HIL approval"
                )
                continue

            # Handle approved column creation - should have been created by now
            if target_col.startswith("__create_column__:"):
                new_col_name = target_col.split(":", 1)[1]
                # Check if column was actually created
                if new_col_name in schema_columns:
                    column_mappings[file_col] = new_col_name  # Replace marker with actual name
                    logger.info(f"[SchemaValidator] Using created column '{new_col_name}'")
                else:
                    pending_new_columns.append({
                        "file_column": file_col,
                        "suggested_name": new_col_name,
                        "marker": target_col,
                        "approved": True,
                    })
                    del column_mappings[file_col]
                    logger.warning(
                        f"[SchemaValidator] Approved column '{new_col_name}' not yet created"
                    )
                continue

            # Handle custom_fields JSONB storage (legacy)
            if target_col == "__custom_fields__":
                if "custom_fields" in schema_columns:
                    column_mappings[file_col] = "custom_fields"
                    logger.info(f"[SchemaValidator] Storing '{file_col}' in custom_fields JSONB")
                else:
                    warnings.append(ValidationIssue(
                        field=file_col,
                        issue_type="no_custom_fields",
                        message=f"Cannot store '{file_col}' in custom_fields - column doesn't exist",
                        severity="warning",
                    ))
                    del column_mappings[file_col]
                continue

            # Handle metadata JSONB storage (new schema evolution pattern)
            if target_col == "__metadata__":
                if "metadata" in schema_columns:
                    # Track that metadata column is being used
                    # The import executor will aggregate all __metadata__ fields into
                    # a single JSONB object in the metadata column
                    mapped_schema_columns.add("metadata")
                    # Store in validated_mappings with special marker for executor
                    validated_mappings[file_col] = "__metadata__"
                    logger.info(f"[SchemaValidator] Storing '{file_col}' in metadata JSONB")
                else:
                    warnings.append(ValidationIssue(
                        field=file_col,
                        issue_type="no_metadata_column",
                        message=(
                            f"Cannot store '{file_col}' in metadata - column doesn't exist. "
                            f"Run migration 006_schema_evolution.sql to add it."
                        ),
                        severity="warning",
                    ))
                # Remove from column_mappings to skip normal column validation
                del column_mappings[file_col]
                continue

            # Handle unresolved AI pending markers - should have been resolved!
            if target_col.startswith("__ai_pending__:"):
                errors.append(ValidationIssue(
                    field=file_col,
                    issue_type="unresolved_ai",
                    message=(
                        f"Coluna '{file_col}' aguardando interpretação AI que não foi completada. "
                        f"Por favor, responda as perguntas novamente."
                    ),
                    severity="error",
                ))
                del column_mappings[file_col]
                continue

            # =================================================================
            # FIX (January 2026): Handle auto-generation markers
            # These special markers indicate required fields that will be
            # computed/generated during import, not mapped from CSV.
            # =================================================================

            # Handle aggregated quantity - computed from row counts by part_number
            if file_col == "__quantity_aggregated__" and target_col == "quantity":
                mapped_schema_columns.add("quantity")
                del column_mappings[file_col]  # Remove marker, keep in mapped_schema_columns
                logger.info(
                    "[SchemaValidator] quantity will be computed via aggregation"
                )
                continue

            # Handle quantity = 1 for all items
            if file_col == "__quantity_one__" and target_col == "quantity":
                mapped_schema_columns.add("quantity")
                del column_mappings[file_col]
                logger.info(
                    "[SchemaValidator] quantity will be set to 1 for all items"
                )
                continue

            # Handle auto-created entry_id (creates parent pending_entries record)
            if file_col == "__entry_id_auto__" and target_col == "entry_id":
                mapped_schema_columns.add("entry_id")
                del column_mappings[file_col]
                logger.info(
                    "[SchemaValidator] entry_id will be auto-created with BULK_IMPORT entry"
                )
                continue

            # Handle auto-incremented line_number
            if file_col == "__line_number_auto__" and target_col == "line_number":
                mapped_schema_columns.add("line_number")
                del column_mappings[file_col]
                logger.info(
                    "[SchemaValidator] line_number will be auto-incremented"
                )
                continue

        # If there are pending column creations, return error asking for HIL approval
        if pending_new_columns:
            for pending in pending_new_columns:
                errors.append(ValidationIssue(
                    field=pending["file_column"],
                    issue_type="pending_column_creation",
                    message=(
                        f"Coluna '{pending['file_column']}' requer criação do campo "
                        f"'{pending['suggested_name']}' no banco de dados. "
                        f"Aguardando aprovação do administrador."
                    ),
                    severity="error",
                    expected="Aprovação de criação de coluna",
                ))

        # =================================================================
        # 1. Validate target columns exist
        # =================================================================
        for file_col, target_col in column_mappings.items():
            if not target_col:
                continue  # Skip unmapped columns

            if target_col not in schema_columns:
                errors.append(ValidationIssue(
                    field=file_col,
                    issue_type="invalid_target",
                    message=(
                        f"Coluna mapeada '{target_col}' não existe em "
                        f"sga.{target_table}"
                    ),
                    severity="error",
                    expected=", ".join(sorted(schema_columns)[:10]) + "...",
                ))
            else:
                validated_mappings[file_col] = target_col
                mapped_schema_columns.add(target_col)

        # =================================================================
        # 2. Check required columns are mapped
        # =================================================================
        unmapped_required = required_columns - mapped_schema_columns

        # Exclude auto-generated columns from required check
        auto_generated = {"created_at", "updated_at", "id", "entry_item_id"}
        unmapped_required -= auto_generated

        for col in unmapped_required:
            col_info = schema.get_column(col)
            has_default = col_info and col_info.default_value is not None

            if not has_default:
                errors.append(ValidationIssue(
                    field=col,
                    issue_type="missing_required",
                    message=(
                        f"Coluna obrigatória '{col}' não está mapeada. "
                        f"Este campo é NOT NULL e não tem valor padrão."
                    ),
                    severity="error",
                ))

        # =================================================================
        # 3. Validate ENUM values in sample data
        # =================================================================
        if sample_data:
            enum_columns = {
                col.name: col.udt_name
                for col in schema.columns
                if col.udt_name in all_enums
            }

            for file_col, target_col in validated_mappings.items():
                if target_col in enum_columns:
                    enum_name = enum_columns[target_col]
                    valid_values = set(all_enums[enum_name])

                    # Check sample values
                    invalid_values = set()
                    for row in sample_data[:10]:  # Check first 10 rows
                        value = row.get(file_col)
                        if value and str(value).upper() not in {
                            v.upper() for v in valid_values
                        }:
                            invalid_values.add(str(value))

                    if invalid_values:
                        errors.append(ValidationIssue(
                            field=file_col,
                            issue_type="invalid_enum",
                            message=(
                                f"Valores inválidos para '{target_col}': "
                                f"{', '.join(list(invalid_values)[:3])}"
                            ),
                            severity="error",
                            sample_value=list(invalid_values)[0],
                            expected=", ".join(valid_values),
                        ))

        # =================================================================
        # 4. Validate data types (basic check with sample data)
        # =================================================================
        if sample_data:
            type_issues = self._validate_data_types(
                validated_mappings,
                schema,
                sample_data,
            )
            for issue in type_issues:
                if issue.severity == "error":
                    errors.append(issue)
                else:
                    warnings.append(issue)

        # =================================================================
        # 5. Check FK references (basic existence check)
        # =================================================================
        fk_issues = self._validate_foreign_keys(
            validated_mappings,
            schema,
            sample_data,
        )
        for issue in fk_issues:
            if issue.severity == "error":
                warnings.append(issue)  # FK issues are warnings, not blockers
            else:
                suggestions.append(issue)

        # =================================================================
        # Generate suggestions
        # =================================================================
        suggestions.extend(self._generate_suggestions(
            column_mappings,
            validated_mappings,
            schema,
            schema_columns,
        ))

        # =================================================================
        # Calculate coverage scores
        # =================================================================
        total_file_columns = len([c for c in column_mappings.keys() if c])
        mapped_count = len(validated_mappings)
        coverage_score = (
            mapped_count / total_file_columns * 100
            if total_file_columns > 0 else 0
        )

        required_count = len(required_columns - auto_generated)
        mapped_required = len(
            (required_columns - auto_generated) & mapped_schema_columns
        )
        required_coverage = (
            mapped_required / required_count * 100
            if required_count > 0 else 100
        )

        # =================================================================
        # Build result
        # =================================================================
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
            validated_mappings=validated_mappings,
            coverage_score=coverage_score,
            required_coverage=required_coverage,
        )

    def _validate_data_types(
        self,
        mappings: Dict[str, str],
        schema,
        sample_data: List[Dict[str, Any]],
    ) -> List[ValidationIssue]:
        """
        Validate data types in sample data against schema expectations.

        Args:
            mappings: Validated column mappings
            schema: TableSchema object
            sample_data: Sample data rows

        Returns:
            List of validation issues
        """
        issues = []

        for file_col, target_col in mappings.items():
            col_info = schema.get_column(target_col)
            if not col_info:
                continue

            data_type = col_info.data_type.lower()

            for i, row in enumerate(sample_data[:5]):
                value = row.get(file_col)
                if value is None or value == "":
                    continue

                value_str = str(value)

                # Integer validation
                if data_type in ("integer", "bigint", "smallint"):
                    if not self._is_integer(value_str):
                        issues.append(ValidationIssue(
                            field=file_col,
                            issue_type="type_mismatch",
                            message=(
                                f"Valor '{value_str}' não é um inteiro válido "
                                f"para coluna '{target_col}'"
                            ),
                            severity="warning",
                            sample_value=value_str,
                            expected="Número inteiro",
                        ))
                        break  # One error per column is enough

                # Numeric/Decimal validation
                elif data_type in ("numeric", "decimal", "real", "double precision"):
                    if not self._is_numeric(value_str):
                        issues.append(ValidationIssue(
                            field=file_col,
                            issue_type="type_mismatch",
                            message=(
                                f"Valor '{value_str}' não é numérico válido "
                                f"para coluna '{target_col}'"
                            ),
                            severity="warning",
                            sample_value=value_str,
                            expected="Número decimal",
                        ))
                        break

                # Date validation
                elif data_type in ("date", "timestamp", "timestamp without time zone"):
                    if not self._is_date(value_str):
                        issues.append(ValidationIssue(
                            field=file_col,
                            issue_type="type_mismatch",
                            message=(
                                f"Valor '{value_str}' não é uma data válida "
                                f"para coluna '{target_col}'"
                            ),
                            severity="warning",
                            sample_value=value_str,
                            expected="Data (dd/mm/yyyy ou yyyy-mm-dd)",
                        ))
                        break

                # VARCHAR length validation
                elif "character varying" in data_type and col_info.max_length:
                    if len(value_str) > col_info.max_length:
                        issues.append(ValidationIssue(
                            field=file_col,
                            issue_type="value_too_long",
                            message=(
                                f"Valor com {len(value_str)} caracteres excede "
                                f"limite de {col_info.max_length} para '{target_col}'"
                            ),
                            severity="warning",
                            sample_value=value_str[:50] + "...",
                            expected=f"Máximo {col_info.max_length} caracteres",
                        ))
                        break

        return issues

    def _validate_foreign_keys(
        self,
        mappings: Dict[str, str],
        schema,
        sample_data: Optional[List[Dict[str, Any]]],
    ) -> List[ValidationIssue]:
        """
        Basic FK validation - checks if mapped columns have FK constraints.

        Full FK resolution would require database queries for each value,
        which is too expensive for validation. This just warns about FK columns.

        Args:
            mappings: Validated column mappings
            schema: TableSchema object
            sample_data: Sample data rows

        Returns:
            List of validation issues (suggestions)
        """
        issues = []

        fk_columns = {
            col.name: col.fk_reference
            for col in schema.columns
            if col.is_foreign_key
        }

        for file_col, target_col in mappings.items():
            if target_col in fk_columns:
                fk_ref = fk_columns[target_col]
                issues.append(ValidationIssue(
                    field=file_col,
                    issue_type="fk_reference",
                    message=(
                        f"Coluna '{target_col}' é uma chave estrangeira para "
                        f"{fk_ref}. Valores devem existir na tabela referenciada."
                    ),
                    severity="suggestion",
                    expected=f"ID válido em {fk_ref}",
                ))

        return issues

    def _generate_suggestions(
        self,
        original_mappings: Dict[str, str],
        validated_mappings: Dict[str, str],
        schema,
        schema_columns: Set[str],
    ) -> List[ValidationIssue]:
        """
        Generate suggestions for improving the mapping.

        Args:
            original_mappings: Original mapping request
            validated_mappings: Validated (clean) mappings
            schema: TableSchema object
            schema_columns: Set of valid column names

        Returns:
            List of suggestions
        """
        suggestions = []

        # Find unmapped file columns
        unmapped_file_cols = [
            col for col, target in original_mappings.items()
            if not target
        ]

        if unmapped_file_cols:
            suggestions.append(ValidationIssue(
                field="unmapped",
                issue_type="unmapped_columns",
                message=(
                    f"{len(unmapped_file_cols)} colunas do arquivo não foram "
                    f"mapeadas: {', '.join(unmapped_file_cols[:5])}"
                    f"{'...' if len(unmapped_file_cols) > 5 else ''}"
                ),
                severity="suggestion",
            ))

        # Find unmapped schema columns that might be useful
        mapped_schema = set(validated_mappings.values())
        useful_unmapped = {"description", "serial_number", "project_code",
                          "location_code", "supplier_name", "nf_number"}
        missing_useful = useful_unmapped - mapped_schema

        if missing_useful:
            suggestions.append(ValidationIssue(
                field="recommended",
                issue_type="recommended_columns",
                message=(
                    f"Considere mapear estas colunas úteis: "
                    f"{', '.join(missing_useful)}"
                ),
                severity="suggestion",
            ))

        return suggestions

    def _is_integer(self, value: str) -> bool:
        """Check if string represents an integer."""
        try:
            # Handle Brazilian number format (1.000 = 1000)
            cleaned = value.replace(".", "").replace(",", ".")
            int(float(cleaned))
            return True
        except (ValueError, TypeError):
            return False

    def _is_numeric(self, value: str) -> bool:
        """Check if string represents a numeric value."""
        try:
            # Handle Brazilian number format (1.234,56 = 1234.56)
            cleaned = value.replace(".", "").replace(",", ".")
            Decimal(cleaned)
            return True
        except (InvalidOperation, ValueError, TypeError):
            return False

    def _is_date(self, value: str) -> bool:
        """Check if string represents a valid date."""
        date_formats = [
            "%d/%m/%Y",
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%y",
            "%Y/%m/%d",
            "%d.%m.%Y",
        ]

        for fmt in date_formats:
            try:
                datetime.strptime(value.strip(), fmt)
                return True
            except ValueError:
                continue

        return False

    def quick_validate(
        self,
        column_mappings: Dict[str, str],
        target_table: str = "pending_entry_items",
    ) -> Tuple[bool, List[str]]:
        """
        Quick validation without sample data.

        Just checks if target columns exist in schema.

        Args:
            column_mappings: Dict mapping file_column → target_column
            target_table: PostgreSQL target table name

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        provider = self._get_schema_provider()
        schema = provider.get_table_schema(target_table)

        if not schema:
            return False, [f"Tabela '{target_table}' não encontrada"]

        schema_columns = set(schema.get_column_names())
        errors = []

        for file_col, target_col in column_mappings.items():
            if target_col and target_col not in schema_columns:
                errors.append(
                    f"Coluna '{target_col}' não existe em sga.{target_table}"
                )

        return len(errors) == 0, errors


# =============================================================================
# Helper Functions
# =============================================================================


def get_schema_validator(schema_provider=None) -> SchemaValidator:
    """
    Get a SchemaValidator instance.

    Args:
        schema_provider: Optional SchemaProvider instance

    Returns:
        SchemaValidator instance
    """
    return SchemaValidator(schema_provider)


def validate_before_import(
    column_mappings: Dict[str, str],
    target_table: str,
    sample_data: Optional[List[Dict[str, Any]]] = None,
) -> ValidationResult:
    """
    Convenience function for pre-import validation.

    Args:
        column_mappings: Dict mapping file_column → target_column
        target_table: PostgreSQL target table name
        sample_data: Optional sample rows for value validation

    Returns:
        ValidationResult
    """
    validator = get_schema_validator()
    return validator.validate_mappings(
        column_mappings=column_mappings,
        target_table=target_table,
        sample_data=sample_data,
    )
