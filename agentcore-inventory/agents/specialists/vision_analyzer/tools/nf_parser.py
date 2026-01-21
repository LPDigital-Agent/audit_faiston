"""
VisionAnalyzer NF-e Parser Tools

BUG-025 FIX: Brazilian NF-e (Nota Fiscal Eletrônica) specific parsing utilities.

Handles:
- CNPJ validation (Brazilian company ID)
- Access key validation (44 digits)
- Brazilian date format parsing (DD/MM/YYYY)
- Brazilian currency format parsing (R$ X.XXX,XX)

Note: These are pure Python validation functions.
The LLM handles extraction; these validate/normalize the results.
"""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def validate_cnpj(cnpj: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Brazilian CNPJ (Cadastro Nacional da Pessoa Jurídica).

    CNPJ format: XX.XXX.XXX/XXXX-XX (14 digits with formatting)

    Args:
        cnpj: CNPJ string (with or without formatting)

    Returns:
        Tuple of (is_valid, normalized_cnpj)
        - is_valid: True if CNPJ passes checksum validation
        - normalized_cnpj: Formatted CNPJ or None if invalid
    """
    # Remove non-digits
    digits = re.sub(r"[^\d]", "", cnpj)

    if len(digits) != 14:
        return False, None

    # CNPJ validation algorithm
    # First check digit
    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    sum1 = sum(int(d) * w for d, w in zip(digits[:12], weights1))
    check1 = 11 - (sum1 % 11)
    if check1 >= 10:
        check1 = 0

    if int(digits[12]) != check1:
        return False, None

    # Second check digit
    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    sum2 = sum(int(d) * w for d, w in zip(digits[:13], weights2))
    check2 = 11 - (sum2 % 11)
    if check2 >= 10:
        check2 = 0

    if int(digits[13]) != check2:
        return False, None

    # Format CNPJ
    formatted = f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"
    return True, formatted


def validate_access_key(access_key: str) -> Tuple[bool, Optional[str]]:
    """
    Validate NF-e access key (Chave de Acesso).

    Access key format: 44 numeric digits encoding:
    - UF code (2 digits)
    - Year/Month (4 digits: AAMM)
    - CNPJ (14 digits)
    - Model (2 digits, should be 55 for NF-e)
    - Series (3 digits)
    - Number (9 digits)
    - Emission type (1 digit)
    - Numeric code (8 digits)
    - Check digit (1 digit)

    Args:
        access_key: Access key string (with or without spaces)

    Returns:
        Tuple of (is_valid, normalized_key)
        - is_valid: True if access key passes validation
        - normalized_key: Cleaned key or None if invalid
    """
    # Remove non-digits
    digits = re.sub(r"[^\d]", "", access_key)

    if len(digits) != 44:
        return False, None

    # Validate check digit (mod 11)
    weights = [4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2,
               9, 8, 7, 6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2, 9, 8, 7,
               6, 5, 4, 3, 2]

    check_sum = sum(int(d) * w for d, w in zip(digits[:43], weights))
    remainder = check_sum % 11
    check_digit = 0 if remainder < 2 else 11 - remainder

    if int(digits[43]) != check_digit:
        return False, None

    return True, digits


def parse_brazilian_date(date_str: str) -> Optional[date]:
    """
    Parse Brazilian date format to Python date.

    Supported formats:
    - DD/MM/YYYY (most common)
    - DD-MM-YYYY
    - DD.MM.YYYY

    Args:
        date_str: Date string in Brazilian format

    Returns:
        Python date object or None if parsing fails
    """
    if not date_str:
        return None

    # Normalize separators
    normalized = re.sub(r"[-.]", "/", date_str.strip())

    try:
        # Try DD/MM/YYYY
        dt = datetime.strptime(normalized, "%d/%m/%Y")
        return dt.date()
    except ValueError:
        pass

    try:
        # Try DD/MM/YY
        dt = datetime.strptime(normalized, "%d/%m/%y")
        return dt.date()
    except ValueError:
        pass

    logger.warning("[NF Parser] Failed to parse date: %s", date_str)
    return None


def parse_brazilian_currency(value_str: str) -> Optional[Decimal]:
    """
    Parse Brazilian currency format to Decimal.

    Brazilian format: R$ X.XXX.XXX,XX
    - Thousands separator: . (dot)
    - Decimal separator: , (comma)
    - Currency symbol: R$ (optional)

    Args:
        value_str: Currency string in Brazilian format

    Returns:
        Decimal value or None if parsing fails
    """
    if not value_str:
        return None

    try:
        # Remove currency symbol and whitespace
        cleaned = re.sub(r"[R$\s]", "", value_str.strip())

        # Handle empty result
        if not cleaned:
            return None

        # Brazilian format: dots for thousands, comma for decimal
        # Convert to standard decimal format
        # First remove thousand separators (dots)
        cleaned = cleaned.replace(".", "")
        # Then convert decimal separator (comma) to dot
        cleaned = cleaned.replace(",", ".")

        return Decimal(cleaned)

    except (InvalidOperation, ValueError) as e:
        logger.warning("[NF Parser] Failed to parse currency '%s': %s", value_str, e)
        return None


def extract_nf_number(text: str) -> Optional[str]:
    """
    Extract NF-e number from text.

    Looks for patterns like:
    - "NF-e Nº 123456"
    - "Nota Fiscal: 123456"
    - "NF 123456"
    - "Número: 123456"

    Args:
        text: Text to search for NF number

    Returns:
        NF number string or None if not found
    """
    patterns = [
        r"NF-?e\s*(?:N[ºo°]?|:)?\s*(\d+)",
        r"Nota\s+Fiscal\s*(?:N[ºo°]?|:)?\s*(\d+)",
        r"NF\s*(?:N[ºo°]?|:)?\s*(\d+)",
        r"N[úu]mero\s*(?:da\s+NF)?:\s*(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def extract_cnpj_from_text(text: str) -> list:
    """
    Extract all CNPJ numbers from text.

    Args:
        text: Text to search for CNPJs

    Returns:
        List of tuples (raw_cnpj, is_valid, formatted_cnpj)
    """
    # Match CNPJ with or without formatting
    pattern = r"\d{2}[.\s]?\d{3}[.\s]?\d{3}[/\s]?\d{4}[-\s]?\d{2}"
    matches = re.findall(pattern, text)

    results = []
    for match in matches:
        is_valid, formatted = validate_cnpj(match)
        results.append((match, is_valid, formatted))

    return results


def normalize_nf_item(
    sequence: int,
    description: str,
    quantity: str,
    unit: str,
    unit_price: str,
    total_price: str,
) -> dict:
    """
    Normalize an NF-e item extracted by the LLM.

    Converts string values to proper types and validates.

    Args:
        sequence: Item sequence number
        description: Item description
        quantity: Quantity string (may include units)
        unit: Unit of measure
        unit_price: Unit price string (Brazilian format)
        total_price: Total price string (Brazilian format)

    Returns:
        Dict with normalized values ready for NFItem schema
    """
    # Parse quantity (may contain decimal with comma)
    qty_value = 0.0
    if quantity:
        qty_clean = re.sub(r"[^\d,.]", "", quantity)
        qty_clean = qty_clean.replace(",", ".")
        try:
            qty_value = float(qty_clean)
        except ValueError:
            qty_value = 0.0

    # Parse prices
    unit_price_dec = parse_brazilian_currency(unit_price)
    total_price_dec = parse_brazilian_currency(total_price)

    return {
        "sequence": sequence,
        "description": description.strip() if description else "",
        "quantity": qty_value,
        "unit": (unit or "UN").upper().strip(),
        "unit_price": float(unit_price_dec) if unit_price_dec else 0.0,
        "total_price": float(total_price_dec) if total_price_dec else 0.0,
    }
