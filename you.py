.audit-entry-card {
    border-left: 3px solid var(--g);
    margin-bottom: 8px;
}

/* ── Spreadsheet-Style Cell Selection & Focus Indicator (AC1 & AC7) ── */
td.cell-selected,
td.cell-num.cell-selected,
td.cell-subbrand.cell-selected,
td.cell-desc.cell-selected,
td.cell-num:focus {
    outline: 2px solid var(--trust-green, #019881) !important;
    outline-offset: -2px !important;
    background-color: rgba(1, 152, 129, 0.09) !important;
    position: relative !important;
    z-index: 5 !important;
    box-shadow: inset 0 0 0 1px var(--trust-green, #019881) !important;
}
