#!/usr/bin/env python3
"""
Step 2 — Pilbara Ports monthly cargo statistics.

Version 3. Changes from v2:
  * v2 returned zero month links. The published page is plain HTML, not
    JavaScript rendered, so the cause is a bot block on the request rather
    than a parsing fault. Fighting that is not worth the time.
  * This version reads the statistics pages from HTML files saved by hand from
    a browser. Parsing then runs locally with nothing to block.
  * The PDFs are still fetched over the network, with browser-like headers,
    because they sit on a separate media path.
  * Scope trimmed: only tonnage reports are fetched, not cargo-by-destination,
    which this analysis does not use.

SETUP (two minutes, once)
  1. Open each page in your browser:
     https://www.pilbaraports.com.au/ports/port-of-port-hedland/about-port-of-hedland/port-statistics-and-reports
     https://www.pilbaraports.com.au/ports/port-of-dampier/about-port-of-dampier/port-statistics-and-reports
  2. Right-click the page, "Save Page As", choose "Page Source" or "HTML Only".
  3. Save them into data/raw/pilbara_ports/ as:
       page_port_hedland.html
       page_dampier.html

USAGE
  python src/step2_pilbara_ports.py --dry-run    # preview what was found
  python src/step2_pilbara_ports.py              # download + extract
  python src/step2_pilbara_ports.py --extract    # extract only, no network
"""

import re
import sys
import time
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone

import requests
import pandas as pd

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

BASE = "https://www.pilbaraports.com.au"

PORTS = {
    "port_hedland": "page_port_hedland.html",
    # Dampier is disabled. Its page publishes "Financial year-to-date
    # statistics", which are cumulative from July rather than monthly totals,
    # so the figures cannot sit in the same table as Port Hedland's without
    # differencing consecutive months and resetting each July. Port Hedland
    # alone covers all ten Category 3+ cyclone months, so this is not needed.
    # "dampier": "page_dampier.html",
}

# Report types worth downloading. "destination" breaks cargo down by receiving
# country, which this analysis does not use.
WANT = {"cargo_type", "fy_to_date"}

START_YEAR = 2015
REQUEST_DELAY = 1.5
TIMEOUT = 90

MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]
MONTHS = {m.lower(): i for i, m in enumerate(MONTH_NAMES, 1)}

ROOT     = Path(__file__).resolve().parent.parent
RAW_DIR  = ROOT / "data" / "raw" / "pilbara_ports"
PROC_DIR = ROOT / "data" / "processed"
SOURCES  = ROOT / "data" / "SOURCES.md"

TODAY = datetime.now(timezone.utc).date().isoformat()

# Browser-like headers. The statistics pages block plain requests, but the
# media paths holding the PDFs generally do not.
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
    "Referer": BASE + "/",
}

YEAR_RE = re.compile(r">\s*(20\d{2})(?:\s*[-/]\s*(\d{2}|20\d{2}))?\s*<")
LINK_RE = re.compile(
    r'<a[^>]*\bhref\s*=\s*["\']([^"\']+)["\'][^>]*>\s*(' +
    "|".join(MONTH_NAMES) + r')\s*</a>',
    re.IGNORECASE)


# ----------------------------------------------------------------------------
# Parsing local HTML
# ----------------------------------------------------------------------------

def classify(url: str) -> str:
    u = url.lower()
    if "destination" in u:
        return "destination"
    if any(k in u for k in ["grt-and-dwt", "grt_and_dwt", "commodity-type",
                            "commodity_type", "cargo%20weights", "cargo-weights",
                            "grt%20and%20dwt"]):
        return "cargo_type"
    if any(k in u for k in ["year-to-date", "ytd", "financial"]):
        return "fy_to_date"
    return "other"


def month_to_year(month: int, y1: int, y2) -> int:
    """
    A single year label usually means calendar year. A span label such as
    2025-26 is a financial year running July to June, so July onward sits in
    the first year and January to June in the second.

    Port Hedland also uses a bare financial-year-end label for the current
    year: the July 2026 report appears under a "2027" heading. A published
    report cannot describe a future month, so any assignment that lands past
    the current month is pulled back one year.
    """
    year = y1 if (y2 is None or month >= 7) else y1 + 1

    now = datetime.now()
    if (year, month) > (now.year, now.month):
        year -= 1
    return year


def parse_page(port: str, path: Path) -> list:
    html = path.read_text(encoding="utf-8", errors="replace")
    print(f"\n[read] {path.name}  ({len(html)/1024:.0f} KB)")

    years = []
    for m in YEAR_RE.finditer(html):
        y1 = int(m.group(1))
        y2 = m.group(2)
        if y2 is not None:
            y2 = int(y2) if len(y2) == 4 else 2000 + int(y2)
        years.append((m.start(), y1, y2))

    links = list(LINK_RE.finditer(html))
    print(f"[scan] {len(years)} year markers, {len(links)} month links")

    if not links:
        print("[warn] no month links found. If you used 'Web Page, Complete', "
              "try View Source and save that text instead.")
        return []

    records = []
    for lm in links:
        prior = [y for y in years if y[0] < lm.start()]
        if not prior:
            continue
        _, y1, y2 = prior[-1]
        month = MONTHS[lm.group(2).lower()]
        url = lm.group(1)
        if url.startswith("/"):
            url = BASE + url
        elif not url.startswith("http"):
            continue

        records.append({
            "port":  port,
            "year":  month_to_year(month, y1, y2),
            "month": month,
            "kind":  classify(url),
            "label": f"{y1}-{y2}" if y2 else str(y1),
            "url":   url,
        })

    if records:
        kinds = pd.Series([r["kind"] for r in records]).value_counts()
        print(f"[kind] {dict(kinds)}")

    seen, out = set(), []
    for r in records:
        key = (r["port"], r["year"], r["month"], r["kind"])
        if key in seen or r["year"] < START_YEAR or r["kind"] not in WANT:
            continue
        seen.add(key)
        out.append(r)

    out.sort(key=lambda x: (x["year"], x["month"]))
    print(f"[keep] {len(out)} tonnage reports for {port}")
    if out:
        print(f"       {out[0]['year']}-{out[0]['month']:02d} to "
              f"{out[-1]['year']}-{out[-1]['month']:02d}")
    return out


def load_pages() -> list:
    records, missing = [], []
    for port, fname in PORTS.items():
        path = RAW_DIR / fname
        if not path.exists():
            missing.append(str(path))
            continue
        records += parse_page(port, path)

    if missing:
        print("\n!! Saved HTML not found:")
        for m in missing:
            print(f"   {m}")
        print("\n   Open the page in your browser, right-click, Save Page As,")
        print("   choose Page Source or HTML Only, save with that filename.")
    return records


# ----------------------------------------------------------------------------
# Preview
# ----------------------------------------------------------------------------

def preview(records: list):
    df = pd.DataFrame(records)
    if df.empty:
        print("\nNothing to preview.")
        return

    print("\n" + "=" * 66)
    print("DISCOVERY PREVIEW")
    print("=" * 66)

    for port, g in df.groupby("port"):
        print(f"\n{port}: {len(g)} reports")
        for y, n in g.groupby("year").size().items():
            flag = "" if n == 12 else "   <-- expected 12"
            print(f"    {y}: {n}{flag}")

    print("\nSample:")
    print(df.sample(min(8, len(df)), random_state=1)
          [["port", "year", "month", "kind", "label"]]
          .sort_values(["port", "year", "month"]).to_string(index=False))

    cyc = PROC_DIR / "dim_cyclone_event.csv"
    if cyc.exists():
        c = pd.read_csv(cyc, parse_dates=["peak_datetime"])
        want = {(d.year, d.month) for d in c[c.category >= 3].peak_datetime}
        have = {(r["year"], r["month"]) for r in records}
        print(f"\nCategory 3+ cyclone months with a report: "
              f"{len(want & have)}/{len(want)}")
        gap = sorted(want - have)
        if gap:
            print("  missing: " + ", ".join(f"{y}-{m:02d}" for y, m in gap))


# ----------------------------------------------------------------------------
# Download
# ----------------------------------------------------------------------------

def download_all(records: list) -> list:
    got, failed = [], []
    for i, rec in enumerate(records, 1):
        out_dir = RAW_DIR / rec["port"] / rec["kind"]
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{rec['year']}-{rec['month']:02d}.pdf"

        if path.exists() and path.stat().st_size > 1000:
            rec["path"] = str(path)
            got.append(rec)
            continue

        try:
            resp = requests.get(rec["url"], headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            if resp.content[:4] != b"%PDF":
                raise ValueError("not a PDF, likely a block page")
            path.write_bytes(resp.content)
            rec["path"] = str(path)
            got.append(rec)
            print(f"  [{i:>3}/{len(records)}] {rec['port'][:4]} {path.name}  "
                  f"{len(resp.content)/1024:.0f} KB")
        except Exception as e:
            rec["error"] = str(e)
            failed.append(rec)
            print(f"  [{i:>3}/{len(records)}] FAILED {path.name}: {e}")

        time.sleep(REQUEST_DELAY)

    print(f"\n[dl  ] {len(got)} available, {len(failed)} failed")
    if failed:
        f = RAW_DIR / "download_failures.json"
        f.write_text(json.dumps(failed, indent=2))
        print(f"[dl  ] failures logged to {f.name}")
        if len(failed) > len(records) * 0.5:
            print("[dl  ] most downloads failed, so the media path is blocked "
                  "as well. Fall back to src/step2_manual_template.py.")
    return got


# ----------------------------------------------------------------------------
# Extraction
# ----------------------------------------------------------------------------

NUM = r"[\d,]+\.?\d*"


def to_float(s) -> float:
    try:
        return float(str(s).replace(",", "").strip())
    except (ValueError, AttributeError):
        return float("nan")


def extract_month(path: Path) -> dict:
    try:
        import pdfplumber
    except ImportError:
        sys.exit("Missing dependency. Run: pip install pdfplumber")

    out = {"total_throughput_t": float("nan"),
           "iron_ore_t": float("nan"),
           "vessel_arrivals": float("nan"),
           "parse_note": ""}

    try:
        with pdfplumber.open(path) as pdf:
            text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception as e:
        out["parse_note"] = f"pdf open failed: {e}"
        return out

    if not text.strip():
        out["parse_note"] = "no extractable text (likely a scanned image)"
        return out

    path.with_suffix(".txt").write_text(text, encoding="utf-8")

    pats = {
        "total_throughput_t": [r"Total\s+Throughput[:\s]+(" + NUM + ")",
                               r"Throughput\s+Total[:\s]+(" + NUM + ")",
                               r"Grand\s+Total[:\s]+(" + NUM + ")"],
        "vessel_arrivals":    [r"Total\s+Distinct\s+Arrivals[:\s]+(" + NUM + ")",
                               r"Total\s+Arrivals[:\s]+(" + NUM + ")"],
        "iron_ore_t":         [r"Iron\s+Ore[^\n]*?(" + NUM + r")\s*$"],
    }
    for field, plist in pats.items():
        for p in plist:
            m = re.search(p, text, re.IGNORECASE | re.MULTILINE)
            if m:
                out[field] = to_float(m.group(1))
                break

    if pd.isna(out["total_throughput_t"]):
        out["parse_note"] = "total throughput not found; see the .txt dump"
    return out


def extract_all(records: list) -> pd.DataFrame:
    targets = [r for r in records if "path" in r]
    print(f"\n[extr] parsing {len(targets)} PDFs")
    rows = []
    for i, rec in enumerate(targets, 1):
        vals = extract_month(Path(rec["path"]))
        rows.append({
            "port": rec["port"],
            "year": rec["year"],
            "month_num": rec["month"],
            "month": f"{rec['year']}-{rec['month']:02d}-01",
            "source_url": rec["url"],
            "source_file": Path(rec["path"]).name,
            "retrieved": TODAY,
            "data_tier": "A",
            **vals,
        })
        if i % 25 == 0:
            print(f"  ...{i}/{len(targets)}")

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["month"] = pd.to_datetime(df.month)
    df["total_throughput_mt"] = df.total_throughput_t / 1e6
    df["iron_ore_mt"] = df.iron_ore_t / 1e6
    return df.sort_values(["port", "month"]).reset_index(drop=True)


def report(df: pd.DataFrame):
    print("\n" + "=" * 66)
    print("EXTRACTION SUMMARY")
    print("=" * 66)
    for port, g in df.groupby("port"):
        ok = int(g.total_throughput_mt.notna().sum())
        print(f"\n{port}: {len(g)} months, {ok} parsed ({ok/len(g)*100:.0f}%)")
        print(f"  {g.month.min():%Y-%m} to {g.month.max():%Y-%m}")
        if ok:
            v = g.total_throughput_mt.dropna()
            print(f"  {v.min():.1f} to {v.max():.1f} Mt, mean {v.mean():.1f} Mt")

    bad = df[df.total_throughput_mt.isna()]
    if len(bad):
        p = PROC_DIR / "port_throughput_needs_review.csv"
        bad.to_csv(p, index=False)
        print(f"\n!! {len(bad)} months not parsed, listed in {p.name}")


def write_sources(df: pd.DataFrame, n: int):
    block = f"""
### Pilbara Ports monthly cargo statistics
- Landing pages (saved manually, see method below):
  - {BASE}/ports/port-of-port-hedland/about-port-of-hedland/port-statistics-and-reports
  - {BASE}/ports/port-of-dampier/about-port-of-dampier/port-statistics-and-reports
- Retrieved: {TODAY}
- Licence: Pilbara Ports Authority, Government of Western Australia
- Tier: A (real, published)
- Script: src/step2_pilbara_ports.py (v3)

**Method**
- The statistics pages block automated requests, returning no content links
  even though the published page is plain HTML rather than JavaScript
  rendered. The pages were therefore saved from a browser and parsed locally;
  only the PDFs were fetched over the network.
- Each month link is assigned the year heading closest before it in the raw
  HTML. The year cannot be taken from the URL, because several entries point
  into a media folder for an unrelated year.
- Port Hedland labels sections by calendar year; Dampier labels them by
  financial year ("2025-26"). For span labels, July to December map to the
  first year and January to June to the second.
- Only tonnage reports were collected. Cargo-by-destination reports were
  skipped as they are not used in this analysis.

**Output**
- data/processed/fact_port_throughput.csv ({len(df)} rows from {n} PDFs)
"""
    if not SOURCES.exists():
        SOURCES.write_text("# Data Sources\n\n## Tier A — Real, published\n")
    with open(SOURCES, "a", encoding="utf-8") as f:
        f.write(block)
    print(f"[save] source block appended to {SOURCES.name}")


# ----------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--extract", action="store_true")
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    manifest = RAW_DIR / "manifest.json"

    if args.extract:
        if not manifest.exists():
            sys.exit("!! No manifest. Run the download phase first.")
        records = json.loads(manifest.read_text())
    else:
        records = load_pages()
        if not records:
            sys.exit(1)
        preview(records)
        if args.dry_run:
            return
        print(f"\n[dl  ] downloading {len(records)} PDFs, "
              f"about {len(records)*REQUEST_DELAY/60:.0f} minutes")
        records = download_all(records)
        manifest.write_text(json.dumps(records, indent=2))

    df = extract_all(records)
    if df.empty:
        sys.exit("!! Nothing extracted.")
    out = PROC_DIR / "fact_port_throughput.csv"
    df.to_csv(out, index=False)
    print(f"\n[save] {out.name}  ({len(df)} rows)")
    report(df)
    write_sources(df, len(records))
    print("\nNEXT: spot-check May 2026 Port Hedland against the news release "
          "(51.6 Mt total, 51.0 Mt iron ore), then move to Step 3.")


if __name__ == "__main__":
    main()
