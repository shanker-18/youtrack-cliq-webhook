def _matches_shipment_keyword(c_key: str, c_db: str, c_code: str) -> bool:
    """Check if any known shipment keyword matches between key and DB name/code."""
    keywords = ["LIQUIDAT", "SUPPLY", "RETAIL", "DISTRIB", "INNOVAT", "TRADE", "CLUB"]
    return any(kw in c_key and (kw in c_db or kw in c_code) for kw in keywords)


def _matches_shipment_fallback(c_key: str, c_disp: str, c_db: str, c_code: str) -> bool:
    """Fallback fuzzy matching between cleaned tokens."""
    if c_key in c_db or c_disp in c_db:
        return True
    if c_db and (c_db in c_key or c_db in c_disp):
        return True
    if c_code and (c_key in c_code or c_code in c_key):
        return True
    return False


def _matches_shipment_driver(
    db_name: str,
    grp: str,
    disp_name: str,
    match_key: str,
    db_section: str = "",
    db_code: str = "",
) -> bool:
    """Matches a PostgreSQL building block (by section, code, and name) to a defined dashboard driver."""
    c_db = _clean_token(db_name)
    c_disp = _clean_token(disp_name)
    c_key = _clean_token(match_key)
    c_sec = _clean_token(db_section)
    c_code = _clean_token(db_code)
    c_grp = _clean_token(grp)
    if not c_db and not c_code:
        return False
    if c_sec and c_sec != c_grp:
        return False
    if c_disp == "OTHER":
        return _matches_other_shipment_driver(c_db, c_code, c_sec, c_key, grp)
    if _matches_shipment_keyword(c_key, c_db, c_code):
        return True
    return _matches_shipment_fallback(c_key, c_disp, c_db, c_code)
