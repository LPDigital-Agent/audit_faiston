-- =============================================================================
-- SGA Inventory PostgreSQL Schema - Materialized Views
-- =============================================================================
-- Pre-computed views for dashboard and reporting performance.
--
-- Refresh Strategy:
-- - Daily views: Refresh via pg_cron or application job
-- - Real-time views: Refresh on-demand via API
--
-- Benefits:
-- - Complex aggregations pre-computed
-- - Dashboard queries run in milliseconds
-- - Reduced load on transactional tables
-- =============================================================================

SET search_path TO sga, public;

-- =============================================================================
-- View: mv_inventory_summary
-- =============================================================================
-- Summary of inventory by location and part number.
-- Used for: Dashboard KPIs, inventory overview

CREATE MATERIALIZED VIEW sga.mv_inventory_summary AS
SELECT
    l.location_id,
    l.location_code,
    l.location_name,
    pn.part_number_id,
    pn.part_number,
    pn.description,
    pn.category,
    COALESCE(b.quantity_total, 0) AS quantity_total,
    COALESCE(b.quantity_reserved, 0) AS quantity_reserved,
    COALESCE(b.quantity_total, 0) - COALESCE(b.quantity_reserved, 0) AS quantity_available,
    pn.min_stock_level,
    CASE
        WHEN COALESCE(b.quantity_total, 0) - COALESCE(b.quantity_reserved, 0) <= 0 THEN 'OUT_OF_STOCK'
        WHEN COALESCE(b.quantity_total, 0) - COALESCE(b.quantity_reserved, 0) <= pn.min_stock_level THEN 'LOW_STOCK'
        ELSE 'IN_STOCK'
    END AS stock_status,
    b.last_movement_at,
    b.last_count_at
FROM sga.balances b
JOIN sga.locations l ON b.location_id = l.location_id
JOIN sga.part_numbers pn ON b.part_number_id = pn.part_number_id
WHERE l.is_active = TRUE
  AND pn.is_active = TRUE;

CREATE UNIQUE INDEX idx_mv_inventory_summary_pk ON sga.mv_inventory_summary(location_id, part_number_id);
CREATE INDEX idx_mv_inventory_summary_location ON sga.mv_inventory_summary(location_code);
CREATE INDEX idx_mv_inventory_summary_pn ON sga.mv_inventory_summary(part_number);
CREATE INDEX idx_mv_inventory_summary_status ON sga.mv_inventory_summary(stock_status);

COMMENT ON MATERIALIZED VIEW sga.mv_inventory_summary IS 'Inventory summary by location and part number';

-- =============================================================================
-- View: mv_movement_daily_stats
-- =============================================================================
-- Daily movement statistics for trend analysis.
-- Used for: Dashboard charts, movement reports

CREATE MATERIALIZED VIEW sga.mv_movement_daily_stats AS
SELECT
    DATE(movement_date) AS movement_day,
    movement_type,
    COUNT(*) AS movement_count,
    SUM(quantity) AS total_quantity,
    COUNT(DISTINCT part_number_id) AS unique_parts,
    COUNT(DISTINCT COALESCE(source_location_id, destination_location_id)) AS locations_affected
FROM sga.movements
WHERE movement_date >= NOW() - INTERVAL '90 days'
GROUP BY DATE(movement_date), movement_type
ORDER BY movement_day DESC, movement_type;

CREATE INDEX idx_mv_movement_daily_day ON sga.mv_movement_daily_stats(movement_day DESC);
CREATE INDEX idx_mv_movement_daily_type ON sga.mv_movement_daily_stats(movement_type);

COMMENT ON MATERIALIZED VIEW sga.mv_movement_daily_stats IS 'Daily movement statistics for 90 days';

-- =============================================================================
-- View: mv_project_inventory
-- =============================================================================
-- Inventory by project for client reporting.
-- Used for: Project dashboards, client reports

CREATE MATERIALIZED VIEW sga.mv_project_inventory AS
SELECT
    p.project_id,
    p.project_code,
    p.project_name,
    p.client_name,
    COUNT(DISTINCT a.asset_id) AS total_assets,
    COUNT(DISTINCT a.asset_id) FILTER (WHERE a.status = 'IN_STOCK') AS assets_in_stock,
    COUNT(DISTINCT a.asset_id) FILTER (WHERE a.status = 'IN_TRANSIT') AS assets_in_transit,
    COUNT(DISTINCT a.asset_id) FILTER (WHERE a.status = 'RESERVED') AS assets_reserved,
    COUNT(DISTINCT a.asset_id) FILTER (WHERE a.status = 'INSTALLED') AS assets_installed,
    COUNT(DISTINCT a.part_number_id) AS unique_part_numbers,
    COUNT(DISTINCT a.location_id) AS locations_used,
    SUM(a.acquisition_cost) AS total_acquisition_cost,
    MAX(a.last_movement_at) AS last_movement_at
FROM sga.projects p
LEFT JOIN sga.assets a ON p.project_id = a.project_id AND a.is_active = TRUE
WHERE p.is_active = TRUE
GROUP BY p.project_id, p.project_code, p.project_name, p.client_name;

CREATE UNIQUE INDEX idx_mv_project_inventory_pk ON sga.mv_project_inventory(project_id);
CREATE INDEX idx_mv_project_inventory_code ON sga.mv_project_inventory(project_code);
CREATE INDEX idx_mv_project_inventory_client ON sga.mv_project_inventory(client_name);

COMMENT ON MATERIALIZED VIEW sga.mv_project_inventory IS 'Inventory summary by project';

-- =============================================================================
-- View: mv_location_utilization
-- =============================================================================
-- Location utilization and capacity metrics.
-- Used for: Warehouse planning, capacity analysis

CREATE MATERIALIZED VIEW sga.mv_location_utilization AS
SELECT
    l.location_id,
    l.location_code,
    l.location_name,
    l.location_type,
    COUNT(DISTINCT a.asset_id) AS total_assets,
    COUNT(DISTINCT a.part_number_id) AS unique_parts,
    COUNT(DISTINCT a.project_id) AS projects_stored,
    SUM(CASE WHEN a.status = 'IN_STOCK' THEN 1 ELSE 0 END) AS available_assets,
    SUM(CASE WHEN a.status = 'RESERVED' THEN 1 ELSE 0 END) AS reserved_assets,
    MAX(a.last_movement_at) AS last_activity
FROM sga.locations l
LEFT JOIN sga.assets a ON l.location_id = a.location_id AND a.is_active = TRUE
WHERE l.is_active = TRUE
GROUP BY l.location_id, l.location_code, l.location_name, l.location_type;

CREATE UNIQUE INDEX idx_mv_location_utilization_pk ON sga.mv_location_utilization(location_id);
CREATE INDEX idx_mv_location_utilization_type ON sga.mv_location_utilization(location_type);

COMMENT ON MATERIALIZED VIEW sga.mv_location_utilization IS 'Location utilization metrics';

-- =============================================================================
-- View: mv_divergence_summary
-- =============================================================================
-- Divergence summary for accuracy KPIs.
-- Used for: Accuracy dashboard, compliance reports

CREATE MATERIALIZED VIEW sga.mv_divergence_summary AS
SELECT
    DATE_TRUNC('month', d.created_at) AS month,
    d.divergence_type,
    d.status,
    COUNT(*) AS divergence_count,
    SUM(ABS(d.variance)) AS total_variance,
    AVG(ABS(d.variance)) AS avg_variance,
    COUNT(*) FILTER (WHERE d.status = 'RESOLVED') AS resolved_count,
    AVG(EXTRACT(EPOCH FROM (d.resolved_at - d.created_at)) / 3600)
        FILTER (WHERE d.resolved_at IS NOT NULL) AS avg_resolution_hours
FROM sga.divergences d
WHERE d.created_at >= NOW() - INTERVAL '12 months'
GROUP BY DATE_TRUNC('month', d.created_at), d.divergence_type, d.status
ORDER BY month DESC;

CREATE INDEX idx_mv_divergence_summary_month ON sga.mv_divergence_summary(month DESC);
CREATE INDEX idx_mv_divergence_summary_type ON sga.mv_divergence_summary(divergence_type);

COMMENT ON MATERIALIZED VIEW sga.mv_divergence_summary IS 'Divergence summary for accuracy KPIs';

-- =============================================================================
-- View: mv_pending_tasks_dashboard
-- =============================================================================
-- Pending tasks summary for operator dashboard.
-- Used for: Task inbox, workload distribution

CREATE MATERIALIZED VIEW sga.mv_pending_tasks_dashboard AS
SELECT
    pe.status,
    pe.source_type,
    COUNT(*) AS entry_count,
    SUM(pe.total_items) AS total_items,
    MIN(pe.created_at) AS oldest_entry,
    AVG(EXTRACT(EPOCH FROM (NOW() - pe.created_at)) / 3600) AS avg_age_hours
FROM sga.pending_entries pe
WHERE pe.status IN ('PENDING', 'PROCESSING')
GROUP BY pe.status, pe.source_type;

COMMENT ON MATERIALIZED VIEW sga.mv_pending_tasks_dashboard IS 'Pending tasks summary for dashboard';

-- =============================================================================
-- View: mv_asset_timeline_summary
-- =============================================================================
-- Asset movement history summary for timeline views.
-- Used for: Asset detail page, timeline visualization

CREATE MATERIALIZED VIEW sga.mv_asset_timeline_summary AS
SELECT
    a.asset_id,
    a.serial_number,
    pn.part_number,
    pn.description,
    COUNT(mi.movement_item_id) AS total_movements,
    MIN(m.movement_date) AS first_movement,
    MAX(m.movement_date) AS last_movement,
    COUNT(DISTINCT m.source_location_id) AS source_locations,
    COUNT(DISTINCT m.destination_location_id) AS destination_locations,
    array_agg(DISTINCT m.movement_type ORDER BY m.movement_type) AS movement_types
FROM sga.assets a
JOIN sga.part_numbers pn ON a.part_number_id = pn.part_number_id
LEFT JOIN sga.movement_items mi ON a.asset_id = mi.asset_id
LEFT JOIN sga.movements m ON mi.movement_id = m.movement_id
WHERE a.is_active = TRUE
GROUP BY a.asset_id, a.serial_number, pn.part_number, pn.description;

CREATE UNIQUE INDEX idx_mv_asset_timeline_pk ON sga.mv_asset_timeline_summary(asset_id);
CREATE INDEX idx_mv_asset_timeline_serial ON sga.mv_asset_timeline_summary(serial_number);
CREATE INDEX idx_mv_asset_timeline_pn ON sga.mv_asset_timeline_summary(part_number);

COMMENT ON MATERIALIZED VIEW sga.mv_asset_timeline_summary IS 'Asset movement timeline summary';

-- =============================================================================
-- View: mv_inventory_accuracy_kpi
-- =============================================================================
-- Inventory accuracy KPIs for management dashboard.
-- Used for: Executive dashboard, compliance metrics

CREATE MATERIALIZED VIEW sga.mv_inventory_accuracy_kpi AS
WITH counts AS (
    SELECT
        DATE_TRUNC('month', c.start_date) AS month,
        SUM(c.total_items) AS total_counted,
        SUM(c.counted_items) AS items_counted,
        SUM(c.divergence_count) AS items_with_variance
    FROM sga.inventory_campaigns c
    WHERE c.status = 'COMPLETED'
      AND c.start_date >= NOW() - INTERVAL '12 months'
    GROUP BY DATE_TRUNC('month', c.start_date)
)
SELECT
    month,
    total_counted,
    items_counted,
    items_with_variance,
    CASE
        WHEN items_counted > 0 THEN
            ROUND((1.0 - (items_with_variance::NUMERIC / items_counted)) * 100, 2)
        ELSE NULL
    END AS accuracy_percentage,
    CASE
        WHEN total_counted > 0 THEN
            ROUND((items_counted::NUMERIC / total_counted) * 100, 2)
        ELSE NULL
    END AS completion_percentage
FROM counts
ORDER BY month DESC;

CREATE INDEX idx_mv_accuracy_kpi_month ON sga.mv_inventory_accuracy_kpi(month DESC);

COMMENT ON MATERIALIZED VIEW sga.mv_inventory_accuracy_kpi IS 'Monthly inventory accuracy KPIs';

-- =============================================================================
-- Function: refresh_all_materialized_views
-- =============================================================================
-- Convenience function to refresh all materialized views.
-- Call via pg_cron or application scheduler.

CREATE OR REPLACE FUNCTION sga.refresh_all_materialized_views()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY sga.mv_inventory_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY sga.mv_movement_daily_stats;
    REFRESH MATERIALIZED VIEW CONCURRENTLY sga.mv_project_inventory;
    REFRESH MATERIALIZED VIEW CONCURRENTLY sga.mv_location_utilization;
    REFRESH MATERIALIZED VIEW CONCURRENTLY sga.mv_divergence_summary;
    REFRESH MATERIALIZED VIEW sga.mv_pending_tasks_dashboard;  -- No unique index
    REFRESH MATERIALIZED VIEW CONCURRENTLY sga.mv_asset_timeline_summary;
    REFRESH MATERIALIZED VIEW sga.mv_inventory_accuracy_kpi;  -- No unique index
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Function: refresh_dashboard_views
-- =============================================================================
-- Refresh only views needed for dashboard (faster).

CREATE OR REPLACE FUNCTION sga.refresh_dashboard_views()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY sga.mv_inventory_summary;
    REFRESH MATERIALIZED VIEW sga.mv_pending_tasks_dashboard;
    REFRESH MATERIALIZED VIEW CONCURRENTLY sga.mv_location_utilization;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Grants for Lambda role
-- =============================================================================
-- These will be executed after role creation

-- Grant SELECT on all views to Lambda role
-- (Execute after role is created)
-- GRANT SELECT ON ALL TABLES IN SCHEMA sga TO sga_lambda_role;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA sga TO sga_lambda_role;

-- =============================================================================
-- End of materialized views
-- =============================================================================
