-- =============================================================================
-- SGA Inventory PostgreSQL Schema - Indexes
-- =============================================================================
-- Optimized indexes for common query patterns.
--
-- Index Strategy:
-- - B-tree for equality and range queries
-- - GIN for full-text search and JSONB
-- - Partial indexes for frequently filtered conditions
-- - Composite indexes for common joins
--
-- Naming Convention:
-- - idx_{table}_{columns}
-- - idx_{table}_{column}_gin (for GIN indexes)
-- - idx_{table}_{column}_partial (for partial indexes)
-- =============================================================================

SET search_path TO sga, public;

-- =============================================================================
-- Projects Indexes
-- =============================================================================

CREATE INDEX idx_projects_code ON sga.projects(project_code);
CREATE INDEX idx_projects_client ON sga.projects(client_name);
CREATE INDEX idx_projects_active ON sga.projects(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_projects_dates ON sga.projects(start_date, end_date);

-- =============================================================================
-- Locations Indexes
-- =============================================================================

CREATE INDEX idx_locations_code ON sga.locations(location_code);
CREATE INDEX idx_locations_parent ON sga.locations(parent_location_id);
CREATE INDEX idx_locations_type ON sga.locations(location_type);
CREATE INDEX idx_locations_active ON sga.locations(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_locations_hierarchy ON sga.locations(location_id, parent_location_id);

-- =============================================================================
-- Part Numbers Indexes
-- =============================================================================

CREATE INDEX idx_part_numbers_pn ON sga.part_numbers(part_number);
CREATE INDEX idx_part_numbers_category ON sga.part_numbers(category);
CREATE INDEX idx_part_numbers_manufacturer ON sga.part_numbers(manufacturer);
CREATE INDEX idx_part_numbers_active ON sga.part_numbers(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_part_numbers_serialized ON sga.part_numbers(is_serialized) WHERE is_serialized = TRUE;

-- Full-text search index
CREATE INDEX idx_part_numbers_search_gin ON sga.part_numbers USING GIN(search_vector);

-- =============================================================================
-- Assets Indexes (Critical for performance)
-- =============================================================================

-- Primary lookups
CREATE INDEX idx_assets_serial ON sga.assets(serial_number);
CREATE INDEX idx_assets_part_number ON sga.assets(part_number_id);
CREATE INDEX idx_assets_location ON sga.assets(location_id);
CREATE INDEX idx_assets_project ON sga.assets(project_id);
CREATE INDEX idx_assets_status ON sga.assets(status);

-- Composite indexes for common queries
CREATE INDEX idx_assets_location_status ON sga.assets(location_id, status);
CREATE INDEX idx_assets_project_status ON sga.assets(project_id, status);
CREATE INDEX idx_assets_pn_location ON sga.assets(part_number_id, location_id);
CREATE INDEX idx_assets_pn_project ON sga.assets(part_number_id, project_id);

-- Partial indexes for active assets
CREATE INDEX idx_assets_active_in_stock ON sga.assets(location_id, part_number_id)
    WHERE is_active = TRUE AND status = 'IN_STOCK';

-- Timestamp indexes
CREATE INDEX idx_assets_created ON sga.assets(created_at DESC);
CREATE INDEX idx_assets_last_movement ON sga.assets(last_movement_at DESC);

-- NF tracking
CREATE INDEX idx_assets_nf ON sga.assets(nf_number, nf_date);

-- =============================================================================
-- Balances Indexes
-- =============================================================================

-- Primary composite key equivalent
CREATE INDEX idx_balances_composite ON sga.balances(part_number_id, location_id, project_id);
CREATE INDEX idx_balances_location ON sga.balances(location_id);
CREATE INDEX idx_balances_project ON sga.balances(project_id);

-- Low stock alert queries
CREATE INDEX idx_balances_low_stock ON sga.balances(quantity_available)
    WHERE quantity_available <= 0;

-- =============================================================================
-- Movements Indexes (Critical for audit and reporting)
-- =============================================================================

-- Type and date queries
CREATE INDEX idx_movements_type ON sga.movements(movement_type);
CREATE INDEX idx_movements_date ON sga.movements(movement_date DESC);
CREATE INDEX idx_movements_type_date ON sga.movements(movement_type, movement_date DESC);

-- Location tracking
CREATE INDEX idx_movements_source ON sga.movements(source_location_id);
CREATE INDEX idx_movements_destination ON sga.movements(destination_location_id);

-- Project and part number
CREATE INDEX idx_movements_project ON sga.movements(project_id);
CREATE INDEX idx_movements_pn ON sga.movements(part_number_id);
CREATE INDEX idx_movements_pn_date ON sga.movements(part_number_id, movement_date DESC);

-- NF tracking
CREATE INDEX idx_movements_nf ON sga.movements(nf_number, nf_date);
CREATE INDEX idx_movements_nf_key ON sga.movements(nf_key) WHERE nf_key IS NOT NULL;

-- Date partitioning support (for monthly queries)
CREATE INDEX idx_movements_month ON sga.movements(DATE_TRUNC('month', movement_date));

-- Approval tracking
CREATE INDEX idx_movements_pending_approval ON sga.movements(movement_type, created_at)
    WHERE approved_at IS NULL;

-- =============================================================================
-- Movement Items Indexes
-- =============================================================================

CREATE INDEX idx_movement_items_movement ON sga.movement_items(movement_id);
CREATE INDEX idx_movement_items_asset ON sga.movement_items(asset_id);
CREATE INDEX idx_movement_items_serial ON sga.movement_items(serial_number);

-- =============================================================================
-- Reservations Indexes
-- =============================================================================

CREATE INDEX idx_reservations_pn_location ON sga.reservations(part_number_id, location_id);
CREATE INDEX idx_reservations_project ON sga.reservations(project_id);
CREATE INDEX idx_reservations_active ON sga.reservations(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_reservations_expires ON sga.reservations(expires_at) WHERE is_active = TRUE;

-- =============================================================================
-- Pending Entries Indexes
-- =============================================================================

CREATE INDEX idx_pending_entries_status ON sga.pending_entries(status);
CREATE INDEX idx_pending_entries_source ON sga.pending_entries(source_type);
CREATE INDEX idx_pending_entries_nf ON sga.pending_entries(nf_number, nf_date);
CREATE INDEX idx_pending_entries_nf_key ON sga.pending_entries(nf_key) WHERE nf_key IS NOT NULL;
CREATE INDEX idx_pending_entries_created ON sga.pending_entries(created_at DESC);

-- Partial index for pending items
CREATE INDEX idx_pending_entries_pending ON sga.pending_entries(created_at DESC)
    WHERE status = 'PENDING';

-- =============================================================================
-- Pending Entry Items Indexes
-- =============================================================================

CREATE INDEX idx_pending_entry_items_entry ON sga.pending_entry_items(entry_id);
CREATE INDEX idx_pending_entry_items_pn ON sga.pending_entry_items(part_number);
CREATE INDEX idx_pending_entry_items_matched ON sga.pending_entry_items(matched_part_number_id)
    WHERE matched_part_number_id IS NOT NULL;
CREATE INDEX idx_pending_entry_items_unprocessed ON sga.pending_entry_items(entry_id)
    WHERE is_processed = FALSE;

-- =============================================================================
-- Inventory Campaigns Indexes
-- =============================================================================

CREATE INDEX idx_campaigns_status ON sga.inventory_campaigns(status);
CREATE INDEX idx_campaigns_location ON sga.inventory_campaigns(location_id);
CREATE INDEX idx_campaigns_project ON sga.inventory_campaigns(project_id);
CREATE INDEX idx_campaigns_dates ON sga.inventory_campaigns(start_date, end_date);

-- =============================================================================
-- Count Results Indexes
-- =============================================================================

CREATE INDEX idx_count_results_campaign ON sga.count_results(campaign_id);
CREATE INDEX idx_count_results_pn ON sga.count_results(part_number_id);
CREATE INDEX idx_count_results_location ON sga.count_results(location_id);
CREATE INDEX idx_count_results_variance ON sga.count_results(variance) WHERE variance != 0;

-- =============================================================================
-- Divergences Indexes
-- =============================================================================

CREATE INDEX idx_divergences_type ON sga.divergences(divergence_type);
CREATE INDEX idx_divergences_status ON sga.divergences(status);
CREATE INDEX idx_divergences_pn ON sga.divergences(part_number_id);
CREATE INDEX idx_divergences_location ON sga.divergences(location_id);
CREATE INDEX idx_divergences_project ON sga.divergences(project_id);
CREATE INDEX idx_divergences_campaign ON sga.divergences(campaign_id) WHERE campaign_id IS NOT NULL;
CREATE INDEX idx_divergences_open ON sga.divergences(created_at DESC) WHERE status = 'OPEN';

-- =============================================================================
-- End of indexes
-- =============================================================================
