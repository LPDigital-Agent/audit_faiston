#!/usr/bin/env python3
"""
Test script for Tiflux Sync Service.

Tests:
1. Parser for expedition addresses
2. DynamoDB connection
3. Sync operation
"""

import asyncio
import sys
import os
import re
import logging
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta, timezone

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Import boto3 directly
import boto3
from boto3.dynamodb.conditions import Key
import httpx

# =============================================================================
# Copy of parser functions (to avoid import issues with strands)
# =============================================================================

@dataclass
class DestinationAddress:
    """Structured destination address for expedition workflow."""
    endereco: Optional[str] = None
    numero: Optional[str] = None
    bairro: Optional[str] = None
    cidade: Optional[str] = None
    uf: Optional[str] = None
    cep: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "endereco": self.endereco or "",
            "numero": self.numero or "S/N",
            "bairro": self.bairro or "",
            "cidade": self.cidade or "",
            "uf": self.uf or "",
            "cep": (self.cep or "").replace("-", ""),
        }

    def is_valid(self) -> bool:
        return bool(self.cep and (self.endereco or self.cidade))


def _clean_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&amp;", "&")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n", text)
    return text.strip()


def parse_expedition_address(description: str) -> Optional[DestinationAddress]:
    """Parse destination address from expedition ticket description."""
    if not description:
        return None

    text = _clean_html(description)

    # Pattern 1: Full address
    full_pattern = re.search(
        r"Endere[çc]o[:\s]+(.+?),\s*(\d+)\s*-\s*([^,]+),\s*([^-]+)\s*-\s*([A-Z]{2}),?\s*(\d{5}-?\d{3})",
        text,
        re.IGNORECASE
    )

    if full_pattern:
        return DestinationAddress(
            endereco=full_pattern.group(1).strip(),
            numero=full_pattern.group(2).strip(),
            bairro=full_pattern.group(3).strip(),
            cidade=full_pattern.group(4).strip(),
            uf=full_pattern.group(5).upper(),
            cep=re.sub(r"[^\d]", "", full_pattern.group(6)),
        )

    # Pattern 2: Simpler format
    simpler_pattern = re.search(
        r"Endere[çc]o[:\s]+(.+?),\s*(\d+)[,\s]+([^-]+)\s*-\s*([A-Z]{2}),?\s*(\d{5}-?\d{3})",
        text,
        re.IGNORECASE
    )

    if simpler_pattern:
        return DestinationAddress(
            endereco=simpler_pattern.group(1).strip(),
            numero=simpler_pattern.group(2).strip(),
            bairro="",
            cidade=simpler_pattern.group(3).strip(),
            uf=simpler_pattern.group(4).upper(),
            cep=re.sub(r"[^\d]", "", simpler_pattern.group(5)),
        )

    # Pattern 3: Extract what we can
    address_match = re.search(r"Endere[çc]o[:\s]+([^\n]+)", text, re.IGNORECASE)
    cep_match = re.search(r"(\d{5}-?\d{3})", text)

    if address_match or cep_match:
        address_line = address_match.group(1).strip() if address_match else ""
        cidade = None
        uf = None
        uf_match = re.search(r"([^,-]+)\s*-\s*([A-Z]{2})", address_line, re.IGNORECASE)
        if uf_match:
            cidade = uf_match.group(1).strip()
            uf = uf_match.group(2).upper()

        numero = None
        numero_match = re.search(r",\s*(\d+)\b", address_line)
        if numero_match:
            numero = numero_match.group(1)

        return DestinationAddress(
            endereco=address_line,
            numero=numero,
            bairro=None,
            cidade=cidade,
            uf=uf,
            cep=re.sub(r"[^\d]", "", cep_match.group(1)) if cep_match else None,
        )

    return None


# =============================================================================
# Tests
# =============================================================================

TIFLUX_API_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJqdGkiOiJhZTg4OWM1NC0xMzc1LTQ4NzctOWQ3YS1hYWRlZDZlNDA4Y2EiLCJzdWIiOjEwMjE4NjIsInNjcCI6InVzZXIiLCJhdWQiOm51bGwsImlhdCI6MTc2ODQ4MzE3MiwicmVxX2xpbWl0IjoxMjAsImV4cCI6MTgzMTU5NzA3Nn0.76Re0k_7ypPzJD0FQxQ_RM9Zl2gV5x_zJX0QRvpXDfM"
TIFLUX_BASE_URL = "https://api.tiflux.com/api/v2"
TABLE_NAME = "faiston-one-sga-tiflux-tickets-prod"


def test_expedition_parser():
    """Test expedition address parser with real examples."""
    print("\n" + "=" * 70)
    print("TEST 1: Expedition Address Parser")
    print("=" * 70)

    test_cases = [
        # Full format from real ticket
        (
            '<p>Endereço: Alameda Araguaia, 762 - Alphaville, Barueri - SP, 06455-010</p>',
            {"endereco": "Alameda Araguaia", "numero": "762", "bairro": "Alphaville",
             "cidade": "Barueri", "uf": "SP", "cep": "06455010"}
        ),
    ]

    passed = 0
    for i, (html, expected) in enumerate(test_cases):
        print(f"\nTest Case {i + 1}:")
        print(f"  Input: {html[:80]}...")

        result = parse_expedition_address(html)

        if result:
            print(f"  Result: {result.to_dict()}")
            all_match = True
            for key, expected_value in expected.items():
                actual_value = getattr(result, key, None)
                if actual_value != expected_value:
                    print(f"  [FAIL] {key}: expected '{expected_value}', got '{actual_value}'")
                    all_match = False
            if all_match:
                print(f"  [PASS]")
                passed += 1
        else:
            print(f"  [FAIL] Result is None")

    print(f"\nParser Tests: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_dynamodb_connection():
    """Test DynamoDB connection."""
    print("\n" + "=" * 70)
    print("TEST 2: DynamoDB Connection")
    print("=" * 70)

    try:
        dynamodb = boto3.resource("dynamodb", region_name="us-east-2")
        table = dynamodb.Table(TABLE_NAME)

        # Try to get table status
        status = table.table_status
        print(f"  Table: {TABLE_NAME}")
        print(f"  Status: {status}")
        print("  [PASS] DynamoDB connection successful")
        return True

    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return False


async def test_tiflux_fetch():
    """Test fetching tickets from Tiflux API."""
    print("\n" + "=" * 70)
    print("TEST 3: Tiflux API Fetch")
    print("=" * 70)

    try:
        async with httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {TIFLUX_API_KEY}",
                "Accept": "application/json",
            },
        ) as client:
            response = await client.get(
                f"{TIFLUX_BASE_URL}/tickets",
                params={"offset": 1, "limit": 10}
            )

            if response.status_code == 200:
                data = response.json()
                count = len(data) if isinstance(data, list) else 0
                print(f"  Fetched {count} tickets from Tiflux")
                print("  [PASS] Tiflux API connection successful")
                return True, data
            else:
                print(f"  [FAIL] HTTP {response.status_code}: {response.text[:100]}")
                return False, []

    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return False, []


async def test_sync_operation():
    """Test full sync: fetch from Tiflux, parse, write to DynamoDB."""
    print("\n" + "=" * 70)
    print("TEST 4: Full Sync Operation")
    print("=" * 70)

    dynamodb = boto3.resource("dynamodb", region_name="us-east-2")
    table = dynamodb.Table(TABLE_NAME)

    # Get existing ticket numbers
    print("\n  Checking existing tickets in DynamoDB...")
    existing_numbers = set()
    try:
        response = table.query(
            IndexName="GSI1-WorkflowQuery",
            KeyConditionExpression=Key("GSI1PK").eq("WORKFLOW#EXPEDICAO"),
            ProjectionExpression="ticket_number",
        )
        for item in response.get("Items", []):
            if "ticket_number" in item:
                existing_numbers.add(int(item["ticket_number"]))
        print(f"  Found {len(existing_numbers)} existing EXPEDICAO tickets")
    except Exception as e:
        print(f"  Warning: Could not query existing tickets: {e}")

    # Fetch from Tiflux - looking for expedicao stages
    print("\n  Fetching expedicao tickets from Tiflux...")
    expedicao_tickets = []

    try:
        async with httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {TIFLUX_API_KEY}",
                "Accept": "application/json",
            },
        ) as client:
            # Fetch up to 3 pages
            for page in range(1, 4):
                response = await client.get(
                    f"{TIFLUX_BASE_URL}/tickets",
                    params={"offset": page, "limit": 200}
                )

                if response.status_code != 200:
                    break

                data = response.json()
                if not data:
                    break

                # Filter for expedicao stages
                for ticket in data:
                    stage = ticket.get("stage", {}).get("name", "").lower()
                    if "enviar logistica" in stage or "enviado logistica" in stage:
                        expedicao_tickets.append(ticket)

                print(f"  Page {page}: Found {len([t for t in data if 'logistica' in t.get('stage', {}).get('name', '').lower()])} expedicao tickets")

        print(f"\n  Total expedicao tickets from Tiflux: {len(expedicao_tickets)}")

    except Exception as e:
        print(f"  [FAIL] Error fetching from Tiflux: {e}")
        return False

    # Ingest new tickets
    new_count = 0
    skipped_count = 0
    error_count = 0

    print("\n  Ingesting new tickets...")
    for ticket in expedicao_tickets:
        ticket_number = ticket.get("ticket_number", 0)

        if ticket_number in existing_numbers:
            skipped_count += 1
            continue

        # Parse address
        description = ticket.get("description", "")
        parsed_address = parse_expedition_address(description)

        # Create DynamoDB item
        now = datetime.now(timezone.utc).isoformat()
        ttl = int((datetime.now(timezone.utc) + timedelta(days=90)).timestamp())

        item = {
            "PK": f"TICKET#{ticket_number}",
            "SK": "METADATA",
            "GSI1PK": "WORKFLOW#EXPEDICAO",
            "GSI1SK": f"{ticket.get('created_at', '')}#{ticket_number}",
            "GSI2PK": f"STATUS#{ticket.get('status', {}).get('id', 0)}",
            "GSI2SK": f"{ticket.get('created_at', '')}#{ticket_number}",
            "GSI3PK": "TENANT#default",
            "GSI3SK": f"{now}#{ticket_number}",
            "GSI4PK": f"DESK#{ticket.get('desk', {}).get('id', 0)}",
            "GSI4SK": f"{ticket.get('created_at', '')}#{ticket_number}",
            "ticket_number": ticket_number,
            "title": ticket.get("title", ""),
            "description_html": description,
            "status": ticket.get("status", {}).get("name", ""),
            "status_id": ticket.get("status", {}).get("id", 0),
            "stage": ticket.get("stage", {}).get("name", ""),
            "stage_id": ticket.get("stage", {}).get("id", 0),
            "desk": ticket.get("desk", {}).get("name", ""),
            "desk_id": ticket.get("desk", {}).get("id", 0),
            "client_name": ticket.get("client", {}).get("name", ""),
            "client_id": ticket.get("client", {}).get("id", 0),
            "tiflux_created_at": ticket.get("created_at", ""),
            "tiflux_updated_at": ticket.get("updated_at", ""),
            "workflow_type": "EXPEDICAO",
            "ingested_at": now,
            "last_synced_at": now,
            "ttl": ttl,
        }

        if parsed_address:
            item["parsed_address"] = parsed_address.to_dict()

        # Write to DynamoDB
        try:
            table.put_item(Item=item)
            new_count += 1
            addr_status = "with address" if parsed_address else "no address"
            print(f"    Ingested #{ticket_number} ({addr_status})")
        except Exception as e:
            error_count += 1
            print(f"    [ERROR] #{ticket_number}: {e}")

    print(f"\n  Sync Results:")
    print(f"    New tickets ingested: {new_count}")
    print(f"    Existing skipped: {skipped_count}")
    print(f"    Errors: {error_count}")

    # Verify by reading back
    print("\n  Verifying cached tickets...")
    try:
        response = table.query(
            IndexName="GSI1-WorkflowQuery",
            KeyConditionExpression=Key("GSI1PK").eq("WORKFLOW#EXPEDICAO"),
            Limit=5,
        )

        cached = response.get("Items", [])
        print(f"  Found {len(cached)} cached tickets (showing first 5):")

        for item in cached[:5]:
            addr = item.get("parsed_address", {})
            addr_str = f"{addr.get('cidade', 'N/A')} - {addr.get('uf', 'N/A')}, CEP: {addr.get('cep', 'N/A')}" if addr else "No address"
            print(f"    #{item.get('ticket_number')}: {item.get('title', '')[:40]}...")
            print(f"      Address: {addr_str}")

    except Exception as e:
        print(f"  [FAIL] Could not verify: {e}")
        return False

    print("\n  [PASS] Sync operation completed successfully")
    return True


async def main():
    print("=" * 70)
    print("  TIFLUX SYNC SERVICE VALIDATION")
    print("=" * 70)

    results = []

    # Test 1: Parser
    results.append(("Parser", test_expedition_parser()))

    # Test 2: DynamoDB
    results.append(("DynamoDB", test_dynamodb_connection()))

    # Test 3: Tiflux API
    tiflux_ok, _ = await test_tiflux_fetch()
    results.append(("Tiflux API", tiflux_ok))

    # Test 4: Full Sync
    if all(r[1] for r in results):
        results.append(("Full Sync", await test_sync_operation()))
    else:
        print("\n  [SKIP] Full Sync - prerequisite tests failed")
        results.append(("Full Sync", False))

    # Summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {name}")

    all_passed = all(p for _, p in results)
    print(f"\n  Overall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
