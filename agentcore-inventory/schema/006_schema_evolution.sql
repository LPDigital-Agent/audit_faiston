-- =============================================================================
-- Migration 006: Schema Evolution Support
-- =============================================================================
-- Purpose: Enable dynamic column creation for CSV imports with unknown fields
-- Author: Schema Evolution Agent (SEA) Infrastructure
-- Date: January 2026
--
-- Features:
--   1. metadata JSONB column for fallback storage
--   2. schema_evolution_log table for audit trail
--   3. dynamic_columns table for tracking created columns
--
-- Safety:
--   - Uses IF NOT EXISTS for idempotency
--   - Advisory locks prevent race conditions (handled in application layer)
--   - All schema changes are audited
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Add metadata JSONB column to pending_entry_items (fallback storage)
-- -----------------------------------------------------------------------------
-- This column stores fields that don't have dedicated columns yet.
-- Used when:
--   - User chooses "Store in metadata" option
--   - DDL creation fails or times out
--   - Lock cannot be acquired within timeout
-- -----------------------------------------------------------------------------

ALTER TABLE sga.pending_entry_items
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

COMMENT ON COLUMN sga.pending_entry_items.metadata IS
'Fallback JSONB storage for dynamic fields that do not have dedicated columns yet. Keys are original CSV column names, values are the field data.';

-- Create GIN index for efficient JSONB queries
CREATE INDEX IF NOT EXISTS idx_pending_entry_items_metadata
ON sga.pending_entry_items USING GIN (metadata);

-- -----------------------------------------------------------------------------
-- 2. Create schema_evolution_log table (Audit Trail)
-- -----------------------------------------------------------------------------
-- Logs ALL schema change attempts (successful and failed) for:
--   - Compliance auditing
--   - Debugging
--   - Usage analytics
--   - Security monitoring
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sga.schema_evolution_log (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- What was changed
    table_name VARCHAR(100) NOT NULL,
    column_name VARCHAR(100) NOT NULL,
    column_type VARCHAR(50) NOT NULL,
    original_csv_column VARCHAR(255),  -- Original column name from CSV
    sample_values TEXT[],              -- First 5 sample values (for debugging)

    -- Who requested the change
    requested_by VARCHAR(100),         -- user_id from session

    -- Status tracking
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',  -- PENDING, CREATED, FAILED, ALREADY_EXISTS
    error_message TEXT,                -- Error details if FAILED

    -- Timestamps
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_status CHECK (status IN ('PENDING', 'CREATED', 'FAILED', 'ALREADY_EXISTS'))
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_schema_evolution_table
ON sga.schema_evolution_log(table_name);

CREATE INDEX IF NOT EXISTS idx_schema_evolution_status
ON sga.schema_evolution_log(status);

CREATE INDEX IF NOT EXISTS idx_schema_evolution_requested_at
ON sga.schema_evolution_log(requested_at DESC);

CREATE INDEX IF NOT EXISTS idx_schema_evolution_requested_by
ON sga.schema_evolution_log(requested_by);

COMMENT ON TABLE sga.schema_evolution_log IS
'Audit log for all dynamic column creation attempts. Tracks successful creations, failures, and requests for columns that already existed.';

-- -----------------------------------------------------------------------------
-- 3. Create dynamic_columns tracking table
-- -----------------------------------------------------------------------------
-- Tracks all dynamically-created columns for:
--   - Schema documentation
--   - Usage analytics (which columns are used most)
--   - Cleanup of unused columns
--   - Schema introspection by AI agents
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sga.dynamic_columns (
    column_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Column identification
    table_name VARCHAR(100) NOT NULL,
    column_name VARCHAR(100) NOT NULL,
    column_type VARCHAR(50) NOT NULL,

    -- Origin tracking
    inferred_from VARCHAR(255),        -- Original CSV column name that triggered creation
    sample_values TEXT[],              -- Sample values used to infer type

    -- Usage tracking
    usage_count INTEGER NOT NULL DEFAULT 1,
    last_used_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Creation metadata
    created_by VARCHAR(100),           -- user_id who first created it
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Unique constraint: one column per table
    CONSTRAINT unique_dynamic_column UNIQUE(table_name, column_name)
);

-- Index for finding columns by table
CREATE INDEX IF NOT EXISTS idx_dynamic_columns_table
ON sga.dynamic_columns(table_name);

-- Index for finding unused columns (for cleanup)
CREATE INDEX IF NOT EXISTS idx_dynamic_columns_last_used
ON sga.dynamic_columns(last_used_at);

COMMENT ON TABLE sga.dynamic_columns IS
'Registry of dynamically-created columns. Used for schema documentation, usage analytics, and potential cleanup of unused columns.';

-- -----------------------------------------------------------------------------
-- 4. Function to increment usage count (called on each import using the column)
-- -----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION sga.increment_dynamic_column_usage(
    p_table_name VARCHAR(100),
    p_column_name VARCHAR(100)
) RETURNS VOID AS $$
BEGIN
    UPDATE sga.dynamic_columns
    SET
        usage_count = usage_count + 1,
        last_used_at = NOW()
    WHERE table_name = p_table_name
      AND column_name = p_column_name;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION sga.increment_dynamic_column_usage IS
'Increments usage count for a dynamic column. Called after successful imports using the column.';

-- -----------------------------------------------------------------------------
-- 5. View for schema evolution dashboard
-- -----------------------------------------------------------------------------

CREATE OR REPLACE VIEW sga.v_schema_evolution_summary AS
SELECT
    table_name,
    COUNT(*) as total_dynamic_columns,
    SUM(usage_count) as total_usages,
    MIN(created_at) as first_column_created,
    MAX(created_at) as last_column_created,
    ARRAY_AGG(column_name ORDER BY created_at DESC) as column_names
FROM sga.dynamic_columns
GROUP BY table_name
ORDER BY total_dynamic_columns DESC;

COMMENT ON VIEW sga.v_schema_evolution_summary IS
'Summary of dynamic columns by table for monitoring and analytics dashboard.';

-- -----------------------------------------------------------------------------
-- End of Migration 006
-- -----------------------------------------------------------------------------
