# =============================================================================
# NF Parser for SGA Inventory
# =============================================================================
# Parser for Brazilian NF (Nota Fiscal Eletrônica) documents.
#
# Features:
# - XML parsing with stdlib ElementTree (no external dependencies)
# - PDF text extraction support (via AI)
# - Serial number extraction from descriptions
# - Confidence scoring for extraction quality
#
# CRITICAL: Uses only Python stdlib for cold start optimization (<30s limit)
# NOTE: Replaced lxml with xml.etree.ElementTree to comply with CLAUDE.md rules
#       (lxml is a heavy C extension that violates cold start requirements)
# =============================================================================

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import re
import xml.etree.ElementTree as ET


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class NFItem:
    """
    Represents a single item from an NF.

    Attributes:
        item_number: Sequential item number in the NF
        part_number: Product code (cProd)
        description: Product description (xProd)
        ncm: NCM code (Nomenclatura Comum do Mercosul)
        cfop: CFOP code (Código Fiscal de Operações)
        quantity: Item quantity
        unit: Unit of measure
        unit_price: Unit price
        total_price: Total price (quantity * unit_price)
        serial_numbers: Extracted serial numbers (if found)
    """
    item_number: int
    part_number: str
    description: str
    ncm: str = ""
    cfop: str = ""
    quantity: float = 0.0
    unit: str = "UN"
    unit_price: float = 0.0
    total_price: float = 0.0
    serial_numbers: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "item_number": self.item_number,
            "part_number": self.part_number,
            "description": self.description,
            "ncm": self.ncm,
            "cfop": self.cfop,
            "quantity": self.quantity,
            "unit": self.unit,
            "unit_price": self.unit_price,
            "total_price": self.total_price,
            "serial_numbers": self.serial_numbers,
        }


@dataclass
class NFExtraction:
    """
    Complete extraction result from an NF document.

    Attributes:
        nf_number: NF number (nNF)
        nf_series: NF series
        nf_key: Access key (44 digits)
        nf_date: Issue date
        nature_operation: Nature of operation (natOp)
        supplier_cnpj: Supplier CNPJ
        supplier_name: Supplier name
        supplier_ie: Supplier state registration
        recipient_cnpj: Recipient CNPJ
        recipient_name: Recipient name
        total_value: Total NF value
        items: List of extracted items
        confidence: Extraction confidence metrics
        raw_xml: Original XML content (if available)
        errors: List of extraction errors/warnings
    """
    nf_number: str = ""
    nf_series: str = ""
    nf_key: str = ""
    nf_date: str = ""
    nature_operation: str = ""
    supplier_cnpj: str = ""
    supplier_name: str = ""
    supplier_ie: str = ""
    recipient_cnpj: str = ""
    recipient_name: str = ""
    total_value: float = 0.0
    items: List[NFItem] = field(default_factory=list)
    confidence: Dict[str, float] = field(default_factory=dict)
    raw_xml: Optional[str] = None
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "nf_number": self.nf_number,
            "nf_series": self.nf_series,
            "nf_key": self.nf_key,
            "nf_date": self.nf_date,
            "nature_operation": self.nature_operation,
            "supplier_cnpj": self.supplier_cnpj,
            "supplier_name": self.supplier_name,
            "supplier_ie": self.supplier_ie,
            "recipient_cnpj": self.recipient_cnpj,
            "recipient_name": self.recipient_name,
            "total_value": self.total_value,
            "items": [item.to_dict() for item in self.items],
            "confidence": self.confidence,
            "errors": self.errors,
            "item_count": len(self.items),
            "total_quantity": sum(item.quantity for item in self.items),
        }


# =============================================================================
# NF Parser Class
# =============================================================================


class NFParser:
    """
    Parser for Brazilian NF (Nota Fiscal Eletrônica) documents.

    Supports:
    - XML format (standard NF)
    - PDF text extraction (via AI prompts)

    Example:
        parser = NFParser()
        extraction = parser.parse_xml(xml_content)
    """

    # NF XML namespaces
    NAMESPACES = {
        "nfe": "http://www.portalfiscal.inf.br/nfe",
    }

    # Common serial number patterns in Brazilian inventory
    SERIAL_PATTERNS = [
        r"S/?N[:\s]*([A-Z0-9]{5,20})",  # S/N: ABC123
        r"SERIAL[:\s]*([A-Z0-9]{5,20})",  # SERIAL: ABC123
        r"SN[:\s]*([A-Z0-9]{5,20})",  # SN: ABC123
        r"N[ºo°]?\s*S[ée]rie[:\s]*([A-Z0-9]{5,20})",  # Nº Série: ABC123
        r"\b([A-Z]{2,4}[0-9]{6,12})\b",  # Generic: XX123456
    ]

    def __init__(self):
        """Initialize the NF parser."""
        self._compiled_patterns = None

    @property
    def serial_patterns(self):
        """Lazily compile serial number regex patterns."""
        if self._compiled_patterns is None:
            self._compiled_patterns = [
                re.compile(p, re.IGNORECASE)
                for p in self.SERIAL_PATTERNS
            ]
        return self._compiled_patterns

    # =========================================================================
    # XML Parsing
    # =========================================================================

    def parse_xml(self, xml_content: str) -> NFExtraction:
        """
        Parse NF XML content.

        Args:
            xml_content: XML string content

        Returns:
            NFExtraction with parsed data
        """
        extraction = NFExtraction(raw_xml=xml_content)

        try:
            # Parse XML using stdlib ElementTree
            root = ET.fromstring(xml_content)

            # Try to find infNFe with namespace first, then without
            # NF standard namespace
            nfe_ns = "{http://www.portalfiscal.inf.br/nfe}"

            infNFe = root.find(f".//{nfe_ns}infNFe")
            if infNFe is None:
                # Try without namespace (some files don't have it)
                infNFe = root.find(".//infNFe")
            if infNFe is None:
                # Try as direct child
                for elem in root.iter():
                    if elem.tag.endswith("infNFe"):
                        infNFe = elem
                        break

            if infNFe is None:
                extraction.errors.append("Could not find infNFe element")
                extraction.confidence = {"overall": 0.0}
                return extraction

            # Detect namespace from found element
            self._detected_ns = ""
            if infNFe.tag.startswith("{"):
                self._detected_ns = infNFe.tag.split("}")[0] + "}"

            # Extract NF key from Id attribute
            nf_id = infNFe.get("Id", "")
            if nf_id.startswith("NFe"):
                extraction.nf_key = nf_id[3:]  # Remove "NFe" prefix

            # Parse identification (ide)
            self._parse_ide(infNFe, extraction)

            # Parse emitter (emit)
            self._parse_emit(infNFe, extraction)

            # Parse recipient (dest)
            self._parse_dest(infNFe, extraction)

            # Parse items (det)
            self._parse_items(infNFe, extraction)

            # Parse totals
            self._parse_totals(infNFe, extraction)

            # Calculate confidence
            extraction.confidence = self._calculate_confidence(extraction)

        except Exception as e:
            extraction.errors.append(f"XML parsing error: {str(e)}")
            extraction.confidence = {"overall": 0.0}

        return extraction

    def _find_element(self, parent, path: str) -> Optional[Any]:
        """Find element with or without namespace."""
        # Use detected namespace from parse_xml
        ns = getattr(self, "_detected_ns", "")

        # Try with detected namespace
        if ns:
            elem = parent.find(f".//{ns}{path}")
            if elem is not None:
                return elem

        # Try without namespace
        elem = parent.find(f".//{path}")
        if elem is not None:
            return elem

        # Try to find by tag suffix (handles any namespace)
        for elem in parent.iter():
            if elem.tag.endswith(path) or elem.tag == path:
                return elem

        return None

    def _get_text(self, parent, path: str, default: str = "") -> str:
        """
        Get text content of element, supporting nested paths like 'ide/nNF'.

        Args:
            parent: Parent element to search from
            path: Path to element (e.g., 'ide/nNF' or 'emit/CNPJ')
            default: Default value if not found

        Returns:
            Text content of the element or default
        """
        ns = getattr(self, "_detected_ns", "")
        parts = path.split("/")

        current = parent
        for part in parts:
            found = None
            # Try with namespace
            if ns:
                found = current.find(f"{ns}{part}")
            # Try without namespace
            if found is None:
                found = current.find(part)
            # Try by suffix
            if found is None:
                for child in current:
                    if child.tag.endswith(part):
                        found = child
                        break
            if found is None:
                return default
            current = found

        return current.text.strip() if current is not None and current.text else default

    def _parse_ide(self, infNFe, extraction: NFExtraction) -> None:
        """Parse identification (ide) section."""
        extraction.nf_number = self._get_text(infNFe, "ide/nNF")
        extraction.nf_series = self._get_text(infNFe, "ide/serie")
        extraction.nf_date = self._get_text(infNFe, "ide/dhEmi")[:10]  # Just date part
        extraction.nature_operation = self._get_text(infNFe, "ide/natOp")

    def _parse_emit(self, infNFe, extraction: NFExtraction) -> None:
        """Parse emitter (emit) section."""
        extraction.supplier_cnpj = self._get_text(infNFe, "emit/CNPJ")
        extraction.supplier_name = self._get_text(infNFe, "emit/xNome")
        extraction.supplier_ie = self._get_text(infNFe, "emit/IE")

    def _parse_dest(self, infNFe, extraction: NFExtraction) -> None:
        """Parse recipient (dest) section."""
        extraction.recipient_cnpj = self._get_text(infNFe, "dest/CNPJ")
        extraction.recipient_name = self._get_text(infNFe, "dest/xNome")

    def _parse_items(self, infNFe, extraction: NFExtraction) -> None:
        """Parse items (det) section."""
        # Use detected namespace
        ns = getattr(self, "_detected_ns", "")

        # Find all det elements with or without namespace
        det_elements = []
        if ns:
            det_elements = infNFe.findall(f".//{ns}det")
        if not det_elements:
            det_elements = infNFe.findall(".//det")
        if not det_elements:
            # Fallback: find by tag suffix
            det_elements = [elem for elem in infNFe.iter() if elem.tag.endswith("det")]

        for det in det_elements:
            try:
                item_number = int(det.get("nItem", 0))

                # Get product info (prod element)
                prod = None
                if ns:
                    prod = det.find(f"{ns}prod")
                if prod is None:
                    prod = det.find("prod")
                if prod is None:
                    # Find by suffix
                    for elem in det:
                        if elem.tag.endswith("prod"):
                            prod = elem
                            break

                if prod is None:
                    continue

                def get_prod_text(tag_name: str) -> str:
                    """Get text from a child element of prod."""
                    elem = None
                    if ns:
                        elem = prod.find(f"{ns}{tag_name}")
                    if elem is None:
                        elem = prod.find(tag_name)
                    if elem is None:
                        # Find by suffix
                        for child in prod:
                            if child.tag.endswith(tag_name):
                                elem = child
                                break
                    return elem.text.strip() if elem is not None and elem.text else ""

                description = get_prod_text("xProd")

                item = NFItem(
                    item_number=item_number,
                    part_number=get_prod_text("cProd"),
                    description=description,
                    ncm=get_prod_text("NCM"),
                    cfop=get_prod_text("CFOP"),
                    quantity=float(get_prod_text("qCom") or 0),
                    unit=get_prod_text("uCom") or "UN",
                    unit_price=float(get_prod_text("vUnCom") or 0),
                    total_price=float(get_prod_text("vProd") or 0),
                    serial_numbers=self.extract_serial_numbers(description),
                )

                extraction.items.append(item)

            except Exception as e:
                extraction.errors.append(f"Error parsing item: {str(e)}")

    def _parse_totals(self, infNFe, extraction: NFExtraction) -> None:
        """Parse totals section."""
        total_str = self._get_text(infNFe, "total/ICMSTot/vNF")
        if total_str:
            try:
                extraction.total_value = float(total_str)
            except ValueError:
                extraction.errors.append(f"Invalid total value: {total_str}")

    # =========================================================================
    # Serial Number Extraction
    # =========================================================================

    def extract_serial_numbers(self, description: str) -> List[str]:
        """
        Extract serial numbers from item description.

        Looks for common patterns like:
        - S/N: ABC123
        - SERIAL: ABC123
        - Nº Série: ABC123

        Args:
            description: Item description text

        Returns:
            List of found serial numbers
        """
        if not description:
            return []

        serials = set()

        for pattern in self.serial_patterns:
            matches = pattern.findall(description)
            for match in matches:
                serial = match.upper().strip()
                # Filter out too short or common words
                if len(serial) >= 5 and serial not in {"SERIAL", "SERIE", "NUMERO"}:
                    serials.add(serial)

        return list(serials)

    # =========================================================================
    # Confidence Calculation
    # =========================================================================

    def _calculate_confidence(self, extraction: NFExtraction) -> Dict[str, float]:
        """
        Calculate confidence scores for extraction.

        Args:
            extraction: The extraction result

        Returns:
            Dict with confidence metrics
        """
        scores = {
            "header": 0.0,
            "supplier": 0.0,
            "items": 0.0,
            "totals": 0.0,
            "overall": 0.0,
        }

        # Header confidence (NF number, date, key)
        header_points = 0
        if extraction.nf_number:
            header_points += 1
        if extraction.nf_date:
            header_points += 1
        if extraction.nf_key and len(extraction.nf_key) == 44:
            header_points += 2  # Full key is worth more
        scores["header"] = min(1.0, header_points / 4)

        # Supplier confidence
        supplier_points = 0
        if extraction.supplier_cnpj and len(extraction.supplier_cnpj) == 14:
            supplier_points += 2
        if extraction.supplier_name:
            supplier_points += 1
        scores["supplier"] = min(1.0, supplier_points / 3)

        # Items confidence
        if extraction.items:
            valid_items = 0
            for item in extraction.items:
                if item.part_number and item.quantity > 0:
                    valid_items += 1
            scores["items"] = valid_items / len(extraction.items)

        # Totals confidence
        if extraction.total_value > 0:
            # Verify sum of items matches total
            items_sum = sum(item.total_price for item in extraction.items)
            if items_sum > 0:
                ratio = min(items_sum, extraction.total_value) / max(items_sum, extraction.total_value)
                scores["totals"] = ratio
            else:
                scores["totals"] = 0.5  # Have total but no items

        # Overall weighted average
        weights = {"header": 0.2, "supplier": 0.2, "items": 0.4, "totals": 0.2}
        scores["overall"] = sum(scores[k] * weights[k] for k in weights)

        # Penalize for errors
        if extraction.errors:
            scores["overall"] *= max(0.5, 1 - (len(extraction.errors) * 0.1))

        return {k: round(v, 3) for k, v in scores.items()}

    # =========================================================================
    # Validation
    # =========================================================================

    def validate_extraction(self, extraction: NFExtraction) -> List[str]:
        """
        Validate extraction and return list of issues.

        Args:
            extraction: The extraction to validate

        Returns:
            List of validation issues (empty if valid)
        """
        issues = []

        # Required fields
        if not extraction.nf_number:
            issues.append("Missing NF number")
        if not extraction.nf_date:
            issues.append("Missing NF date")
        if not extraction.supplier_cnpj:
            issues.append("Missing supplier CNPJ")

        # CNPJ format
        if extraction.supplier_cnpj and len(extraction.supplier_cnpj) != 14:
            issues.append(f"Invalid supplier CNPJ length: {len(extraction.supplier_cnpj)}")

        # Items
        if not extraction.items:
            issues.append("No items found")
        else:
            for item in extraction.items:
                if not item.part_number:
                    issues.append(f"Item {item.item_number} missing part number")
                if item.quantity <= 0:
                    issues.append(f"Item {item.item_number} has invalid quantity")

        # Totals
        if extraction.total_value <= 0:
            issues.append("Invalid or missing total value")

        return issues

    # =========================================================================
    # PDF Text Extraction (AI-assisted)
    # =========================================================================

    def get_pdf_extraction_prompt(self, pdf_text: str) -> str:
        """
        Generate prompt for AI-based PDF extraction.

        Use this prompt with Gemini to extract NF data from PDF text.

        Args:
            pdf_text: Extracted text from PDF

        Returns:
            Prompt string for the LLM
        """
        return f"""Extraia os dados da Nota Fiscal Eletrônica (NF) do texto abaixo.

Retorne um JSON com a seguinte estrutura:
{{
    "nf_number": "número da NF",
    "nf_series": "série",
    "nf_key": "chave de acesso (44 dígitos)",
    "nf_date": "data de emissão (YYYY-MM-DD)",
    "nature_operation": "natureza da operação",
    "supplier_cnpj": "CNPJ do emitente (apenas números)",
    "supplier_name": "nome do emitente",
    "recipient_cnpj": "CNPJ do destinatário (apenas números)",
    "recipient_name": "nome do destinatário",
    "total_value": valor_total_nf,
    "items": [
        {{
            "item_number": número_sequencial,
            "part_number": "código do produto",
            "description": "descrição do produto",
            "ncm": "código NCM",
            "cfop": "código CFOP",
            "quantity": quantidade,
            "unit": "unidade",
            "unit_price": valor_unitário,
            "total_price": valor_total_item,
            "serial_numbers": ["lista", "de", "seriais", "se", "encontrados"]
        }}
    ]
}}

IMPORTANTE:
- Extraia TODOS os itens da nota
- Procure números de série nas descrições (S/N:, Serial:, Nº Série:)
- Valores numéricos devem ser números, não strings
- CNPJ deve conter apenas 14 dígitos numéricos
- Se não encontrar algum campo, use string vazia ou 0

Texto da NF:
{pdf_text}

JSON:"""

    def get_scanned_nf_prompt(self) -> str:
        """
        Generate prompt for Vision AI to extract NF data from scanned images.

        Use this prompt with Gemini Vision to extract NF data from scanned
        paper documents (DANFE images, photographed invoices, etc.).

        Returns:
            Prompt string for Vision model
        """
        return """Voce e um especialista em extracao de dados de Notas Fiscais Eletronicas (NF) brasileiras.

Analise a imagem da NF/DANFE escaneada e extraia TODOS os dados disponiveis.

## CAMPOS OBRIGATORIOS

Extraia com precisao:
1. **Cabecalho**: Numero da NF, Serie, Chave de Acesso (44 digitos), Data de Emissao
2. **Emitente**: CNPJ (14 digitos), Nome/Razao Social, Inscricao Estadual
3. **Destinatario**: CNPJ (14 digitos), Nome/Razao Social
4. **Itens**: Para CADA item na nota:
   - Codigo do Produto (cProd)
   - Descricao completa (xProd)
   - NCM (8 digitos)
   - CFOP (4 digitos)
   - Quantidade
   - Unidade
   - Valor Unitario
   - Valor Total
   - Numeros de Serie (se visiveis na descricao: S/N, Serial, IMEI, etc.)
5. **Totais**: Valor Total da NF, ICMS, IPI, etc.

## FORMATO DE RESPOSTA

Retorne APENAS um JSON valido (sem markdown, sem explicacoes):

{
    "nf_number": "numero da NF",
    "nf_series": "serie",
    "nf_key": "chave de acesso 44 digitos sem espacos",
    "nf_date": "YYYY-MM-DD",
    "nature_operation": "natureza da operacao",
    "supplier_cnpj": "14 digitos apenas numeros",
    "supplier_name": "nome do emitente",
    "supplier_ie": "inscricao estadual",
    "recipient_cnpj": "14 digitos apenas numeros",
    "recipient_name": "nome do destinatario",
    "total_value": 0.00,
    "items": [
        {
            "item_number": 1,
            "part_number": "codigo do produto",
            "description": "descricao completa",
            "ncm": "NCM 8 digitos",
            "cfop": "CFOP 4 digitos",
            "quantity": 1.0,
            "unit": "UN",
            "unit_price": 0.00,
            "total_price": 0.00,
            "serial_numbers": ["lista de seriais encontrados"]
        }
    ],
    "extraction_confidence": 0.85,
    "quality_issues": ["lista de problemas de legibilidade, se houver"]
}

## REGRAS IMPORTANTES

1. Se a imagem estiver ILEGIVEL ou PARCIALMENTE LEGIVEL:
   - Defina extraction_confidence entre 0.3 e 0.7
   - Liste os problemas em quality_issues
   - Extraia o que for possivel, use "" para campos ilegíveis

2. CNPJ deve ter EXATAMENTE 14 digitos numericos

3. Chave de Acesso deve ter EXATAMENTE 44 digitos numericos

4. Valores monetarios: use ponto como separador decimal (1234.56)

5. Procure ATIVAMENTE por numeros de serie em descricoes de produtos

6. Se for uma pagina de continuacao (itens), indique no quality_issues

Analise a imagem e retorne o JSON:"""

    def parse_ai_response(self, ai_response: str) -> NFExtraction:
        """
        Parse AI response into NFExtraction.

        Args:
            ai_response: JSON response from AI

        Returns:
            NFExtraction object
        """
        import json

        extraction = NFExtraction()

        try:
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', ai_response)
            if not json_match:
                extraction.errors.append("No JSON found in AI response")
                extraction.confidence = {"overall": 0.0}
                return extraction

            data = json.loads(json_match.group())

            # Map fields
            extraction.nf_number = str(data.get("nf_number", ""))
            extraction.nf_series = str(data.get("nf_series", ""))
            extraction.nf_key = str(data.get("nf_key", "")).replace(" ", "")
            extraction.nf_date = str(data.get("nf_date", ""))
            extraction.nature_operation = str(data.get("nature_operation", ""))
            extraction.supplier_cnpj = str(data.get("supplier_cnpj", "")).replace(".", "").replace("/", "").replace("-", "")
            extraction.supplier_name = str(data.get("supplier_name", ""))
            extraction.recipient_cnpj = str(data.get("recipient_cnpj", "")).replace(".", "").replace("/", "").replace("-", "")
            extraction.recipient_name = str(data.get("recipient_name", ""))
            extraction.total_value = float(data.get("total_value", 0))

            # Parse items
            for item_data in data.get("items", []):
                item = NFItem(
                    item_number=int(item_data.get("item_number", 0)),
                    part_number=str(item_data.get("part_number", "")),
                    description=str(item_data.get("description", "")),
                    ncm=str(item_data.get("ncm", "")),
                    cfop=str(item_data.get("cfop", "")),
                    quantity=float(item_data.get("quantity", 0)),
                    unit=str(item_data.get("unit", "UN")),
                    unit_price=float(item_data.get("unit_price", 0)),
                    total_price=float(item_data.get("total_price", 0)),
                    serial_numbers=item_data.get("serial_numbers", []),
                )
                extraction.items.append(item)

            # Calculate confidence (lower for AI extraction)
            extraction.confidence = self._calculate_confidence(extraction)
            extraction.confidence["overall"] *= 0.9  # AI extraction penalty

        except json.JSONDecodeError as e:
            extraction.errors.append(f"JSON parse error: {str(e)}")
            extraction.confidence = {"overall": 0.0}
        except Exception as e:
            extraction.errors.append(f"Parse error: {str(e)}")
            extraction.confidence = {"overall": 0.0}

        return extraction
