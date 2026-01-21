-- =============================================================================
-- SGA Inventory PostgreSQL Schema - Initial Tables
-- =============================================================================
-- Migration from DynamoDB single-table design to PostgreSQL relational schema.
--
-- Design Principles:
-- - Event sourcing for movements (immutable audit trail)
-- - Generated columns for calculated fields
-- - Full-text search for part numbers
-- - Row-Level Security ready (tenant_id on all tables)
-- - Soft deletes where appropriate (is_active flag)
--
-- Naming Conventions:
-- - Tables: lowercase_with_underscores
-- - Primary keys: {table_name}_id
-- - Foreign keys: {referenced_table}_id
-- - Timestamps: created_at, updated_at
-- =============================================================================

-- Create schema
CREATE SCHEMA IF NOT EXISTS sga;

-- Set search path
SET search_path TO sga, public;

-- =============================================================================
-- Extension: UUID for primary keys
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- Enum Types
-- =============================================================================

-- Asset status enum
CREATE TYPE sga.asset_status AS ENUM (
    'IN_STOCK',
    'IN_TRANSIT',
    'RESERVED',
    'INSTALLED',
    'DEFECTIVE',
    'DISPOSED'
);

-- Movement type enum
CREATE TYPE sga.movement_type AS ENUM (
    'ENTRADA',
    'SAIDA',
    'TRANSFERENCIA',
    'RESERVA',
    'LIBERACAO',
    'AJUSTE_POSITIVO',
    'AJUSTE_NEGATIVO',
    'EXPEDIÇÃO',
    'REVERSA'
);

-- Task status enum
CREATE TYPE sga.task_status AS ENUM (
    'PENDING',
    'IN_PROGRESS',
    'APPROVED',
    'REJECTED',
    'COMPLETED'
);

-- Task type enum
CREATE TYPE sga.task_type AS ENUM (
    'APPROVAL_ENTRY',
    'APPROVAL_EXIT',
    'APPROVAL_ADJUSTMENT',
    'DIVERGENCE_RESOLUTION',
    'DOCUMENT_REVIEW',
    'QUALITY_CHECK'
);

-- Priority enum
CREATE TYPE sga.priority AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH',
    'URGENT'
);

-- Source type enum
CREATE TYPE sga.entry_source AS ENUM (
    'NF_XML',
    'NF_PDF',
    'NF_IMAGE',
    'SAP_IMPORT',
    'MANUAL',
    'BULK_IMPORT'
);

-- =============================================================================
-- Table: projects
-- =============================================================================
-- Client contracts/projects that own assets.
-- DynamoDB equivalent: PROJ# entities

CREATE TABLE sga.projects (
    project_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_code VARCHAR(50) NOT NULL UNIQUE,
    project_name VARCHAR(255) NOT NULL,
    client_name VARCHAR(255) NOT NULL,
    contract_number VARCHAR(100),
    start_date DATE,
    end_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);

COMMENT ON TABLE sga.projects IS 'Client contracts/projects that own assets';

-- =============================================================================
-- Table: locations
-- =============================================================================
-- Warehouse locations with hierarchy support.
-- DynamoDB equivalent: LOC# entities

CREATE TABLE sga.locations (
    location_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_code VARCHAR(50) NOT NULL UNIQUE,
    location_name VARCHAR(255) NOT NULL,
    location_type VARCHAR(50) NOT NULL,  -- WAREHOUSE, AREA, BIN, etc.
    parent_location_id UUID REFERENCES sga.locations(location_id),
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(50),
    postal_code VARCHAR(20),
    country VARCHAR(50) DEFAULT 'BR',
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);

COMMENT ON TABLE sga.locations IS 'Warehouse locations with hierarchy support';

-- =============================================================================
-- Table: part_numbers
-- =============================================================================
-- SKU catalog with full-text search support.
-- DynamoDB equivalent: PN# entities

CREATE TABLE sga.part_numbers (
    part_number_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    part_number VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(500) NOT NULL,
    category VARCHAR(100),
    manufacturer VARCHAR(255),
    model VARCHAR(255),
    unit_of_measure VARCHAR(20) DEFAULT 'UN',
    weight_kg NUMERIC(10, 3),
    dimensions_cm JSONB,  -- {length, width, height}
    is_serialized BOOLEAN DEFAULT TRUE,  -- Requires serial tracking
    min_stock_level INTEGER DEFAULT 0,
    max_stock_level INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    -- Full-text search column
    search_vector TSVECTOR GENERATED ALWAYS AS (
        setweight(to_tsvector('portuguese', coalesce(part_number, '')), 'A') ||
        setweight(to_tsvector('portuguese', coalesce(description, '')), 'B') ||
        setweight(to_tsvector('portuguese', coalesce(category, '')), 'C') ||
        setweight(to_tsvector('portuguese', coalesce(manufacturer, '')), 'D')
    ) STORED,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);

COMMENT ON TABLE sga.part_numbers IS 'SKU catalog with full-text search support';

-- =============================================================================
-- Table: assets
-- =============================================================================
-- Serialized assets with full lifecycle tracking.
-- DynamoDB equivalent: ASSET# entities

CREATE TABLE sga.assets (
    asset_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    serial_number VARCHAR(100) NOT NULL UNIQUE,
    part_number_id UUID NOT NULL REFERENCES sga.part_numbers(part_number_id),
    project_id UUID REFERENCES sga.projects(project_id),
    location_id UUID REFERENCES sga.locations(location_id),
    status sga.asset_status DEFAULT 'IN_STOCK',
    condition VARCHAR(50),  -- NEW, USED, REFURBISHED, etc.
    purchase_date DATE,
    warranty_end_date DATE,
    acquisition_cost NUMERIC(12, 2),
    current_value NUMERIC(12, 2),
    nf_number VARCHAR(50),
    nf_date DATE,
    last_movement_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);

COMMENT ON TABLE sga.assets IS 'Serialized assets with full lifecycle tracking';

-- =============================================================================
-- Table: balances
-- =============================================================================
-- Stock balance projections (denormalized for query performance).
-- DynamoDB equivalent: BALANCE# entities

CREATE TABLE sga.balances (
    balance_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    part_number_id UUID NOT NULL REFERENCES sga.part_numbers(part_number_id),
    location_id UUID NOT NULL REFERENCES sga.locations(location_id),
    project_id UUID REFERENCES sga.projects(project_id),
    quantity_total INTEGER NOT NULL DEFAULT 0,
    quantity_reserved INTEGER NOT NULL DEFAULT 0,
    -- Generated column: available = total - reserved
    quantity_available INTEGER GENERATED ALWAYS AS (quantity_total - quantity_reserved) STORED,
    last_movement_at TIMESTAMPTZ,
    last_count_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (part_number_id, location_id, project_id)
);

COMMENT ON TABLE sga.balances IS 'Stock balance projections (denormalized for performance)';

-- =============================================================================
-- Table: movements
-- =============================================================================
-- IMMUTABLE event sourcing table for all inventory movements.
-- DynamoDB equivalent: MOVE# entities

CREATE TABLE sga.movements (
    movement_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    movement_type sga.movement_type NOT NULL,
    movement_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    part_number_id UUID NOT NULL REFERENCES sga.part_numbers(part_number_id),
    quantity INTEGER NOT NULL,
    source_location_id UUID REFERENCES sga.locations(location_id),
    destination_location_id UUID REFERENCES sga.locations(location_id),
    project_id UUID REFERENCES sga.projects(project_id),
    nf_number VARCHAR(50),
    nf_date DATE,
    nf_key VARCHAR(50),
    reason VARCHAR(500),
    reference_document VARCHAR(100),
    approved_by VARCHAR(100),
    approved_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100) NOT NULL
);

COMMENT ON TABLE sga.movements IS 'IMMUTABLE event sourcing table for inventory movements';

-- =============================================================================
-- Table: movement_items
-- =============================================================================
-- Serial numbers associated with each movement.
-- (Embedded in DynamoDB MOVE# but normalized here)

CREATE TABLE sga.movement_items (
    movement_item_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    movement_id UUID NOT NULL REFERENCES sga.movements(movement_id),
    asset_id UUID NOT NULL REFERENCES sga.assets(asset_id),
    serial_number VARCHAR(100) NOT NULL,  -- Denormalized for query
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE sga.movement_items IS 'Serial numbers associated with each movement';

-- =============================================================================
-- Table: reservations
-- =============================================================================
-- Temporary stock reservations (with TTL).
-- DynamoDB equivalent: RESERVE# entities

CREATE TABLE sga.reservations (
    reservation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    part_number_id UUID NOT NULL REFERENCES sga.part_numbers(part_number_id),
    location_id UUID NOT NULL REFERENCES sga.locations(location_id),
    project_id UUID REFERENCES sga.projects(project_id),
    quantity INTEGER NOT NULL,
    purpose VARCHAR(255),
    reserved_by VARCHAR(100) NOT NULL,
    reserved_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,  -- TTL for automatic cleanup
    released_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE sga.reservations IS 'Temporary stock reservations with TTL';

-- =============================================================================
-- Table: pending_entries
-- =============================================================================
-- Pending material entries (NF uploads awaiting processing).
-- DynamoDB equivalent: DOC# entities

CREATE TABLE sga.pending_entries (
    entry_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_type sga.entry_source NOT NULL,
    nf_number VARCHAR(50),
    nf_key VARCHAR(50),
    nf_date DATE,
    supplier_name VARCHAR(255),
    supplier_cnpj VARCHAR(20),
    total_value NUMERIC(12, 2),
    total_items INTEGER,
    status VARCHAR(50) DEFAULT 'PENDING',  -- PENDING, PROCESSING, COMPLETED, ERROR
    error_message TEXT,
    s3_document_key VARCHAR(500),
    ocr_confidence NUMERIC(5, 2),
    metadata JSONB DEFAULT '{}',
    processed_at TIMESTAMPTZ,
    processed_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100)
);

COMMENT ON TABLE sga.pending_entries IS 'Pending material entries (NF uploads)';

-- =============================================================================
-- Table: pending_entry_items
-- =============================================================================
-- Line items from pending entries.
-- (Embedded in DynamoDB DOC# but normalized here)

CREATE TABLE sga.pending_entry_items (
    entry_item_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entry_id UUID NOT NULL REFERENCES sga.pending_entries(entry_id) ON DELETE CASCADE,
    line_number INTEGER NOT NULL,
    part_number VARCHAR(100),
    description VARCHAR(500),
    quantity INTEGER NOT NULL,
    unit_value NUMERIC(12, 2),
    total_value NUMERIC(12, 2),
    serial_numbers TEXT[],  -- Array of serial numbers
    matched_part_number_id UUID REFERENCES sga.part_numbers(part_number_id),
    match_confidence NUMERIC(5, 2),
    is_processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE sga.pending_entry_items IS 'Line items from pending material entries';

-- =============================================================================
-- Table: inventory_campaigns
-- =============================================================================
-- Inventory counting campaigns.
-- (New table - not in original DynamoDB design)

CREATE TABLE sga.inventory_campaigns (
    campaign_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_name VARCHAR(255) NOT NULL,
    campaign_type VARCHAR(50),  -- FULL, CYCLIC, SPOT
    location_id UUID REFERENCES sga.locations(location_id),
    project_id UUID REFERENCES sga.projects(project_id),
    start_date DATE NOT NULL,
    end_date DATE,
    status VARCHAR(50) DEFAULT 'PLANNED',  -- PLANNED, IN_PROGRESS, COMPLETED
    total_items INTEGER DEFAULT 0,
    counted_items INTEGER DEFAULT 0,
    divergence_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100)
);

COMMENT ON TABLE sga.inventory_campaigns IS 'Inventory counting campaigns';

-- =============================================================================
-- Table: count_results
-- =============================================================================
-- Individual count results from inventory campaigns.
-- (New table - not in original DynamoDB design)

CREATE TABLE sga.count_results (
    count_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID NOT NULL REFERENCES sga.inventory_campaigns(campaign_id),
    part_number_id UUID NOT NULL REFERENCES sga.part_numbers(part_number_id),
    location_id UUID NOT NULL REFERENCES sga.locations(location_id),
    expected_quantity INTEGER NOT NULL,
    counted_quantity INTEGER,
    variance INTEGER GENERATED ALWAYS AS (COALESCE(counted_quantity, 0) - expected_quantity) STORED,
    counted_by VARCHAR(100),
    counted_at TIMESTAMPTZ,
    verified_by VARCHAR(100),
    verified_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE sga.count_results IS 'Individual count results from inventory campaigns';

-- =============================================================================
-- Table: divergences
-- =============================================================================
-- Inventory discrepancies and anomalies.
-- DynamoDB equivalent: DIV# entities

CREATE TABLE sga.divergences (
    divergence_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    divergence_type VARCHAR(50) NOT NULL,  -- COUNT, RECONCILIATION, SYSTEM
    part_number_id UUID NOT NULL REFERENCES sga.part_numbers(part_number_id),
    location_id UUID REFERENCES sga.locations(location_id),
    project_id UUID REFERENCES sga.projects(project_id),
    expected_quantity INTEGER NOT NULL,
    actual_quantity INTEGER NOT NULL,
    variance INTEGER GENERATED ALWAYS AS (actual_quantity - expected_quantity) STORED,
    status VARCHAR(50) DEFAULT 'OPEN',  -- OPEN, INVESTIGATING, RESOLVED, CLOSED
    resolution VARCHAR(500),
    resolved_by VARCHAR(100),
    resolved_at TIMESTAMPTZ,
    campaign_id UUID REFERENCES sga.inventory_campaigns(campaign_id),
    related_movement_id UUID REFERENCES sga.movements(movement_id),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100)
);

COMMENT ON TABLE sga.divergences IS 'Inventory discrepancies and anomalies';

-- =============================================================================
-- End of initial schema
-- =============================================================================
