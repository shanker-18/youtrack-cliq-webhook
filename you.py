def _resolve_valid_user_id(cursor, user_id: Optional[int]) -> Optional[int]:
    """Ensure user_id exists in users table before writing foreign-keyed audit/value rows."""
    if user_id is not None:
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s;", (user_id,))
        if cursor.fetchone():
            return user_id
    cursor.execute("SELECT user_id FROM users ORDER BY user_id LIMIT 1;")
    fallback = cursor.fetchone()
    return fallback["user_id"] if fallback else None
