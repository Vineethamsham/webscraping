
# TFB Discovery – README

Goal: produce a complete, deduplicated list of **all** in-scope Magenta Pulse URLs for TFB **Plans**, **Devices**, and **Promotions**.

## Files
- `TFB_URL_Inventory.xlsx` – seeds & regex patterns (already created for you).
- `discovery_all.py` – discovery script (sitemap + shallow crawl).

## Install
```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install httpx lxml pandas openpyxl defusedxml
```

## Run (safe, shallow, filtered)
```bash
python discovery_all.py --base https://magentapulse.t-mobile.com \
                        --workbook TFB_URL_Inventory.xlsx \
                        --out TFB_URL_Inventory_FULL.xlsx \
                        --depth 2 --throttle 0.75
```

- The script reads **Seeds** and **Include/Exclude patterns** from the workbook.
- It parses sitemaps from `robots.txt` and also crawls from the seeds up to depth 2.
- It filters to in-scope paths (plans, devices, promotions) and excludes Not-in-Scope (account, billing, order, etc.).
- Output: `TFB_URL_Inventory_FULL.xlsx` with **URL_Inventory** (all relevant URLs) and **Summary** (counts by entity).

## After it runs
1. Open `TFB_URL_Inventory_FULL.xlsx`.
2. Spot-check 3–5 URLs per entity.
3. Paste the **URL_Inventory** into your master spreadsheet or share the file directly.

## Notes
- Keep depth small (2). If you are missing detail pages, increase to `--depth 3` temporarily.
- The script honors canonical URLs and dedupes automatically.
- Discovery skips JS rendering (faster); actual scraping/extraction can use Playwright later.
- Please be polite: keep `--throttle` ≥ 0.5s and respect site Terms & robots.
