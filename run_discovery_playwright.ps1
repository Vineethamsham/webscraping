
# run_discovery_playwright.ps1
$ErrorActionPreference = "Stop"
if (Test-Path ".\.venv\Scripts\Activate.ps1") { . .\.venv\Scripts\Activate.ps1 }
pip install -r requirements.txt
pip install -r requirements_playwright.txt
python -m playwright install chromium
python .\discovery_playwright.py --base "https://magentapulse.t-mobile.com" `
    --workbook ".\TFB_URL_Inventory_UPDATED.xlsx" `
    --out ".\TFB_URL_Inventory_FULL.xlsx" `
    --depth 2 `
    --throttle 0.5
