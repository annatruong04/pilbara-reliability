#!/usr/bin/env python3
"""
Step 1 — Download and process the BOM Australian Tropical Cyclone Database.

Version 2. Changes from v1:
  * FIX: MAX_WIND_SPD is stored by BOM in metres per second, not km/h.
    v1 applied the Australian category scale directly to m/s values and
    classified 26 of 27 Pilbara events as Category 0, which contradicted the
    central pressure recorded on the same rows. Now converted (x 3.6) before
    categorising, with the original m/s value retained for provenance.
  * Added validation that cross-checks the wind-derived category against an
    independent pressure-derived category, so a unit error fails loudly.
  * Normalised placeholder cyclone names ("Noname", "Unnamed", blanks).
  * Distances now measured from the closest in-box track point, not the peak.
  * Added cyclone season labelling (Nov to Apr straddles two calendar years).

Run from the project root:
    python src/step1_download_bom.py

Outputs:
    data/raw/bom/IDCKMSTM0S.csv               raw download, never edited
    data/raw/bom/IDCKMSTM0S_<date>.csv        dated backup copy
    data/processed/dim_cyclone_event.csv      Pilbara events, one row each
    data/processed/cyclone_track_points.csv   filtered track points for mapping
    data/SOURCES.md                           appended source block
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import numpy as np
import requests

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

BOM_URL = "http://www.bom.gov.au/clim_data/IDCKMSTM0S.csv"

# Pilbara region bounding box.
# Covers Port Hedland, Dampier, Karratha, Newman and the inland mine belt.
LAT_MIN, LAT_MAX = -24.0, -17.5
LON_MIN, LON_MAX = 113.0, 122.5

START_YEAR = 2015          # match your Pilbara Ports data coverage

# BOM records MAX_WIND_SPD in metres per second.
MS_TO_KMH = 3.6

PORTS = {
    "port_hedland": (-20.31, 118.58),
    "dampier":      (-20.66, 116.71),
}

# Any track point within this distance of a port counts as a close approach.
CLOSE_APPROACH_KM = 150

ROOT      = Path(__file__).resolve().parent.parent
RAW_DIR   = ROOT / "data" / "raw" / "bom"
PROC_DIR  = ROOT / "data" / "processed"
SOURCES   = ROOT / "data" / "SOURCES.md"

TODAY = datetime.now(timezone.utc).date().isoformat()


# ----------------------------------------------------------------------------
# 1. Download
# ----------------------------------------------------------------------------

def download() -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    target = RAW_DIR / "IDCKMSTM0S.csv"

    if target.exists():
        print(f"[skip] {target.name} already present "
              f"({target.stat().st_size/1_048_576:.1f} MB). Delete for a fresh copy.")
        return target

    print(f"[get ] {BOM_URL}")
    r = requests.get(BOM_URL, timeout=120,
                     headers={"User-Agent": "student-project/1.0"})
    r.raise_for_status()
    target.write_bytes(r.content)
    print(f"[save] {target}  ({len(r.content)/1_048_576:.1f} MB)")

    backup = RAW_DIR / f"IDCKMSTM0S_{TODAY}.csv"
    shutil.copy2(target, backup)
    print(f"[save] {backup.name}  (dated backup)")
    return target


# ----------------------------------------------------------------------------
# 2. Read
# ----------------------------------------------------------------------------

MARKERS = ["DISTURBANCE_ID", "SURFACE_CODE", "LAT", "LON", "TM"]


def find_header_row(path: Path, max_scan: int = 15) -> int:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if i >= max_scan:
                break
            if sum(m in line.upper() for m in MARKERS) >= 3:
                return i
    raise RuntimeError("Header row not found in the first 15 lines.")


def pick(df: pd.DataFrame, candidates: list):
    lower = {c.lower().strip(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    for c in candidates:
        for k, v in lower.items():
            if c.lower() in k:
                return v
    return None


def load(path: Path) -> pd.DataFrame:
    hdr = find_header_row(path)
    print(f"[read] header on line {hdr}")
    df = pd.read_csv(path, skiprows=hdr, low_memory=False)

    lat_col = pick(df, ["LAT", "LATITUDE"])
    if lat_col and pd.to_numeric(df[lat_col].head(1), errors="coerce").isna().all():
        print("[read] dropping description row under header")
        df = df.iloc[1:].reset_index(drop=True)

    print(f"[read] {len(df):,} rows, {len(df.columns)} columns")
    return df


# ----------------------------------------------------------------------------
# 3. Category scales and helpers
# ----------------------------------------------------------------------------

def category_from_wind(kmh: float) -> float:
    """Australian tropical cyclone category, from max sustained wind in km/h."""
    if pd.isna(kmh):
        return np.nan
    if kmh <  63: return 0     # tropical low, below cyclone strength
    if kmh <  88: return 1
    if kmh < 125: return 2
    if kmh < 165: return 3
    if kmh < 225: return 4
    return 5


def category_from_pressure(hpa: float) -> float:
    """
    Approximate category from central pressure. Used ONLY as an independent
    cross-check on the wind-derived category, never as the reported value.
    Thresholds are indicative for the Australian region.
    """
    if pd.isna(hpa):
        return np.nan
    if hpa >= 990: return 0
    if hpa >= 985: return 1
    if hpa >= 970: return 2
    if hpa >= 955: return 3
    if hpa >= 930: return 4
    return 5


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1 = np.asarray(lat1, dtype=float)
    lon1 = np.asarray(lon1, dtype=float)
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = np.radians(lat2 - lat1)
    dl = np.radians(lon2 - lon1)
    a = np.sin(dp/2)**2 + np.cos(p1) * np.cos(p2) * np.sin(dl/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))


def clean_name(raw) -> str:
    """BOM uses 'Noname', 'Unnamed' and blanks for unnamed systems."""
    if pd.isna(raw):
        return "Unnamed"
    s = str(raw).strip()
    if s == "" or s.lower() in {"noname", "unnamed", "none", "nan", "-"}:
        return "Unnamed"
    return s.title()


def season_label(dt) -> str:
    """Cyclone season runs Nov to Apr, so it straddles two calendar years."""
    if dt.month >= 11:
        return f"{dt.year}-{str(dt.year + 1)[2:]}"
    return f"{dt.year - 1}-{str(dt.year)[2:]}"


# ----------------------------------------------------------------------------
# 4. Process
# ----------------------------------------------------------------------------

def process(df: pd.DataFrame):
    col_id   = pick(df, ["DISTURBANCE_ID", "DISTURBANCE ID"])
    col_name = pick(df, ["NAME", "NAME_x", "TC_NAME"])
    col_time = pick(df, ["TM", "DATETIME", "DATE_TIME", "TIME"])
    col_lat  = pick(df, ["LAT", "LATITUDE"])
    col_lon  = pick(df, ["LON", "LONGITUDE"])
    col_pres = pick(df, ["CENTRAL_PRES", "CENTRAL_PRESSURE", "MSLP", "PRES"])
    col_wind = pick(df, ["MAX_WIND_SPD", "MAX_WIND_SPEED", "WIND_SPD"])

    required = {"id": col_id, "time": col_time, "lat": col_lat, "lon": col_lon}
    if any(v is None for v in required.values()):
        print("\n!! Missing:", [k for k, v in required.items() if v is None])
        for c in df.columns:
            print("     ", c)
        sys.exit(1)

    print(f"[cols] id={col_id} name={col_name} time={col_time} "
          f"lat={col_lat} lon={col_lon} pres={col_pres} wind={col_wind}")

    for c in [col_lat, col_lon, col_pres, col_wind]:
        if c:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["datetime"] = pd.to_datetime(df[col_time], errors="coerce")

    # ---- UNIT FIX -----------------------------------------------------------
    # BOM stores MAX_WIND_SPD in metres per second. v1 of this script applied
    # the km/h category scale directly and classified almost every event as
    # Category 0, contradicting the central pressure on the same rows.
    if col_wind:
        df["wind_ms"]  = df[col_wind]
        df["wind_kmh"] = df[col_wind] * MS_TO_KMH
        print(f"[unit] converted {col_wind} from m/s to km/h (x{MS_TO_KMH})")
        if df.wind_ms.notna().any():
            print(f"[unit] range {df.wind_ms.min():.1f}-{df.wind_ms.max():.1f} m/s "
                  f"= {df.wind_kmh.min():.1f}-{df.wind_kmh.max():.1f} km/h")
    else:
        df["wind_ms"] = np.nan
        df["wind_kmh"] = np.nan
    # -------------------------------------------------------------------------

    before = len(df)
    df = df.dropna(subset=[col_lat, col_lon, "datetime"])
    print(f"[clean] dropped {before - len(df):,} rows missing lat/lon/time")

    in_box = (df[col_lat].between(LAT_MIN, LAT_MAX) &
              df[col_lon].between(LON_MIN, LON_MAX) &
              (df.datetime.dt.year >= START_YEAR))

    ids    = df.loc[in_box, col_id].unique()
    tracks = df[df[col_id].isin(ids)].copy()
    box    = df[in_box].copy()

    print(f"[filt] {len(ids)} cyclones entered the Pilbara box since {START_YEAR}")
    print(f"[filt] {len(tracks):,} track points retained")
    if len(ids) == 0:
        sys.exit("!! No events. Check the bounding box and START_YEAR.")

    # Distance from every in-box point to each port
    for port, (plat, plon) in PORTS.items():
        box[f"km_{port}"] = haversine(box[col_lat].values, box[col_lon].values,
                                      plat, plon)

    rows = []
    for did, g in box.groupby(col_id):
        # Peak = strongest moment while in the region. Prefer the pressure
        # minimum; fall back to the wind maximum if pressure is missing.
        if col_pres and g[col_pres].notna().any():
            peak = g.loc[g[col_pres].idxmin()]
        elif g.wind_kmh.notna().any():
            peak = g.loc[g.wind_kmh.idxmax()]
        else:
            peak = g.iloc[len(g) // 2]

        max_kmh = g.wind_kmh.max()
        max_ms  = g.wind_ms.max()
        min_hpa = g[col_pres].min() if col_pres else np.nan

        rec = {
            "disturbance_id":   did,
            "cyclone_name":     clean_name(peak[col_name]) if col_name else "Unnamed",
            "season_year":      int(g.datetime.min().year),
            "season_label":     season_label(g.datetime.min()),
            "first_in_region":  g.datetime.min(),
            "peak_datetime":    peak["datetime"],
            "last_in_region":   g.datetime.max(),
            "hours_in_region":  round((g.datetime.max() - g.datetime.min())
                                      .total_seconds() / 3600, 1),
            "peak_lat":         round(float(peak[col_lat]), 3),
            "peak_lon":         round(float(peak[col_lon]), 3),
            "min_pressure_hpa": float(min_hpa) if pd.notna(min_hpa) else np.nan,
            "max_wind_ms":      round(float(max_ms), 1) if pd.notna(max_ms) else np.nan,
            "max_wind_kmh":     round(float(max_kmh), 1) if pd.notna(max_kmh) else np.nan,
            "track_points":     int((tracks[col_id] == did).sum()),
        }

        rec["category"]           = category_from_wind(max_kmh)
        rec["category_from_pres"] = category_from_pressure(min_hpa)

        for port in PORTS:
            nearest = float(g[f"km_{port}"].min())
            rec[f"km_to_{port}"] = round(nearest, 1)
            rec[f"close_{port}"] = bool(nearest <= CLOSE_APPROACH_KM)

        rows.append(rec)

    ev = pd.DataFrame(rows).sort_values("peak_datetime").reset_index(drop=True)
    ev["cyclone_id"] = range(1, len(ev) + 1)
    ev["month"]      = ev.peak_datetime.dt.to_period("M").dt.to_timestamp()
    ev["data_tier"]  = "A"

    order = ["cyclone_id", "disturbance_id", "cyclone_name", "season_year",
             "season_label", "month", "peak_datetime", "first_in_region",
             "last_in_region", "hours_in_region", "category",
             "category_from_pres", "max_wind_ms", "max_wind_kmh",
             "min_pressure_hpa", "peak_lat", "peak_lon",
             "km_to_port_hedland", "close_port_hedland",
             "km_to_dampier", "close_dampier", "track_points", "data_tier"]
    ev = ev[[c for c in order if c in ev.columns]]

    tracks = tracks.rename(columns={col_lat: "lat", col_lon: "lon"})
    tracks["data_tier"] = "A"

    return ev, tracks


# ----------------------------------------------------------------------------
# 5. Validation — fail loudly on the kind of error v1 shipped silently
# ----------------------------------------------------------------------------

def validate(ev: pd.DataFrame) -> list:
    warnings = []
    print("\n" + "-" * 62)
    print("VALIDATION")
    print("-" * 62)

    # 1. Wind-derived and pressure-derived categories should broadly agree.
    both = ev.dropna(subset=["category", "category_from_pres"])
    if len(both):
        mean_diff = (both.category - both.category_from_pres).abs().mean()
        print(f"  wind vs pressure category, mean absolute difference: {mean_diff:.2f}")
        if mean_diff > 1.5:
            warnings.append(
                f"Wind and pressure categories disagree badly "
                f"(mean difference {mean_diff:.2f}). Check the unit conversion.")

    # 2. A severe pressure reading must not come back as Category 0 or 1.
    bad = ev[(ev.min_pressure_hpa < 960) & (ev.category <= 1)]
    if len(bad):
        warnings.append(
            f"{len(bad)} event(s) below 960 hPa classified as Category 0 or 1. "
            "This is the exact symptom of a wind unit error.")
        print("\n  Suspect rows:")
        print(bad[["cyclone_name", "min_pressure_hpa", "category"]]
              .to_string(index=False))

    # 3. Physical plausibility of the converted wind speeds.
    if ev.max_wind_kmh.notna().any():
        hi = ev.max_wind_kmh.max()
        print(f"  strongest recorded wind: {hi:.0f} km/h")
        if hi < 100:
            warnings.append(
                f"Strongest wind only {hi:.0f} km/h across {len(ev)} events. "
                "Implausibly low for the Pilbara, likely still in m/s.")
        if hi > 350:
            warnings.append(f"Strongest wind {hi:.0f} km/h is implausibly high.")

    # 4. Category distribution sanity.
    n_severe = int((ev.category >= 3).sum())
    print(f"  Category 3+ events: {n_severe} of {len(ev)}")
    if n_severe == 0:
        warnings.append(
            "No Category 3+ events in over a decade of Pilbara data. "
            "Rio Tinto reported four cyclones affecting Q1 2025 alone.")

    # 5. Known reference events, checked against published BOM reports.
    print()
    for name, expect in [("Ilsa", 4), ("Veronica", 3), ("Zelia", 4)]:
        m = ev[ev.cyclone_name.str.contains(name, case=False, na=False)]
        if len(m):
            got = m.iloc[0].category
            flag = "ok" if got >= expect else "TOO LOW"
            print(f"  {name:<10} category {got:.0f}  (expected {expect}+)  [{flag}]")
            if got < expect:
                warnings.append(
                    f"{name} classified as Category {got:.0f}, expected {expect}+.")
        else:
            print(f"  {name:<10} not found in the filtered set")

    if warnings:
        print("\n  !! WARNINGS")
        for w in warnings:
            print(f"     - {w}")
    else:
        print("\n  All checks passed.")
    return warnings


# ----------------------------------------------------------------------------
# 6. Save
# ----------------------------------------------------------------------------

def save(ev, tracks, raw):
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    p1 = PROC_DIR / "dim_cyclone_event.csv"
    p2 = PROC_DIR / "cyclone_track_points.csv"
    ev.to_csv(p1, index=False)
    tracks.to_csv(p2, index=False)
    print(f"\n[save] {p1.name}  ({len(ev)} events)")
    print(f"[save] {p2.name}  ({len(tracks):,} points)")

    block = f"""
### BOM Australian Tropical Cyclone Database
- Landing page: https://www.bom.gov.au/cyclone/tropical-cyclone-knowledge-centre/databases/
- Endpoint: {BOM_URL}
- Retrieved: {TODAY}
- Raw file: data/raw/bom/{raw.name} ({raw.stat().st_size/1_048_576:.1f} MB)
- Licence: Commonwealth of Australia, Bureau of Meteorology
- Tier: A (real, published)
- Script: src/step1_download_bom.py (v2)

**Processing**
- Retained all track points for any cyclone with at least one observation
  inside the Pilbara bounding box (lat {LAT_MIN} to {LAT_MAX},
  lon {LON_MIN} to {LON_MAX}) from {START_YEAR} onward.
- Aggregated to one row per event. Peak defined as the in-box observation with
  the lowest central pressure.
- Distances to Port Hedland and Dampier computed by haversine from the closest
  in-box track point.

**Known data quality issue and correction**
- MAX_WIND_SPD is recorded by BOM in metres per second. Version 1 of this
  script applied the Australian km/h category scale directly to those values
  and classified 26 of 27 Pilbara events as Category 0, contradicting the
  central pressure recorded on the same rows. Cyclone Zelia, at 927 hPa,
  returned Category 0.
- Corrected by converting to km/h (x {MS_TO_KMH}) before categorising. Both the
  original m/s value and the converted km/h value are retained in the output.
- A validation step now cross-checks the wind-derived category against an
  independent pressure-derived category and against three published reference
  events, and fails loudly if they diverge.

**Outputs**
- data/processed/dim_cyclone_event.csv ({len(ev)} events)
- data/processed/cyclone_track_points.csv ({len(tracks):,} points)
"""
    if not SOURCES.exists():
        SOURCES.write_text("# Data Sources\n\n## Tier A — Real, published\n")
    with open(SOURCES, "a", encoding="utf-8") as f:
        f.write(block)
    print(f"[save] source block appended to {SOURCES.name}")


# ----------------------------------------------------------------------------

def main():
    raw = download()
    df = load(raw)
    ev, tracks = process(df)
    warnings = validate(ev)
    save(ev, tracks, raw)

    print("\n" + "=" * 80)
    print("PILBARA CYCLONE EVENTS")
    print("=" * 80)
    show = ["cyclone_id", "cyclone_name", "peak_datetime", "category",
            "max_wind_ms", "max_wind_kmh", "min_pressure_hpa",
            "km_to_port_hedland"]
    print(ev[show].to_string(index=False))

    print("\nBy category:")
    print(ev.category.value_counts().sort_index().to_string())

    sev = ev[ev.category >= 3].sort_values("category", ascending=False)
    if len(sev):
        print(f"\nCategory 3+ events ({len(sev)}):")
        print(sev[["cyclone_name", "peak_datetime", "category", "max_wind_kmh",
                   "min_pressure_hpa", "km_to_port_hedland"]]
              .to_string(index=False))

    print("\nEvents per season:")
    print(ev.season_label.value_counts().sort_index().to_string())

    if warnings:
        print("\nResolve the warnings above before building on this data.")
    else:
        print("\nNEXT: verify three cyclone names and categories against BOM "
              "reports or Wikipedia, then move to Step 2 (Pilbara Ports).")


if __name__ == "__main__":
    main()
