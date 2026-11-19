-- V008: Performance indexes for audit history row_id seeks
-- Applied after V007__add_horizon_year_to_planning_rows.sql

CREATE INDEX IF NOT EXISTS idx_consumption_audit_row_perf
    ON consumption_audit_history (row_id, performed_at DESC);

CREATE INDEX IF NOT EXISTS idx_shipment_audit_row_perf
    ON shipment_audit_history (row_id, performed_at DESC);

CREATE INDEX IF NOT EXISTS idx_consumption_audit_row_val
    ON consumption_audit_history (row_id, value_id);

CREATE INDEX IF NOT EXISTS idx_shipment_audit_row_val
    ON shipment_audit_history (row_id, value_id);
