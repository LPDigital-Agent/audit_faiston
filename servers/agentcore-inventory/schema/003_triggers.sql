-- =============================================================================
-- SGA Inventory PostgreSQL Schema - Triggers & Functions
-- =============================================================================
-- Business logic implemented as database triggers for data integrity.
--
-- Key Triggers:
-- - updated_at auto-update on all tables
-- - Immutable movements (prevent UPDATE/DELETE)
-- - Balance recalculation on movement
-- - Reservation expiration cleanup
-- - Audit logging
-- =============================================================================

SET search_path TO sga, public;

-- =============================================================================
-- Function: update_updated_at_column
-- =============================================================================
-- Automatically sets updated_at to current timestamp on row update.

CREATE OR REPLACE FUNCTION sga.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to all tables with updated_at column
CREATE TRIGGER trg_projects_updated_at
    BEFORE UPDATE ON sga.projects
    FOR EACH ROW
    EXECUTE FUNCTION sga.update_updated_at_column();

CREATE TRIGGER trg_locations_updated_at
    BEFORE UPDATE ON sga.locations
    FOR EACH ROW
    EXECUTE FUNCTION sga.update_updated_at_column();

CREATE TRIGGER trg_part_numbers_updated_at
    BEFORE UPDATE ON sga.part_numbers
    FOR EACH ROW
    EXECUTE FUNCTION sga.update_updated_at_column();

CREATE TRIGGER trg_assets_updated_at
    BEFORE UPDATE ON sga.assets
    FOR EACH ROW
    EXECUTE FUNCTION sga.update_updated_at_column();

CREATE TRIGGER trg_balances_updated_at
    BEFORE UPDATE ON sga.balances
    FOR EACH ROW
    EXECUTE FUNCTION sga.update_updated_at_column();

CREATE TRIGGER trg_campaigns_updated_at
    BEFORE UPDATE ON sga.inventory_campaigns
    FOR EACH ROW
    EXECUTE FUNCTION sga.update_updated_at_column();

CREATE TRIGGER trg_divergences_updated_at
    BEFORE UPDATE ON sga.divergences
    FOR EACH ROW
    EXECUTE FUNCTION sga.update_updated_at_column();

-- =============================================================================
-- Function: prevent_movement_modification
-- =============================================================================
-- CRITICAL: Movements are IMMUTABLE for audit compliance.
-- Prevents UPDATE and DELETE on movements table.

CREATE OR REPLACE FUNCTION sga.prevent_movement_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Movements are immutable and cannot be modified or deleted. Create a new adjustment movement instead.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_movements_immutable
    BEFORE UPDATE OR DELETE ON sga.movements
    FOR EACH ROW
    EXECUTE FUNCTION sga.prevent_movement_modification();

-- =============================================================================
-- Function: update_balance_on_movement
-- =============================================================================
-- Automatically updates balance projections when a movement is created.

CREATE OR REPLACE FUNCTION sga.update_balance_on_movement()
RETURNS TRIGGER AS $$
DECLARE
    v_part_number_id UUID;
    v_location_id UUID;
    v_project_id UUID;
    v_quantity INTEGER;
BEGIN
    v_part_number_id := NEW.part_number_id;
    v_project_id := NEW.project_id;
    v_quantity := NEW.quantity;

    -- Handle different movement types
    CASE NEW.movement_type
        WHEN 'ENTRADA', 'AJUSTE_POSITIVO', 'REVERSA' THEN
            -- Increase destination balance
            v_location_id := NEW.destination_location_id;
            INSERT INTO sga.balances (part_number_id, location_id, project_id, quantity_total, last_movement_at)
            VALUES (v_part_number_id, v_location_id, v_project_id, v_quantity, NOW())
            ON CONFLICT (part_number_id, location_id, project_id)
            DO UPDATE SET
                quantity_total = sga.balances.quantity_total + v_quantity,
                last_movement_at = NOW(),
                updated_at = NOW();

        WHEN 'SAIDA', 'AJUSTE_NEGATIVO', 'EXPEDIÇÃO' THEN
            -- Decrease source balance
            v_location_id := NEW.source_location_id;
            UPDATE sga.balances
            SET quantity_total = quantity_total - v_quantity,
                last_movement_at = NOW(),
                updated_at = NOW()
            WHERE part_number_id = v_part_number_id
              AND location_id = v_location_id
              AND (project_id = v_project_id OR (project_id IS NULL AND v_project_id IS NULL));

        WHEN 'TRANSFERENCIA' THEN
            -- Decrease source
            UPDATE sga.balances
            SET quantity_total = quantity_total - v_quantity,
                last_movement_at = NOW(),
                updated_at = NOW()
            WHERE part_number_id = v_part_number_id
              AND location_id = NEW.source_location_id
              AND (project_id = v_project_id OR (project_id IS NULL AND v_project_id IS NULL));

            -- Increase destination
            INSERT INTO sga.balances (part_number_id, location_id, project_id, quantity_total, last_movement_at)
            VALUES (v_part_number_id, NEW.destination_location_id, v_project_id, v_quantity, NOW())
            ON CONFLICT (part_number_id, location_id, project_id)
            DO UPDATE SET
                quantity_total = sga.balances.quantity_total + v_quantity,
                last_movement_at = NOW(),
                updated_at = NOW();

        WHEN 'RESERVA' THEN
            -- Increase reserved quantity
            UPDATE sga.balances
            SET quantity_reserved = quantity_reserved + v_quantity,
                last_movement_at = NOW(),
                updated_at = NOW()
            WHERE part_number_id = v_part_number_id
              AND location_id = NEW.source_location_id
              AND (project_id = v_project_id OR (project_id IS NULL AND v_project_id IS NULL));

        WHEN 'LIBERACAO' THEN
            -- Decrease reserved quantity
            UPDATE sga.balances
            SET quantity_reserved = GREATEST(0, quantity_reserved - v_quantity),
                last_movement_at = NOW(),
                updated_at = NOW()
            WHERE part_number_id = v_part_number_id
              AND location_id = NEW.source_location_id
              AND (project_id = v_project_id OR (project_id IS NULL AND v_project_id IS NULL));

        ELSE
            -- Unknown movement type - log warning
            RAISE WARNING 'Unknown movement type: %', NEW.movement_type;
    END CASE;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_movements_update_balance
    AFTER INSERT ON sga.movements
    FOR EACH ROW
    EXECUTE FUNCTION sga.update_balance_on_movement();

-- =============================================================================
-- Function: update_asset_on_movement
-- =============================================================================
-- Updates asset status and location when movement items are created.

CREATE OR REPLACE FUNCTION sga.update_asset_on_movement_item()
RETURNS TRIGGER AS $$
DECLARE
    v_movement RECORD;
BEGIN
    -- Get the parent movement
    SELECT * INTO v_movement FROM sga.movements WHERE movement_id = NEW.movement_id;

    -- Update asset based on movement type
    CASE v_movement.movement_type
        WHEN 'ENTRADA', 'REVERSA' THEN
            UPDATE sga.assets
            SET location_id = v_movement.destination_location_id,
                project_id = v_movement.project_id,
                status = 'IN_STOCK',
                last_movement_at = v_movement.movement_date,
                nf_number = COALESCE(v_movement.nf_number, nf_number),
                nf_date = COALESCE(v_movement.nf_date, nf_date),
                updated_at = NOW()
            WHERE asset_id = NEW.asset_id;

        WHEN 'SAIDA', 'EXPEDIÇÃO' THEN
            UPDATE sga.assets
            SET status = 'IN_TRANSIT',
                last_movement_at = v_movement.movement_date,
                updated_at = NOW()
            WHERE asset_id = NEW.asset_id;

        WHEN 'TRANSFERENCIA' THEN
            UPDATE sga.assets
            SET location_id = v_movement.destination_location_id,
                last_movement_at = v_movement.movement_date,
                updated_at = NOW()
            WHERE asset_id = NEW.asset_id;

        WHEN 'RESERVA' THEN
            UPDATE sga.assets
            SET status = 'RESERVED',
                last_movement_at = v_movement.movement_date,
                updated_at = NOW()
            WHERE asset_id = NEW.asset_id;

        WHEN 'LIBERACAO' THEN
            UPDATE sga.assets
            SET status = 'IN_STOCK',
                last_movement_at = v_movement.movement_date,
                updated_at = NOW()
            WHERE asset_id = NEW.asset_id;

        ELSE
            -- Just update last_movement_at
            UPDATE sga.assets
            SET last_movement_at = v_movement.movement_date,
                updated_at = NOW()
            WHERE asset_id = NEW.asset_id;
    END CASE;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_movement_items_update_asset
    AFTER INSERT ON sga.movement_items
    FOR EACH ROW
    EXECUTE FUNCTION sga.update_asset_on_movement_item();

-- =============================================================================
-- Function: release_expired_reservations
-- =============================================================================
-- Called periodically to release expired reservations.
-- Can be triggered by pg_cron or application code.

CREATE OR REPLACE FUNCTION sga.release_expired_reservations()
RETURNS INTEGER AS $$
DECLARE
    v_released_count INTEGER;
    v_reservation RECORD;
BEGIN
    v_released_count := 0;

    FOR v_reservation IN
        SELECT * FROM sga.reservations
        WHERE is_active = TRUE
          AND expires_at < NOW()
    LOOP
        -- Update balance
        UPDATE sga.balances
        SET quantity_reserved = GREATEST(0, quantity_reserved - v_reservation.quantity),
            updated_at = NOW()
        WHERE part_number_id = v_reservation.part_number_id
          AND location_id = v_reservation.location_id
          AND (project_id = v_reservation.project_id OR (project_id IS NULL AND v_reservation.project_id IS NULL));

        -- Mark reservation as released
        UPDATE sga.reservations
        SET is_active = FALSE,
            released_at = NOW()
        WHERE reservation_id = v_reservation.reservation_id;

        v_released_count := v_released_count + 1;
    END LOOP;

    RETURN v_released_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Function: validate_movement_quantity
-- =============================================================================
-- Validates that there's sufficient stock for outbound movements.

CREATE OR REPLACE FUNCTION sga.validate_movement_quantity()
RETURNS TRIGGER AS $$
DECLARE
    v_available INTEGER;
BEGIN
    -- Only validate outbound movements
    IF NEW.movement_type IN ('SAIDA', 'TRANSFERENCIA', 'EXPEDIÇÃO', 'AJUSTE_NEGATIVO') THEN
        SELECT COALESCE(quantity_available, 0) INTO v_available
        FROM sga.balances
        WHERE part_number_id = NEW.part_number_id
          AND location_id = NEW.source_location_id
          AND (project_id = NEW.project_id OR (project_id IS NULL AND NEW.project_id IS NULL));

        IF v_available IS NULL OR v_available < NEW.quantity THEN
            RAISE EXCEPTION 'Insufficient stock. Available: %, Requested: %', COALESCE(v_available, 0), NEW.quantity;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_movements_validate_quantity
    BEFORE INSERT ON sga.movements
    FOR EACH ROW
    EXECUTE FUNCTION sga.validate_movement_quantity();

-- =============================================================================
-- Function: update_campaign_stats
-- =============================================================================
-- Updates campaign statistics when count results are added/modified.

CREATE OR REPLACE FUNCTION sga.update_campaign_stats()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE sga.inventory_campaigns
    SET total_items = (SELECT COUNT(*) FROM sga.count_results WHERE campaign_id = NEW.campaign_id),
        counted_items = (SELECT COUNT(*) FROM sga.count_results WHERE campaign_id = NEW.campaign_id AND counted_quantity IS NOT NULL),
        divergence_count = (SELECT COUNT(*) FROM sga.count_results WHERE campaign_id = NEW.campaign_id AND variance != 0),
        updated_at = NOW()
    WHERE campaign_id = NEW.campaign_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_count_results_update_stats
    AFTER INSERT OR UPDATE ON sga.count_results
    FOR EACH ROW
    EXECUTE FUNCTION sga.update_campaign_stats();

-- =============================================================================
-- Function: create_divergence_from_count
-- =============================================================================
-- Automatically creates divergence record when count result shows variance.

CREATE OR REPLACE FUNCTION sga.create_divergence_from_count()
RETURNS TRIGGER AS $$
BEGIN
    -- Only create divergence if there's a variance and count is complete
    IF NEW.counted_quantity IS NOT NULL AND NEW.variance != 0 THEN
        INSERT INTO sga.divergences (
            divergence_type,
            part_number_id,
            location_id,
            expected_quantity,
            actual_quantity,
            campaign_id,
            created_by
        )
        VALUES (
            'COUNT',
            NEW.part_number_id,
            NEW.location_id,
            NEW.expected_quantity,
            NEW.counted_quantity,
            NEW.campaign_id,
            NEW.counted_by
        )
        ON CONFLICT DO NOTHING;  -- Avoid duplicate divergences
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_count_results_create_divergence
    AFTER INSERT OR UPDATE OF counted_quantity ON sga.count_results
    FOR EACH ROW
    EXECUTE FUNCTION sga.create_divergence_from_count();

-- =============================================================================
-- End of triggers
-- =============================================================================
