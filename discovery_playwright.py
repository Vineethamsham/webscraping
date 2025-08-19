
# discovery_playwright.py
# Discovery with Playwright (works when site requires login/SSO). Opens a browser, you sign in once,
# then it crawls seeds to a shallow depth and collects all in-scope URLs.
#
# Usage (PowerShell or bash):
#   python discovery_playwright.py --base https://magentapulse.t-mobile.com \
#       --workbook TFB_URL_Inventory_UPDATED.xlsx --out TFB_URL_Inventory_FULL.xlsx --depth 2 --throttle 0.5
#
import argparse, re, time, urllib.parse as up
from collections import deque
from datetime import datetime, timezone
import pandas as pd
from playwright.sync_api import sync_playwright
import os

chrome_profile = os.path.join(os.environ["LOCALAPPDATA"], "Google", "Chrome", "User Data")

DEF_USER_AGENT = "Mozilla/5.0 (compatible; TFB-Discovery/1.0; +https://example.org)"

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

def discover_with_browser(base, seeds, allow, block, depth=2, throttle=0.5, user_data_dir="user_data"):
    hits = {}
    seen = set()
    q = deque()

    with sync_playwright() as p:
        # Persistent context stores your login/cookies between runs
       # browser = p.chromium.launch_persistent_context(user_data_dir=user_data_dir, headless=False)
        browser = p.chromium.launch_persistent_context(user_data_dir=chrome_profile, headless=False,  channel="chrome",          # or "chrome" if you prefer
            ignore_https_errors=True,     # avoid corp TLS errors during discovery
            user_agent = DEF_USER_AGENT
            )

        page = browser.new_page()
        # visit a base page first to let you log in if needed
        page.goto(base, wait_until="domcontentloaded", timeout=60000)

        # BFS
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
                # try to wait a bit for dynamic links
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except:
                    pass
                # get canonical href if present
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
                    # strip fragments
                    if "#" in href:
                        href = href.split("#", 1)[0]
                    if same_domain(base, href) and href not in seen:
                        q.append((href, d+1))
                time.sleep(throttle)
            except Exception as e:
                # skip pages that error out
                continue

        browser.close()
    return hits

def write_results(out_xl, hits):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    columns = ["url","entity","section","priority","discovery","status","requires_login",
               "format","language","last_seen","content_hash","owner","notes"]
    rows = [{
        "url": u, "entity": e, "section": "", "priority": "P1" if e in ("plan","device","promo") else "P2",
        "discovery": "playwright", "status": "todo", "requires_login": "",
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
        print("No in-scope pages found. Ensure you're logged in and increase depth.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--workbook", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--throttle", type=float, default=0.5)
    args = ap.parse_args()

    seeds, allow, block = read_patterns(args.workbook)
    hits = discover_with_browser(args.base, seeds, allow, block, depth=args.depth, throttle=args.throttle)
    write_results(args.out, hits)

if __name__ == "__main__":
    main()




# Replace

def discover_with_browser(base, seeds, allow, block, depth=2, throttle=0.5, user_data_dir=PRIVATE_PROFILE_DIR):
    hits = {}
    seen = set()
    q = deque()

    with sync_playwright() as p:
        # Launch Chrome with a fresh, local profile (NOT the enterprise profile)
        try:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=False,
                channel="chrome",              # use Chrome (works for you)
                ignore_https_errors=True,
                user_agent=DEF_USER_AGENT
            )
        except Exception:
            # Fallback: explicit path (adjust if your Chrome is elsewhere)
            browser = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=False,
                executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                ignore_https_errors=True,
                user_agent=DEF_USER_AGENT
            )

        page = browser.new_page()

        # Open base page to allow SSO; you log in once with this fresh profile.
        page.goto(base, wait_until="domcontentloaded", timeout=90000)
        print("\n*** Log in in the opened Chrome window (fresh profile) ***")
        input("Press ENTER here after you are fully signed in and can browse … ")

        # BFS crawl
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

                # canonical
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

                # enqueue children
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

        browser.close()
    return hits
