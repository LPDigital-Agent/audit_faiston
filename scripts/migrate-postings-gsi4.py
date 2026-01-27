#!/usr/bin/env python3
"""
Migration Script: Add GSI4 Keys to Existing Postings

This script adds GSI4PK and GSI4SK attributes to existing postings that don't have them.
This is required after adding GSI4-TenantQuery to enable efficient listing of all postings.

GSI4 Design:
- GSI4PK: TENANT#default (fixed value for single-tenant)
- GSI4SK: {created_at}#{posting_id} (for sorting by date)

Usage:
    # Dry run (preview changes)
    python scripts/migrate-postings-gsi4.py --dry-run

    # Execute migration
    python scripts/migrate-postings-gsi4.py

    # With custom table name
    python scripts/migrate-postings-gsi4.py --table faiston-one-prod-sga-postings

Requirements:
    - AWS credentials configured (profile: faiston-aio)
    - boto3 installed
"""

import argparse
import boto3
from boto3.dynamodb.conditions import Attr
from botocore.config import Config
import sys
from datetime import datetime


# Default configuration
DEFAULT_TABLE_NAME = "faiston-one-sga-postings-prod"
DEFAULT_REGION = "us-east-2"
DEFAULT_PROFILE = "faiston-aio"
TENANT_ID = "default"  # Single-tenant for now


def get_dynamodb_table(table_name: str, region: str, profile: str):
    """Get DynamoDB table resource."""
    session = boto3.Session(profile_name=profile)
    dynamodb = session.resource("dynamodb", region_name=region)
    return dynamodb.Table(table_name)


def scan_postings_without_gsi4(table, dry_run: bool = True):
    """
    Scan for postings that don't have GSI4PK attribute.
    Returns list of items that need migration.
    """
    print("\n[1/3] Scanning for postings without GSI4 keys...")

    items_to_migrate = []
    scan_kwargs = {
        "FilterExpression": Attr("PK").begins_with("POSTING#") & Attr("SK").eq("METADATA") & Attr("GSI4PK").not_exists()
    }

    done = False
    start_key = None
    total_scanned = 0

    while not done:
        if start_key:
            scan_kwargs["ExclusiveStartKey"] = start_key

        response = table.scan(**scan_kwargs)
        items = response.get("Items", [])
        items_to_migrate.extend(items)
        total_scanned += response.get("ScannedCount", 0)

        start_key = response.get("LastEvaluatedKey")
        done = start_key is None

        # Progress indicator
        print(f"      Scanned {total_scanned} items, found {len(items_to_migrate)} to migrate...", end="\r")

    print(f"\n      Found {len(items_to_migrate)} postings needing GSI4 keys")
    return items_to_migrate


def migrate_postings(table, items: list, dry_run: bool = True):
    """
    Add GSI4PK and GSI4SK to each posting.
    """
    if not items:
        print("\n[2/3] No postings to migrate!")
        return 0

    print(f"\n[2/3] {'[DRY RUN] Would update' if dry_run else 'Updating'} {len(items)} postings...")

    updated_count = 0
    errors = []

    for i, item in enumerate(items):
        pk = item.get("PK")
        sk = item.get("SK")
        posting_id = item.get("posting_id", pk.replace("POSTING#", "") if pk else "unknown")
        created_at = item.get("created_at", datetime.utcnow().isoformat() + "Z")

        # Build GSI4 keys
        gsi4_pk = f"TENANT#{TENANT_ID}"
        gsi4_sk = f"{created_at}#{posting_id}"

        if dry_run:
            print(f"      [{i+1}/{len(items)}] Would add GSI4 to {posting_id}")
            print(f"                GSI4PK: {gsi4_pk}")
            print(f"                GSI4SK: {gsi4_sk}")
            updated_count += 1
        else:
            try:
                table.update_item(
                    Key={"PK": pk, "SK": sk},
                    UpdateExpression="SET GSI4PK = :gsi4pk, GSI4SK = :gsi4sk",
                    ExpressionAttributeValues={
                        ":gsi4pk": gsi4_pk,
                        ":gsi4sk": gsi4_sk,
                    },
                    ConditionExpression="attribute_not_exists(GSI4PK)",  # Safety: don't overwrite
                )
                updated_count += 1
                print(f"      [{i+1}/{len(items)}] Updated {posting_id}")
            except table.meta.client.exceptions.ConditionalCheckFailedException:
                # Already has GSI4PK, skip
                print(f"      [{i+1}/{len(items)}] Skipped {posting_id} (already has GSI4)")
            except Exception as e:
                errors.append((posting_id, str(e)))
                print(f"      [{i+1}/{len(items)}] ERROR on {posting_id}: {e}")

    if errors:
        print(f"\n      Errors encountered: {len(errors)}")
        for posting_id, error in errors[:5]:  # Show first 5 errors
            print(f"        - {posting_id}: {error}")

    return updated_count


def verify_migration(table):
    """
    Verify GSI4 is working by querying it.
    """
    print("\n[3/3] Verifying GSI4 query works...")

    try:
        response = table.query(
            IndexName="GSI4-TenantQuery",
            KeyConditionExpression="GSI4PK = :pk",
            ExpressionAttributeValues={":pk": f"TENANT#{TENANT_ID}"},
            Limit=5,
            ScanIndexForward=False,  # Newest first
        )

        items = response.get("Items", [])
        print(f"      GSI4 query returned {len(items)} items (showing up to 5)")

        for item in items:
            posting_id = item.get("posting_id", "?")
            status = item.get("status", "?")
            created = item.get("created_at", "?")[:10]
            print(f"        - {posting_id} | {status} | {created}")

        return True
    except Exception as e:
        print(f"      ERROR: GSI4 query failed: {e}")
        print("      This might mean GSI4 hasn't been created in DynamoDB yet.")
        print("      Run 'terraform apply' first to create the GSI.")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Add GSI4 keys to existing postings for efficient listing"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them",
    )
    parser.add_argument(
        "--table",
        default=DEFAULT_TABLE_NAME,
        help=f"DynamoDB table name (default: {DEFAULT_TABLE_NAME})",
    )
    parser.add_argument(
        "--region",
        default=DEFAULT_REGION,
        help=f"AWS region (default: {DEFAULT_REGION})",
    )
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        help=f"AWS profile (default: {DEFAULT_PROFILE})",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip GSI4 verification step",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("  POSTINGS GSI4 MIGRATION")
    print("=" * 60)
    print(f"  Table:   {args.table}")
    print(f"  Region:  {args.region}")
    print(f"  Profile: {args.profile}")
    print(f"  Mode:    {'DRY RUN (no changes)' if args.dry_run else 'LIVE (will update records)'}")
    print("=" * 60)

    if not args.dry_run:
        confirm = input("\nThis will modify DynamoDB records. Continue? [y/N]: ")
        if confirm.lower() != "y":
            print("Aborted.")
            sys.exit(0)

    # Get table
    table = get_dynamodb_table(args.table, args.region, args.profile)

    # Step 1: Find postings without GSI4
    items = scan_postings_without_gsi4(table, args.dry_run)

    # Step 2: Migrate them
    updated = migrate_postings(table, items, args.dry_run)

    # Step 3: Verify (only if not dry run and not skipped)
    if not args.dry_run and not args.skip_verify:
        verify_migration(table)
    elif args.dry_run:
        print("\n[3/3] Skipping verification (dry run)")

    # Summary
    print("\n" + "=" * 60)
    print("  MIGRATION SUMMARY")
    print("=" * 60)
    print(f"  Postings found:   {len(items)}")
    print(f"  Postings updated: {updated}")
    if args.dry_run:
        print("\n  [!] DRY RUN - No changes were made")
        print("  Run without --dry-run to apply changes")
    else:
        print("\n  [OK] Migration complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
