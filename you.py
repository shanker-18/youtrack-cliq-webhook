        elif row_id and period_month:
            cursor.execute(
                "SELECT value_id FROM consumption_planning_values WHERE row_id = %s AND period_month = %s LIMIT 1;",
                (row_id, period_month),
            )
            val_row = cursor.fetchone()
            resolved_value_id = val_row["value_id"] if val_row else None
            if resolved_value_id:
                query = """
                    SELECT
                        a.audit_id, a.row_id, a.value_id, a.event_type,
                        a.old_value, a.new_value, a.comment, a.performed_at, a.is_copied_record,
                        u.user_id, u.display_name AS user_name, u.email AS user_email,
                        d.dept_id, d.code AS dept_code, d.name AS dept_name
                    FROM consumption_audit_history a
                    LEFT JOIN users u ON a.performed_by = u.user_id
                    LEFT JOIN departments d ON a.dept_id = d.dept_id
                    WHERE a.value_id = %s OR (a.row_id = %s AND a.value_id IS NULL)
                    ORDER BY a.performed_at DESC;
                """
                cursor.execute(query, (resolved_value_id, row_id))
            else:
                query = """
                    SELECT
                        a.audit_id, a.row_id, a.value_id, a.event_type,
                        a.old_value, a.new_value, a.comment, a.performed_at, a.is_copied_record,
                        u.user_id, u.display_name AS user_name, u.email AS user_email,
                        d.dept_id, d.code AS dept_code, d.name AS dept_name
                    FROM consumption_audit_history a
                    LEFT JOIN users u ON a.performed_by = u.user_id
                    LEFT JOIN departments d ON a.dept_id = d.dept_id
                    WHERE a.row_id = %s AND a.value_id IS NULL
                    ORDER BY a.performed_at DESC;
                """
                cursor.execute(query, (row_id,))
