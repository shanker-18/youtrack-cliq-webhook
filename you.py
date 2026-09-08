import os

# Kenvue NA IBP Validation Dashboard Stylesheet (Python Module)

COLOR_TRUST_GREEN = "#005A38"
COLOR_TRUST_GREEN_DARK = "#004229"
COLOR_CARE_YELLOW = "#FFB800"
COLOR_EMPATHY_PURPLE = "#6A2676"
COLOR_COURAGE_CORAL = "#E05A47"
COLOR_BG_LIGHT = "#F8F9FA"
COLOR_CARD_BG = "#FFFFFF"
COLOR_TEXT_MAIN = "#212529"
COLOR_TEXT_MUTED = "#6C757D"
COLOR_BORDER = "#E9ECEF"

# Raw CSS string for Dash application
RAW_CSS = """
:root {
  --kenvue-trust-green: #005A38;
  --kenvue-trust-green-dark: #004229;
  --kenvue-care-yellow: #FFB800;
  --kenvue-empathy-purple: #6A2676;
  --kenvue-courage-coral: #E05A47;
  --kenvue-bg-light: #F8F9FA;
  --kenvue-card-bg: #FFFFFF;
  --kenvue-text-main: #212529;
  --kenvue-text-muted: #6C757D;
  --kenvue-border: #E9ECEF;
  --kenvue-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

body {
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background-color: var(--kenvue-bg-light);
  color: var(--kenvue-text-main);
  -webkit-font-smoothing: antialiased;
}

.kenvue-header {
  background-color: var(--kenvue-trust-green);
  color: #ffffff;
  padding: 16px 32px;
  box-shadow: 0 2px 10px rgba(0, 90, 56, 0.2);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.kenvue-brand-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.kenvue-logo-badge {
  background-color: var(--kenvue-care-yellow);
  color: #000000;
  font-weight: 800;
  font-size: 14px;
  padding: 4px 10px;
  border-radius: 6px;
  letter-spacing: 0.5px;
}

.kenvue-header h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.3px;
}

.kenvue-header-timestamp {
  font-size: 13px;
  opacity: 0.9;
  background: rgba(255, 255, 255, 0.15);
  padding: 6px 14px;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.kenvue-container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
}

.kenvue-tabs {
  margin-bottom: 24px;
}

.nav-tabs .nav-link {
  font-size: 15px;
  font-weight: 600;
  color: var(--kenvue-text-muted);
  border: none !important;
  padding: 12px 24px;
  border-radius: 8px 8px 0 0 !important;
  transition: all 0.2s ease;
}

.nav-tabs .nav-link:hover {
  color: var(--kenvue-trust-green);
}

.nav-tabs .nav-link.active {
  color: var(--kenvue-trust-green) !important;
  background-color: transparent !important;
  border-bottom: 3px solid var(--kenvue-trust-green) !important;
}

.sync-section {
  background: var(--kenvue-card-bg);
  padding: 20px 24px;
  border-radius: 12px;
  box-shadow: var(--kenvue-shadow);
  margin-bottom: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px solid var(--kenvue-border);
}

.btn-sync-snowflake {
  background-color: var(--kenvue-trust-green) !important;
  color: #ffffff !important;
  font-weight: 700 !important;
  font-size: 14px !important;
  padding: 10px 24px !important;
  border-radius: 8px !important;
  border: none !important;
  box-shadow: 0 4px 8px rgba(0, 90, 56, 0.25) !important;
  transition: all 0.2s ease !important;
  cursor: pointer;
}

.btn-sync-snowflake:hover {
  background-color: var(--kenvue-trust-green-dark) !important;
  transform: translateY(-1px);
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.kpi-card {
  background: var(--kenvue-card-bg);
  padding: 20px;
  border-radius: 12px;
  box-shadow: var(--kenvue-shadow);
  border-left: 5px solid var(--kenvue-trust-green);
  border-top: 1px solid var(--kenvue-border);
  border-right: 1px solid var(--kenvue-border);
  border-bottom: 1px solid var(--kenvue-border);
  transition: transform 0.2s ease;
}

.kpi-card:hover {
  transform: translateY(-2px);
}

.kpi-card.yellow {
  border-left-color: var(--kenvue-care-yellow);
}

.kpi-card.purple {
  border-left-color: var(--kenvue-empathy-purple);
}

.kpi-card.coral {
  border-left-color: var(--kenvue-courage-coral);
}

.kpi-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--kenvue-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.kpi-value {
  font-size: 26px;
  font-weight: 800;
  color: var(--kenvue-text-main);
}

.chart-card {
  background: var(--kenvue-card-bg);
  padding: 24px;
  border-radius: 12px;
  box-shadow: var(--kenvue-shadow);
  border: 1px solid var(--kenvue-border);
  margin-bottom: 24px;
}

.chart-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--kenvue-trust-green);
  margin-bottom: 16px;
}

.empty-state-card {
  background: var(--kenvue-card-bg);
  padding: 48px 24px;
  border-radius: 12px;
  box-shadow: var(--kenvue-shadow);
  border: 2px dashed var(--kenvue-border);
  text-align: center;
  margin-bottom: 24px;
}

.empty-state-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.6;
}

.empty-state-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--kenvue-trust-green);
  margin-bottom: 8px;
}

.empty-state-text {
  font-size: 15px;
  color: var(--kenvue-text-muted);
  max-width: 500px;
  margin: 0 auto;
}

.datatable-card {
  background: var(--kenvue-card-bg);
  padding: 24px;
  border-radius: 12px;
  box-shadow: var(--kenvue-shadow);
  border: 1px solid var(--kenvue-border);
  margin-bottom: 24px;
}

.modal-header {
  background-color: var(--kenvue-trust-green);
  color: #ffffff;
  border-radius: 8px 8px 0 0;
}

.modal-header .btn-close {
  filter: invert(1);
}

.btn-kenvue-primary {
  background-color: var(--kenvue-trust-green) !important;
  color: #ffffff !important;
  font-weight: 600 !important;
  border-radius: 6px !important;
}

.btn-kenvue-primary:hover {
  background-color: var(--kenvue-trust-green-dark) !important;
}

.btn-kenvue-coral {
  background-color: var(--kenvue-courage-coral) !important;
  color: #ffffff !important;
  font-weight: 600 !important;
  border-radius: 6px !important;
}
"""

def generate_css_file():
    assets_dir = os.path.join(os.path.dirname(__file__), "assets")
    os.makedirs(assets_dir, exist_ok=True)
    css_path = os.path.join(assets_dir, "style.css")
    with open(css_path, "w", encoding="utf-8") as f:
        f.write(RAW_CSS.strip())

generate_css_file()
