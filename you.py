SELECT
    'CONSUMPTION' AS domain,
    mm.model_name,
    cbb.name AS building_block,
    EXTRACT(MONTH FROM cpv.period_month)::int AS month_num,
    ROUND(SUM(cpv.value_in_thousands) / 1000.0, 4) AS value_in_millions
FROM public.consumption_planning_rows cpr
INNER JOIN public.consumption_building_blocks cbb
    ON cpr.building_block_id = cbb.block_id
INNER JOIN public.consumption_planning_values cpv
    ON cpr.row_id = cpv.row_id
INNER JOIN public.master_models mm
    ON cpr.model_id = mm.model_id
INNER JOIN public.consumption_snapshots s
    ON cpr.snapshot_id = s.snapshot_id
INNER JOIN public.planning_cycles pc
    ON s.cycle_id = pc.cycle_id
WHERE
    cpr.is_deleted = FALSE
    AND cbb.is_active = TRUE
    AND mm.is_active = TRUE
    AND mm.model_name ILIKE '%CHILDREN%MOTRIN%' -- Remove this line if you want all models
    AND UPPER(pc.snapshot_type) = 'BP'          -- <--- Target BP Snapshot
    AND EXTRACT(YEAR FROM cpv.period_month) = 2026 -- Plan year
GROUP BY mm.model_name, cbb.name, month_num
ORDER BY mm.model_name, cbb.name, month_num;
