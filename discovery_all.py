
# discovery_all.py
# Discover ALL in-scope Magenta Pulse pages (plans, devices, promotions)
# Usage:
#   pip install httpx lxml pandas openpyxl defusedxml
#   python discovery_all.py --base https://magentapulse.t-mobile.com --workbook TFB_URL_Inventory.xlsx --out TFB_URL_Inventory_FULL.xlsx

import argparse, re, time, sys, urllib.parse as up
from collections import deque, defaultdict
from datetime import datetime
import httpx
from lxml import html, etree
from defusedxml.ElementTree import fromstring as safe_fromstring
import pandas as pd

DEF_USER_AGENT = "Mozilla/5.0 (compatible; TFB-Discovery/1.0; +https://example.org)"

def read_patterns(xl_path):
    inc = pd.read_excel(xl_path, sheet_name="Include_Patterns")
    exc = pd.read_excel(xl_path, sheet_name="Exclude_Patterns")
    seeds = pd.read_excel(xl_path, sheet_name="Seeds")["url"].dropna().tolist()
    allow = [(re.compile(p, re.I), hint) for p, hint in zip(inc["allowed_path_regex"], inc["entity_hint"])]
    block = [re.compile(p, re.I) for p in exc["disallowed_path_regex"]]
    return seeds, allow, block

def robots_sitemaps(base, cli):
    # Try robots.txt
    rob = up.urljoin(base, "/robots.txt")
    sitemaps = []
    try:
        r = cli.get(rob)
        if r.status_code == 200:
            for line in r.text.splitlines():
                line = line.strip()
                if line.lower().startswith("sitemap:"):
                    sitemaps.append(line.split(":",1)[1].strip())
    except Exception:
        pass
    return sitemaps

def parse_sitemap(cli, url):
    urls = []
    try:
        r = cli.get(url)
        if r.status_code != 200:
            return urls
        xml = safe_fromstring(r.content)
        tag = etree.QName(xml.tag).localname.lower()
        if tag == "sitemapindex":
            for sm in xml.findall(".//{*}sitemap/{*}loc"):
                child = sm.text.strip()
                urls.extend(parse_sitemap(cli, child))
        elif tag == "urlset":
            for u in xml.findall(".//{*}url/{*}loc"):
                urls.append(u.text.strip())
    except Exception:
        return urls
    return urls

def same_domain(base, url):
    return up.urlsplit(url).netloc.endswith(up.urlsplit(base).netloc)

def canonical_url(doc, url):
    try:
        c = doc.xpath("//link[@rel='canonical']/@href")
        if c:
            return up.urljoin(url, c[0])
    except Exception:
        pass
    return url

def in_scope(url, allow, block):
    path = up.urlsplit(url).path
    if any(b.search(path) for b in block):
        return False, None
    for pat, hint in allow:
        if pat.search(path):
            return True, hint
    return False, None

def discover_all(base, seeds, allow, block, max_depth=2, throttle=0.75):
    seen = set()
    hits = {}  # url -> entity
    # HTTP client
    with httpx.Client(follow_redirects=True, timeout=15, headers={"User-Agent": DEF_USER_AGENT}) as cli:
        # Sitemaps first
        smaps = robots_sitemaps(base, cli)
        for sm in smaps:
            for u in parse_sitemap(cli, sm):
                if same_domain(base, u):
                    ok, ent = in_scope(u, allow, block)
                    if ok:
                        hits[u] = ent

        # BFS crawl from seeds
        q = deque()
        for s in seeds:
            if same_domain(base, s):
                q.append((s, 0))

        while q:
            url, d = q.popleft()
            if url in seen or d > max_depth:
                continue
            seen.add(url)
            try:
                r = cli.get(url)
                if r.status_code != 200:
                    continue
                doc = html.fromstring(r.text)
                can = canonical_url(doc, url)
                if can not in seen:
                    seen.add(can)
                ok, ent = in_scope(can, allow, block)
                if ok:
                    hits[can] = ent
                # enqueue children
                for href in doc.xpath("//a[@href]/@href"):
                    nxt = up.urljoin(can, href.strip())
                    if "#" in nxt:
                        nxt = nxt.split("#",1)[0]
                    if not same_domain(base, nxt):
                        continue
                    if nxt not in seen:
                        q.append((nxt, d+1))
                time.sleep(throttle)
            except Exception:
                continue
    return hits

def write_results(out_xl, hits):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
    rows = []
    for u, e in sorted(hits.items()):
        rows.append({
            "url": u,
            "entity": e,
            "section": "",
            "priority": "P1" if e in ("plan","device","promo") else "P2",
            "discovery": "sitemap+crawl",
            "status": "todo",
            "requires_login": "",
            "format": "",
            "language": "en",
            "last_seen": now,
            "content_hash": "",
            "owner": "",
            "notes": ""
        })
    df = pd.DataFrame(rows)
    summary = (df.groupby("entity")["url"].count().rename("count").reset_index()
                 .sort_values("count", ascending=False))
    with pd.ExcelWriter(out_xl, engine="xlsxwriter") as w:
        df.to_excel(w, index=False, sheet_name="URL_Inventory")
        summary.to_excel(w, index=False, sheet_name="Summary")
    print("Wrote", len(df), "URLs to", out_xl)
    print("By entity:")
    for _, r in summary.iterrows():
        print("  ", r["entity"], "=", r["count"])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="Base domain (e.g., https://magentapulse.t-mobile.com)")
    ap.add_argument("--workbook", default="TFB_URL_Inventory.xlsx", help="Workbook with Seeds/Patterns")
    ap.add_argument("--out", default="TFB_URL_Inventory_FULL.xlsx", help="Output workbook")
    ap.add_argument("--depth", type=int, default=2, help="Crawl depth")
    ap.add_argument("--throttle", type=float, default=0.75, help="Delay between requests (s)")
    args = ap.parse_args()

    seeds, allow, block = read_patterns(args.workbook)
    hits = discover_all(args.base, seeds, allow, block, max_depth=args.depth, throttle=args.throttle)
    write_results(args.out, hits)

if __name__ == "__main__":
    main()
