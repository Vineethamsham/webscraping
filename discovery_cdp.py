
# discovery_cdp.py
# Connect to an already-running Chrome (your managed profile) via CDP and crawl
# all in-scope pages (plans/devices/promotions) using the patterns in the workbook.
#
# HOW TO USE (PowerShell):
# 1) Close all Chrome windows.
# 2) Start Chrome with remote debugging enabled:
#      & "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
#    (Adjust the path if Chrome lives elsewhere. Keep this window open.)
# 3) In that Chrome window, sign in to Magenta Pulse and confirm you can browse.
# 4) In this folder (with your workbook), run:
#      python discovery_cdp.py --base "https://magentapulse.t-mobile.com" --workbook "TFB_URL_Inventory_UPDATED.xlsx" --out "TFB_URL_Inventory_FULL.xlsx" --depth 3 --throttle 0.7
#
import argparse, re, time, urllib.parse as up
from collections import deque
from datetime import datetime, timezone
import pandas as pd
from playwright.sync_api import sync_playwright

DEF_USER_AGENT = "Mozilla/5.0 (TFB-Discovery/1.0)"
CDP_ENDPOINT = "http://localhost:9222"

def read_patterns(xl_path):
    inc = pd.read_excel(xl_path, sheet_name="Include_Patterns")
    exc = pd.read_excel(xl_path, sheet_name="Exclude_Patterns")
    seeds = pd.read_excel(xl_path, sheet_name="Seeds")["url"].dropna().tolist()
    allow = [(re.compile(p, re.I), hint) for p, hint in zip(inc["allowed_path_regex"], inc["entity_hint"])]
    block = [re.compile(p, re.I) for p in exc["disallowed_path_regex"]]
    return seeds, allow, block

def same_domain(base, url):
    return up.urlsplit(url).netloc.endswith(up.urlsplit(base).netloc)

def canonical_url(page_url, canonical_href):
    if canonical_href:
        return up.urljoin(page_url, canonical_href)
    return page_url

def in_scope(url, allow, block):
    path = up.urlsplit(url).path
    if any(b.search(path) for b in block):
        return False, None
    for pat, hint in allow:
        if pat.search(path):
            return True, hint
    return False, None

def discover_over_cdp(base, seeds, allow, block, depth=3, throttle=0.7):
    hits, seen = {}, set()
    q = deque()
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_ENDPOINT)
        context = browser.contexts[0] if browser.contexts else browser.new_context(
            ignore_https_errors=True, user_agent=DEF_USER_AGENT
        )
        page = context.new_page()
        page.goto(base, wait_until="domcontentloaded", timeout=90000)
        try:
            page.wait_for_load_state("networkidle", timeout=6000)
        except:
            pass
        for s in seeds:
            if same_domain(base, s):
                q.append((s, 0))
        while q:
            url, d = q.popleft()
            if url in seen or d > depth:
                continue
            seen.add(url)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=90000)
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except:
                    pass
                can_href = None
                try:
                    el = page.query_selector('link[rel="canonical"]')
                    if el:
                        can_href = el.get_attribute("href")
                except:
                    pass
                can = canonical_url(page.url, can_href)
                ok, ent = in_scope(can, allow, block)
                if ok:
                    hits[can] = ent
                hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
                for href in hrefs:
                    if not href:
                        continue
                    if "#" in href:
                        href = href.split("#", 1)[0]
                    if same_domain(base, href) and href not in seen:
                        q.append((href, d + 1))
                time.sleep(throttle)
            except Exception:
                continue
        # detach (do not close your real Chrome)
        try:
            page.close()
        except Exception:
            pass
        try:
            context.dispose()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass
    return hits

def write_results(out_xl, hits):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    columns = ["url","entity","section","priority","discovery","status","requires_login",
               "format","language","last_seen","content_hash","owner","notes"]
    rows = [{
        "url": u, "entity": e, "section": "", "priority": "P1" if e in ("plan","device","promo") else "P2",
        "discovery": "cdp", "status": "todo", "requires_login": "",
        "format": "", "language": "en", "last_seen": now, "content_hash": "",
        "owner": "", "notes": ""
    } for u, e in sorted(hits.items())]
    df = pd.DataFrame(rows, columns=columns)
    if not df.empty:
        summary = (df.groupby("entity")["url"].count()
                     .rename("count").reset_index()
                     .sort_values("count", ascending=False))
    else:
        summary = pd.DataFrame({"entity": [], "count": []})
    with pd.ExcelWriter(out_xl, engine="xlsxwriter") as w:
        df.to_excel(w, index=False, sheet_name="URL_Inventory")
        summary.to_excel(w, index=False, sheet_name="Summary")
    print(f"Wrote {len(df)} URLs to {out_xl}")
    if df.empty:
        print("No in-scope pages found. Make sure Chrome is running with --remote-debugging-port=9222 and you're logged in.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--workbook", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--depth", type=int, default=3)
    ap.add_argument("--throttle", type=float, default=0.7)
    args = ap.parse_args()
    seeds, allow, block = read_patterns(args.workbook)
    hits = discover_over_cdp(args.base, seeds, allow, block, depth=args.depth, throttle=args.throttle)
    write_results(args.out, hits)

if __name__ == "__main__":
    main()
