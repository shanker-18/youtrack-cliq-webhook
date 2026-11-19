                    FROM consumption_audit_history
                    WHERE snapshot_id = %s
                      AND value_id IS NOT NULL
                      AND value_id IN (
                          SELECT v2.value_id
                          FROM consumption_planning_values v2
                          JOIN consumption_planning_rows r2 ON v2.row_id = r2.row_id
                          WHERE r2.snapshot_id = %s
                            AND r2.building_block_id = %s
                      )
                    GROUP BY value_id
