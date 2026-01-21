-- =============================================================================
-- Migration 005: Equipment Research Tracking
-- =============================================================================
-- Table for tracking equipment documentation research status.
-- Used by EquipmentResearchAgent to:
-- - Deduplicate research (don't re-research same part number)
-- - Track progress and status of each research task
-- - Store search queries, sources, and summaries
-- - Enable retry logic for failed research
--
-- Author: Claude Code + Faiston Team
-- Date: 2026-01-06
-- =============================================================================

-- =============================================================================
-- Equipment Research Table
-- =============================================================================
-- Tracks documentation research status for imported equipment.
-- One row per unique part_number - research is deduped at this level.

CREATE TABLE IF NOT EXISTS sga.equipment_research (
    -- Primary Key
    research_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Part Number Reference (unique - one research per PN)
    part_number VARCHAR(100) UNIQUE NOT NULL,
    part_number_id UUID REFERENCES sga.part_numbers(part_number_id) ON DELETE SET NULL,

    -- Equipment Information (captured at queue time)
    description TEXT,
    manufacturer VARCHAR(200),
    category VARCHAR(100),

    -- Research Status
    -- PENDING: Queued for research
    -- IN_PROGRESS: Currently being researched
    -- COMPLETED: Successfully found and downloaded documentation
    -- NO_DOCS_FOUND: Searched but no relevant documentation found
    -- FAILED: Research failed (network, quota, etc.)
    -- RATE_LIMITED: Skipped due to daily quota limit
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'NO_DOCS_FOUND', 'FAILED', 'RATE_LIMITED')),

    -- Research Results
    documents_found INTEGER DEFAULT 0,
    documents_downloaded INTEGER DEFAULT 0,
    s3_prefix VARCHAR(500),  -- e.g., "equipment-docs/by-part-number/ABC123/"

    -- Search Metadata
    search_queries JSONB DEFAULT '[]'::jsonb,  -- ["query1", "query2", ...]
    sources JSONB DEFAULT '[]'::jsonb,         -- [{url, title, type, downloaded}]

    -- AI-Generated Summary
    summary TEXT,

    -- Error Handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    last_retry_at TIMESTAMPTZ,

    -- Timing
    queued_at TIMESTAMPTZ,           -- When added to research queue
    started_at TIMESTAMPTZ,          -- When research started
    completed_at TIMESTAMPTZ,        -- When research completed/failed

    -- Audit
    queued_by VARCHAR(100),          -- User who triggered research
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add comment
COMMENT ON TABLE sga.equipment_research IS
'Tracks equipment documentation research status for Bedrock Knowledge Base RAG. One row per unique part_number.';

-- =============================================================================
-- Indexes for Queue Processing
-- =============================================================================

-- Index for finding pending research items (queue processing)
CREATE INDEX IF NOT EXISTS idx_equipment_research_status_queue
ON sga.equipment_research(status, queued_at)
WHERE status = 'PENDING';

-- Index for finding failed items to retry
CREATE INDEX IF NOT EXISTS idx_equipment_research_retry
ON sga.equipment_research(status, retry_count, last_retry_at)
WHERE status = 'FAILED' AND retry_count < 3;

-- Index for part number lookups (deduplication check)
CREATE INDEX IF NOT EXISTS idx_equipment_research_part_number
ON sga.equipment_research(part_number);

-- Index for part_number_id foreign key
CREATE INDEX IF NOT EXISTS idx_equipment_research_pn_id
ON sga.equipment_research(part_number_id)
WHERE part_number_id IS NOT NULL;

-- Index for status distribution queries (dashboard)
CREATE INDEX IF NOT EXISTS idx_equipment_research_status
ON sga.equipment_research(status);

-- =============================================================================
-- Trigger for updated_at
-- =============================================================================

CREATE OR REPLACE FUNCTION sga.update_equipment_research_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_equipment_research_updated_at ON sga.equipment_research;

CREATE TRIGGER trg_equipment_research_updated_at
    BEFORE UPDATE ON sga.equipment_research
    FOR EACH ROW
    EXECUTE FUNCTION sga.update_equipment_research_timestamp();

-- =============================================================================
-- Google Search Quota Tracking Table
-- =============================================================================
-- Tracks daily Google Search API usage to respect 5000/day limit.

CREATE TABLE IF NOT EXISTS sga.google_search_quota (
    quota_date DATE PRIMARY KEY,
    search_count INTEGER DEFAULT 0,
    daily_limit INTEGER DEFAULT 5000,
    last_search_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE sga.google_search_quota IS
'Tracks daily Google Search API usage for EquipmentResearchAgent rate limiting (5000/day limit).';

-- Index for quota lookup
CREATE INDEX IF NOT EXISTS idx_google_search_quota_date
ON sga.google_search_quota(quota_date DESC);

-- =============================================================================
-- Helper Functions
-- =============================================================================

-- Function to check if quota is available
CREATE OR REPLACE FUNCTION sga.check_google_search_quota()
RETURNS BOOLEAN AS $$
DECLARE
    current_count INTEGER;
    daily_limit INTEGER;
BEGIN
    SELECT COALESCE(q.search_count, 0), COALESCE(q.daily_limit, 5000)
    INTO current_count, daily_limit
    FROM sga.google_search_quota q
    WHERE q.quota_date = CURRENT_DATE;

    IF current_count IS NULL THEN
        -- No record for today, quota is available
        RETURN TRUE;
    END IF;

    RETURN current_count < daily_limit;
END;
$$ LANGUAGE plpgsql;

-- Function to increment search quota
CREATE OR REPLACE FUNCTION sga.increment_google_search_quota()
RETURNS INTEGER AS $$
DECLARE
    new_count INTEGER;
BEGIN
    INSERT INTO sga.google_search_quota (quota_date, search_count, last_search_at)
    VALUES (CURRENT_DATE, 1, NOW())
    ON CONFLICT (quota_date)
    DO UPDATE SET
        search_count = sga.google_search_quota.search_count + 1,
        last_search_at = NOW(),
        updated_at = NOW()
    RETURNING search_count INTO new_count;

    RETURN new_count;
END;
$$ LANGUAGE plpgsql;

-- Function to get research queue summary
CREATE OR REPLACE FUNCTION sga.get_equipment_research_summary()
RETURNS TABLE (
    status VARCHAR(50),
    count BIGINT,
    oldest_queued TIMESTAMPTZ,
    newest_queued TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        er.status,
        COUNT(*)::BIGINT,
        MIN(er.queued_at),
        MAX(er.queued_at)
    FROM sga.equipment_research er
    GROUP BY er.status
    ORDER BY er.status;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Grant Permissions
-- =============================================================================
-- Grant access to the bedrock_user role (used by AgentCore)

DO $$
BEGIN
    -- Check if bedrock_user role exists before granting
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'bedrock_user') THEN
        GRANT SELECT, INSERT, UPDATE ON sga.equipment_research TO bedrock_user;
        GRANT SELECT, INSERT, UPDATE ON sga.google_search_quota TO bedrock_user;
        GRANT EXECUTE ON FUNCTION sga.check_google_search_quota() TO bedrock_user;
        GRANT EXECUTE ON FUNCTION sga.increment_google_search_quota() TO bedrock_user;
        GRANT EXECUTE ON FUNCTION sga.get_equipment_research_summary() TO bedrock_user;
    END IF;
END $$;

-- =============================================================================
-- Sample Data (for testing - commented out)
-- =============================================================================
/*
INSERT INTO sga.equipment_research (
    part_number, description, manufacturer, status, queued_at, queued_by
) VALUES
    ('CISCO-9300-24T', 'Cisco Catalyst 9300 24-port Switch', 'Cisco', 'PENDING', NOW(), 'test@faiston.com'),
    ('DELL-R740', 'Dell PowerEdge R740 Server', 'Dell', 'PENDING', NOW(), 'test@faiston.com')
ON CONFLICT (part_number) DO NOTHING;
*/
