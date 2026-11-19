def _load_audit_row_and_events(domain: str, row_id: int, period_date: date) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], str]:
    """Fetch row details, current value, and audit trail in minimal DB round-trips."""
    from database.connection import get_db_cursor

    is_consumption = domain.upper() == "CONSUMPTION"
    row_table = "consumption_planning_rows" if is_consumption else "shipment_planning_rows"
    val_table = "consumption_planning_values" if is_consumption else "shipment_planning_values"
    audit_table = "consumption_audit_history" if is_consumption else "shipment_audit_history"

    row_details = None
    events = []
    cur_val = "0.00"

    try:
        with get_db_cursor(commit=False) as cursor:
            # 1. Row details + current value in one query
            cursor.execute(
                f"""
                SELECT r.row_id, r.item, r.description, r.is_deleted, r.model_id,
                       m.model_name,
                       v.value_id, v.value_in_thousands
                FROM {row_table} r
                LEFT JOIN master_models m ON r.model_id = m.model_id
                LEFT JOIN {val_table} v ON v.row_id = r.row_id AND v.period_month = %s
                WHERE r.row_id = %s;
                """,
                (period_date, row_id),
            )
            row_details = cursor.fetchone()

            if row_details and row_details.get("value_in_thousands") is not None:
                cur_val = f"{float(row_details['value_in_thousands']):.2f}"

            resolved_value_id = row_details["value_id"] if row_details and row_details.get("value_id") else None

            # 2. Audit trail using resolved value_id (no JOIN needed)
            if resolved_value_id:
                cursor.execute(
                    f"""
                    SELECT a.audit_id, a.row_id, a.value_id, a.event_type,
                           a.old_value, a.new_value, a.comment, a.performed_at, a.is_copied_record,
                           u.user_id, u.display_name AS user_name, u.email AS user_email,
                           d.dept_id, d.code AS dept_code, d.name AS dept_name
                    FROM {audit_table} a
                    LEFT JOIN users u ON a.performed_by = u.user_id
                    LEFT JOIN departments d ON a.dept_id = d.dept_id
                    WHERE a.value_id = %s OR (a.row_id = %s AND a.value_id IS NULL)
                    ORDER BY a.performed_at DESC;
                    """,
                    (resolved_value_id, row_id),
                )
            else:
                cursor.execute(
                    f"""
                    SELECT a.audit_id, a.row_id, a.value_id, a.event_type,
                           a.old_value, a.new_value, a.comment, a.performed_at, a.is_copied_record,
                           u.user_id, u.display_name AS user_name, u.email AS user_email,
                           d.dept_id, d.code AS dept_code, d.name AS dept_name
                    FROM {audit_table} a
                    LEFT JOIN users u ON a.performed_by = u.user_id
                    LEFT JOIN departments d ON a.dept_id = d.dept_id
                    WHERE a.row_id = %s AND a.value_id IS NULL
                    ORDER BY a.performed_at DESC;
                    """,
                    (row_id,),
                )
            raw_events = cursor.fetchall()
    except (psycopg2.Error, KeyError, ValueError) as e:
        logger.exception("Failed to load audit data", extra={"context": {"error": str(e)}})
        return row_details, events, cur_val

    # Format events through the service layer formatter
    from services.planning_service import resolve_source_lineage, _build_audit_event_item
    needs_lineage = any(
        (ev.get("is_copied_record") is True or ev.get("event_type") == "CYCLE_INITIALIZED")
        for ev in raw_events
    )
    cached_lineage = resolve_source_lineage(domain, row_id) if needs_lineage else "Current Cycle"
    events = [_build_audit_event_item(ev, cached_lineage) for ev in raw_events]

    return row_details, events, cur_val
