            parsed = _parse_batch_cell(c)
            if parsed is None:
                errors += 1
                continue
            rid, period_month, old_val, new_val = parsed
            if old_val == new_val:
                continue
