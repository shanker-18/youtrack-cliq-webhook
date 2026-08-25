CYCLES = ["Current Planning Cycle (Jun 2026)", "Jul 2026 (Draft Cycle)", "May 2026 (Locked Cycle)"]
MARKETS = ["Select Market", "US (United States)", "Canada", "Europe", "Global Total"]
BUS = ["Select Business Unit", "Consumer Healthcare", "Self-Care", "Skin Health & Beauty"]

STAGES = [
    ("01", "Baseline", "Statistical baseline demand forecast"),
    ("02", "Bottom-Up", "Sales & commercial driver-based inputs"),
    ("03", "Top-Down", "Strategic executive business plan target"),
    ("04", "Reconciliation", "Resolve differences between Top Down and Bottom Up"),
    ("05", "Demand Review", "Cross-functional consensus review"),
    ("06", "Consensus", "Formal sign-off by functional leads"),
    ("07", "One Volume Plan", "Single source of truth consensus plan"),
]

NAV_ITEMS = [
    ("Home", "bi-house-door-fill"),
    ("Consumption LE", "bi-graph-up"),
    ("Inventory LE", "bi-box-seam"),
    ("Shipment LE", "bi-truck"),
    ("POS & Inventory Data", "bi-database"),
    ("Building Blocks", "bi-building-blocks"),
    ("Demand Review", "bi-people-fill"),
    ("Dashboard", "bi-speedometer2"),
]

MODULES = [
    ("Consumption LE", "Planning Workspace", "bi-graph-up", "Latest Estimate consumption planning & scan data."),
    ("Inventory LE", "Planning Workspace", "bi-box-seam", "Inventory planning, projected positions & safety stock."),
    ("Shipment LE", "Planning Workspace", "bi-truck", "Primary shipment schedules & ex-factory projections."),
    ("POS & Inventory Data", "Planning Workspace", "bi-database", "POS retailer source data & channel inventory."),
    ("Building Blocks", "Planning & Review", "bi-building-blocks", "Business & demand drivers shaping volume."),
    ("Demand Review", "Planning & Review", "bi-people-fill", "Cross-functional demand review & consensus."),
    ("Dashboard", "Planning & Review", "bi-speedometer2", "Planning analytics & consensus reporting."),
]

DRIVERS = [
    ("Base Trends", "Demand Trend", "Organic baseline consumption momentum."),
    ("Seasonality", "Pattern", "Seasonal index shifts & historical velocity."),
    ("NPI", "Commercial", "New Product Introduction incremental volume."),
    ("NPI Cannibalization", "Commercial", "Estimated volume shift from legacy SKUs."),
    ("Merchandising", "Trade Promo", "Circular promo slots & display lifts."),
    ("Pricing", "Finance", "Price adjustments & elasticity impacts."),
    ("Store Openings", "Distribution", "Incremental door distribution points."),
    ("Store Closings", "Distribution", "Footprint reduction & door adjustments."),
    ("Innovation", "Product", "Packaging redesigns & line extensions."),
    ("Customer Target Adjust", "Account", "Retailer account volume adjustments."),
    ("Supply / Fill Rate", "Supply Chain", "Plant capacity & fill rate feasibility."),
    ("Shifting Placement / OSA", "Retail Ops", "On-shelf availability & placement changes."),
]

SUPPLY_CONCEPTS = [
    ("Inventory Build", "Pre-season accumulation for peak demand."),
    ("Store Openings", "Initial pipeline fill for new retail doors."),
    ("Store Closings", "Inventory buy-back & liquidation tracking."),
    ("Supply / Fill Rate", "Production alignment against demand."),
    ("Supply Vulnerability", "Raw material & lead-time risk assessment."),
    ("Inventory Drawdown", "Planned stock reduction during off-peak."),
]
