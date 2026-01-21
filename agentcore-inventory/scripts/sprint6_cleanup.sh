#!/bin/bash
# =============================================================================
# Sprint 6: DynamoDB Inventory Table Cleanup
# =============================================================================
# Execute this script ONLY AFTER validating PostgreSQL migration:
#
# Pre-requisites:
# 1. ✅ Infrastructure deployed via GitHub Actions (terraform apply)
# 2. ✅ SQL schema migrations executed against Aurora
# 3. ✅ AgentCore Gateway created via AWS CLI
# 4. ✅ Lambda MCP tools tested end-to-end
# 5. ✅ Feature flag USE_POSTGRES_MCP=true validated
# 6. ✅ 1 week parallel running with no issues
#
# What this script does:
# 1. Removes DynamoDB inventory table Terraform file
# 2. Updates IAM policy to remove inventory table reference
# 3. Archives the DynamoDB client (not deleted, kept for reference)
# 4. Updates main.py to remove feature flag (PostgreSQL is now default)
#
# WARNING: This is IRREVERSIBLE. Ensure all validation is complete!
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
TERRAFORM_DIR="$PROJECT_ROOT/terraform/main"
SERVER_DIR="$PROJECT_ROOT/server/agentcore-inventory"

echo "=============================================="
echo "Sprint 6: DynamoDB Inventory Table Cleanup"
echo "=============================================="
echo ""
echo "Project root: $PROJECT_ROOT"
echo ""

# Safety check
read -p "Have you completed ALL validation steps? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Aborting. Complete validation first."
    exit 1
fi

echo ""
echo "Step 1: Archive DynamoDB client..."
echo "----------------------------------------------"
mkdir -p "$SERVER_DIR/tools/_archived"
if [ -f "$SERVER_DIR/tools/dynamodb_client.py" ]; then
    mv "$SERVER_DIR/tools/dynamodb_client.py" "$SERVER_DIR/tools/_archived/dynamodb_client.py.bak"
    echo "✅ Archived: dynamodb_client.py -> _archived/dynamodb_client.py.bak"
else
    echo "⚠️  dynamodb_client.py not found (already archived?)"
fi

echo ""
echo "Step 2: Remove DynamoDB inventory table Terraform..."
echo "----------------------------------------------"
if [ -f "$TERRAFORM_DIR/dynamodb_sga_inventory.tf" ]; then
    # First, remove the resource from Terraform state (to avoid destroy)
    echo "Removing from Terraform state..."
    cd "$TERRAFORM_DIR"
    AWS_PROFILE=faiston-aio terraform state rm aws_dynamodb_table.sga_inventory || true

    # Then delete the file
    rm "$TERRAFORM_DIR/dynamodb_sga_inventory.tf"
    echo "✅ Deleted: dynamodb_sga_inventory.tf"
else
    echo "⚠️  dynamodb_sga_inventory.tf not found (already deleted?)"
fi

echo ""
echo "Step 3: Update IAM policy to remove inventory table..."
echo "----------------------------------------------"
echo "Manual step required:"
echo "  Edit: $TERRAFORM_DIR/iam_sga_agentcore.tf"
echo "  Remove the 'DynamoDBSGAInventoryAccess' statement"
echo "  Keep HIL and Audit table access statements"
echo ""

echo ""
echo "Step 4: Update main.py to use PostgreSQL by default..."
echo "----------------------------------------------"
echo "Manual step required:"
echo "  Edit: $SERVER_DIR/main.py"
echo "  1. Remove USE_POSTGRES_MCP feature flag (set True as default)"
echo "  2. Remove DynamoDB fallback in get_database_adapter()"
echo "  3. Update health_check to reflect PostgreSQL-only mode"
echo ""

echo ""
echo "Step 5: Run Terraform validate..."
echo "----------------------------------------------"
cd "$TERRAFORM_DIR"
AWS_PROFILE=faiston-aio terraform validate
echo "✅ Terraform validation passed"

echo ""
echo "=============================================="
echo "Sprint 6 cleanup partially complete!"
echo "=============================================="
echo ""
echo "Manual steps remaining:"
echo "1. Edit iam_sga_agentcore.tf to remove inventory table access"
echo "2. Edit main.py to make PostgreSQL the default"
echo "3. Run: terraform plan (via GitHub Actions)"
echo "4. Run: terraform apply (via GitHub Actions)"
echo "5. Deploy agents via GitHub Actions"
echo ""
echo "After these steps, the DynamoDB inventory table can be"
echo "manually deleted from AWS Console if desired."
echo ""
