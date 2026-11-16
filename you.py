SELECT
    cbb.name AS building_block,
    EXTRACT(MONTH FROM cpv.period_month)::int AS month_num,
    TO_CHAR(cpv.period_month, 'Mon') AS month_name,
    SUM(cpv.value_in_thousands) AS value_in_thousands,
    ROUND((SUM(cpv.value_in_thousands) / 1000.0)::numeric, 4) AS value_in_millions
FROM public.consumption_planning_rows cpr
INNER JOIN public.consumption_building_blocks cbb
    ON cpr.building_block_id = cbb.block_id
INNER JOIN public.consumption_planning_values cpv
    ON cpr.row_id = cpv.row_id
INNER JOIN public.master_models mm
    ON cpr.model_id = mm.model_id
WHERE
    UPPER(TRIM(mm.model_name)) LIKE '%CHILDREN%MOTRIN%'
    AND cpr.is_deleted = FALSE
    AND cbb.is_active = TRUE
    AND mm.is_active = TRUE
    AND EXTRACT(YEAR FROM cpv.period_month) = 2026
    AND (
        cpr.snapshot_id IS NULL 
        OR cpr.snapshot_id = (
            SELECT s.snapshot_id
            FROM public.consumption_snapshots s
            JOIN public.planning_cycles pc ON s.cycle_id = pc.cycle_id
            WHERE (UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%CURRENT%' OR pc.is_active = TRUE)
            ORDER BY pc.cycle_month DESC NULLS LAST, s.snapshot_id DESC
            LIMIT 1
        )
    )
GROUP BY
    cbb.name,
    month_num,
    cpv.period_month
ORDER BY
    cbb.name,
    month_num;
