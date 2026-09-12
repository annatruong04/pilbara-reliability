#!/usr/bin/env python3
"""
Step 5 — Generate the DAX measure library.

Power BI Desktop has no bulk measure import. Typing seventy measures by hand
takes hours and reliably introduces typos. This script writes them out in
three formats:

    powerbi/measures.csx    Tabular Editor 2 C# script, creates all measures
    powerbi/measures.tmdl   TMDL fragment, for .pbip projects
    powerbi/measures.md     plain reference, for copying one at a time

It also writes a starter data quality table, since page 5 of the dashboard
needs one and it does not exist yet:

    data/processed/dim_data_quality.csv

Version 2. Changes from v1:
  * Added return period measures. v1 loaded dim_return_period but had no
    measure reading from it, so page 3's return period panel had nothing to
    display.
  * Added season aggregation and rolling twelve-month measures. The cyclone
    season runs November to April, so grouping by calendar year cuts every
    season in half.
  * Added conditional formatting colour measures and dynamic titles.
  * Added data quality measures and generated the table they read from.

Model coefficients are read from analysis_model_results.csv rather than
hardcoded, so refitting the model and rerunning this script keeps the
dashboard consistent with the analysis. A hardcoded coefficient goes stale
silently the moment the model changes.

Run from the project root:
    python src/step5_generate_dax.py

Then, to load into Power BI:
    1. Download Tabular Editor 2 (free) from tabulareditor.com
    2. In Power BI Desktop, create the holding table:
       Modeling > New table >  _Measures = { BLANK() }
       Hide the single column it creates.
    3. Load data/processed/dim_data_quality.csv as a table
    4. External Tools ribbon > Tabular Editor
    5. File > Open > powerbi/measures.csx, press F5
    6. File > Save, then refresh the field list in Power BI Desktop
"""

import csv
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
OUT = ROOT / "powerbi"

MEASURE_TABLE = "_Measures"
TODAY = datetime.now(timezone.utc).date().isoformat()


# ----------------------------------------------------------------------------
# Read the fitted coefficients so the dashboard cannot drift from the analysis
# ----------------------------------------------------------------------------

def load_coefficients() -> dict:
    path = PROC / "analysis_model_results.csv"
    fallback = {"coef": -1.662, "lo": -2.415, "hi": -0.909,
                "source": "fallback defaults, model results file not found"}

    if not path.exists():
        print(f"[warn] {path.name} not found, using fallback coefficients")
        return fallback

    res = pd.read_csv(path)
    pref = res[res.model.str.startswith("M2")]
    if pref.empty:
        print("[warn] no M2 row found, using fallback coefficients")
        return fallback

    r = pref.iloc[0]
    print(f"[read] M2 coefficient {r.coef_mt:+.4f} "
          f"[{r.ci_low:+.4f}, {r.ci_high:+.4f}] from {path.name}")
    return {"coef": float(r.coef_mt), "lo": float(r.ci_low),
            "hi": float(r.ci_high),
            "source": f"{path.name}, model {r.model}, n={int(r.n)}"}


def observed_capability() -> float:
    path = PROC / "fact_reliability_monthly.csv"
    if path.exists():
        return float(pd.read_csv(path).daily_capability_mt.mean())
    return float("nan")


# ----------------------------------------------------------------------------
# Data quality table — page 5 needs this and it does not exist yet
# ----------------------------------------------------------------------------

DQ_ROWS = [
    {
        "defect_id": 1,
        "defect": "Wind unit error",
        "stage": "Step 1, cyclone extraction",
        "symptom": "26 of 27 events classified Category 0, contradicting the "
                   "central pressure recorded on the same rows. Cyclone Zelia "
                   "at 927 hPa returned Category 0.",
        "root_cause": "BOM stores MAX_WIND_SPD in metres per second, not "
                      "kilometres per hour. The Australian category scale was "
                      "applied directly to the raw values.",
        "fix": "Convert to km/h before categorising. Added an automated "
               "cross-check against a pressure-derived category and three "
               "published reference events.",
        "records_affected": 27,
        "total_records": 27,
        "severity": "High",
        "status": "Fixed",
        "detected_by": "Cross-field consistency check",
    },
    {
        "defect_id": 2,
        "defect": "Financial year section labels",
        "stage": "Step 2, port statistics discovery",
        "symptom": "Discovery returned zero monthly reports for both ports "
                   "despite the pages listing 139 of them.",
        "root_cause": "Dampier labels sections by financial year (2025-26) "
                      "while Port Hedland uses calendar years. The matcher "
                      "accepted only four-digit labels, so no year was ever "
                      "detected and every link was discarded.",
        "fix": "Accept both label formats. For a financial year span, map "
               "July to December to the first year and January to June to "
               "the second.",
        "records_affected": 278,
        "total_records": 278,
        "severity": "High",
        "status": "Fixed",
        "detected_by": "Zero-result sanity check",
    },
    {
        "defect_id": 3,
        "defect": "Uncontrolled baseline comparison",
        "stage": "Step 3, impact analysis",
        "symptom": "Q1 2025 showed a 9.1 Mt surplus against the Q1 average, "
                   "directly contradicting the regression run on the same "
                   "data, which found a loss.",
        "root_cause": "The baseline averaged all Q1 months since 2015, a "
                      "period spanning substantial port growth. The "
                      "comparison measured expansion, not disruption.",
        "fix": "Replaced with a model counterfactual that controls for "
               "calendar month and long-run trend.",
        "records_affected": 3,
        "total_records": 137,
        "severity": "High",
        "status": "Fixed",
        "detected_by": "Contradiction between two figures from one dataset",
    },
    {
        "defect_id": 4,
        "defect": "Future-dated report",
        "stage": "Step 2, port statistics discovery",
        "symptom": "A report was assigned to July 2027, a month that has not "
                   "occurred.",
        "root_cause": "Port Hedland files the current month under a "
                      "financial-year-end heading, so July 2026 appears "
                      "beneath a 2027 label.",
        "fix": "Any assignment landing past the current month is pulled back "
               "one year. A published report cannot describe the future.",
        "records_affected": 1,
        "total_records": 139,
        "severity": "Medium",
        "status": "Fixed",
        "detected_by": "Range check against the current date",
    },
    {
        "defect_id": 5,
        "defect": "Sparse gale radius field",
        "stage": "Step 1, field selection",
        "symptom": "MN_RADIUS_GF_WIND looked ideal for measuring whether "
                   "gale-force winds actually reached the port.",
        "root_cause": "The field is populated on 12 of 958 track points, "
                      "about 1%. It was not routinely recorded for most of "
                      "the period.",
        "fix": "Rejected the field rather than imputing it. Used track "
               "distance to the port instead.",
        "records_affected": 946,
        "total_records": 958,
        "severity": "Medium",
        "status": "Rejected",
        "detected_by": "Completeness profiling before use",
    },
    {
        "defect_id": 6,
        "defect": "Unavailable source month",
        "stage": "Step 2, download",
        "symptom": "One month of 139 could not be downloaded.",
        "root_cause": "The July 2021 link points to a web page rather than a "
                      "PDF.",
        "fix": "Excluded and documented rather than interpolated. One month "
               "of 138 does not affect the analysis.",
        "records_affected": 1,
        "total_records": 139,
        "severity": "Low",
        "status": "Accepted",
        "detected_by": "Content-type check on download",
    },
    {
        "defect_id": 7,
        "defect": "Wind speed granularity",
        "stage": "Step 3, variable selection",
        "symptom": "Converted wind speeds take only 13 distinct values across "
                   "958 observations.",
        "root_cause": "BOM records winds in whole 5-knot bands, then stores "
                      "the converted metres-per-second value. The variable is "
                      "effectively ordinal, not continuous.",
        "fix": "Used central pressure and category as severity measures. Wind "
               "speed is retained for display only, not as a continuous "
               "regressor.",
        "records_affected": 958,
        "total_records": 958,
        "severity": "Medium",
        "status": "Mitigated",
        "detected_by": "Distinct value count during profiling",
    },
]


def write_data_quality_table():
    path = PROC / "dim_data_quality.csv"
    if path.exists():
        print(f"[skip] {path.name} already exists, leaving it alone")
        return

    PROC.mkdir(parents=True, exist_ok=True)
    fields = list(DQ_ROWS[0].keys()) + ["pct_affected", "data_tier"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in DQ_ROWS:
            row = dict(r)
            row["pct_affected"] = round(
                r["records_affected"] / r["total_records"], 4)
            row["data_tier"] = "A"
            w.writerow(row)
    print(f"[save] {path.name}  ({len(DQ_ROWS)} defects)")


# ----------------------------------------------------------------------------
# Measure definitions — single source of truth
# ----------------------------------------------------------------------------

def build_measures(c: dict) -> list:
    """Each entry: (name, dax, format string or None, folder, description)."""

    return [
        # ---------------- 00 Constants ----------------
        ("Severity Coefficient", f"{c['coef']:.4f}", "0.0000", "00 Constants",
         f"Regression coefficient on proximity-weighted severity. "
         f"Source: {c['source']}"),
        ("Severity CI Low", f"{c['lo']:.4f}", "0.0000", "00 Constants",
         "Lower bound of the 95% confidence interval."),
        ("Severity CI High", f"{c['hi']:.4f}", "0.0000", "00 Constants",
         "Upper bound of the 95% confidence interval."),
        ("AUD per USD", "0.65", "0.00", "00 Constants",
         "Exchange rate assumption, used only to express tonnes as dollars."),
        ("Proximity Decay Km", "200", "0", "00 Constants",
         "Distance scale for the severity weighting. An assumption."),
        ("Availability Target", "0.98", "0.0%", "00 Constants",
         "Illustrative benchmark. Not sourced from Pilbara Ports."),

        # ---------------- 01 Reliability ----------------
        ("Total Downtime Days",
         "SUM ( fact_reliability_event[event_downtime_days] )",
         "#,0.0", "01 Reliability",
         "Estimated production-equivalent lost days across cyclone events."),

        ("Total Downtime Hours",
         "SUM ( fact_reliability_event[event_downtime_hours] )",
         "#,0", "01 Reliability", "Downtime expressed in hours."),

        ("Total Lost Mt",
         "SUM ( fact_reliability_event[event_lost_mt] )",
         "#,0.0", "01 Reliability",
         "Estimated production lost to cyclone events, million tonnes."),

        ("Event Count", "COUNTROWS ( fact_reliability_event )",
         "#,0", "01 Reliability", "Number of cyclone events in context."),

        ("Severe Event Count",
         "CALCULATE ( [Event Count], fact_reliability_event[category] >= 3 )",
         "#,0", "01 Reliability", "Category 3 and above events."),

        ("Observation Years",
         "DIVIDE ( DISTINCTCOUNT ( fact_reliability_monthly[month] ), 12 )",
         "#,0.0", "01 Reliability", "Observation window in years."),

        ("Downtime Days Per Year",
         "DIVIDE ( [Total Downtime Days], [Observation Years] )",
         "#,0.0", "01 Reliability", "Annualised downtime."),

        ("Lost Mt Per Year",
         "DIVIDE ( [Total Lost Mt], [Observation Years] )",
         "#,0.0", "01 Reliability", "Annualised production loss."),

        ("Availability Pct",
         "AVERAGE ( fact_reliability_monthly[availability] )",
         "0.00%", "01 Reliability",
         "Mean monthly availability against modelled no-cyclone capability."),

        ("Weather Availability Pct",
         "CALCULATE ( [Availability Pct], "
         "fact_reliability_monthly[weighted_severity] > 0 )",
         "0.00%", "01 Reliability",
         "Availability restricted to months with a cyclone. Headline figure."),

        ("Overall Weather Availability",
         "1 - DIVIDE ( [Total Downtime Days], [Observation Years] * 365.25 )",
         "0.00%", "01 Reliability",
         "Availability across the whole period. Higher than the weather-month "
         "figure because the denominator differs. Show it as supporting text, "
         "not as a second headline, or readers will assume an error."),

        ("Months Below Target",
         "CALCULATE ( COUNTROWS ( fact_reliability_monthly ), "
         "fact_reliability_monthly[availability] < [Availability Target] )",
         "#,0", "01 Reliability", "Months falling short of the target."),

        # ---------------- 02 MTBF and MTTR ----------------
        ("MTBF Days",
         "AVERAGE ( fact_reliability_event[days_since_previous] )",
         "#,0", "02 MTBF and MTTR",
         "Mean days between consecutive events, all severities. Pulled down "
         "by tropical lows, so pair it with the severe-only figure."),

        ("MTBF Years", "DIVIDE ( [MTBF Days], 365.25 )",
         "#,0.00", "02 MTBF and MTTR", "MTBF expressed in years."),

        ("MTBF Severe Days",
         """VAR Severe =
    FILTER (
        ALLSELECTED ( fact_reliability_event ),
        fact_reliability_event[category] >= 3
    )
VAR N = COUNTROWS ( Severe )
VAR FirstDate = MINX ( Severe, fact_reliability_event[peak_datetime] )
VAR LastDate = MAXX ( Severe, fact_reliability_event[peak_datetime] )
RETURN
    IF ( N > 1, DIVIDE ( DATEDIFF ( FirstDate, LastDate, DAY ), N - 1 ) )""",
         "#,0", "02 MTBF and MTTR",
         "MTBF for Category 3 and above only. The planning-relevant figure."),

        ("MTTR Days",
         "AVERAGE ( fact_reliability_event[event_downtime_days] )",
         "#,0.00", "02 MTBF and MTTR",
         "Mean days to restore normal throughput. Inferred from monthly "
         "tonnage, not a measured repair duration."),

        ("MTTR Severe Days",
         "CALCULATE ( [MTTR Days], fact_reliability_event[category] >= 3 )",
         "#,0.00", "02 MTBF and MTTR", "MTTR for Category 3 and above."),

        ("MTTR Cat4 Plus Days",
         "CALCULATE ( [MTTR Days], fact_reliability_event[category] >= 4 )",
         "#,0.00", "02 MTBF and MTTR", "MTTR for Category 4 and above."),

        # ---------------- 03 Pareto ----------------
        ("Downtime Rank",
         """RANKX (
    ALLSELECTED ( fact_reliability_event[category_label] ),
    [Total Downtime Days],
    ,
    DESC
)""", "#,0", "03 Pareto", "Rank of each category by total downtime."),

        ("Cumulative Downtime Days",
         """VAR CurrentRank = [Downtime Rank]
RETURN
    SUMX (
        FILTER (
            ALLSELECTED ( fact_reliability_event[category_label] ),
            [Downtime Rank] <= CurrentRank
        ),
        [Total Downtime Days]
    )""", "#,0.0", "03 Pareto", "Running total for the Pareto line."),

        ("Cumulative Downtime Pct",
         """DIVIDE (
    [Cumulative Downtime Days],
    CALCULATE (
        [Total Downtime Days],
        ALLSELECTED ( fact_reliability_event[category_label] )
    )
)""", "0.0%", "03 Pareto", "Cumulative percentage for the Pareto line."),

        ("Severe Share of Downtime",
         """DIVIDE (
    CALCULATE ( [Total Downtime Days], fact_reliability_event[category] >= 3 ),
    CALCULATE ( [Total Downtime Days], ALL ( fact_reliability_event[category] ) )
)""", "0.0%", "03 Pareto",
         "Share of all downtime from Category 3 and above."),

        ("Severe Share of Events",
         """DIVIDE (
    [Severe Event Count],
    CALCULATE ( [Event Count], ALL ( fact_reliability_event[category] ) )
)""", "0.0%", "03 Pareto",
         "Share of events that are severe. Contrast with the downtime share "
         "to show the Pareto effect."),

        ("Pareto Statement",
         """"Category 3 and above: " & FORMAT ( [Severe Share of Events], "0%" )
    & " of events, " & FORMAT ( [Severe Share of Downtime], "0%" )
    & " of downtime\"""",
         None, "03 Pareto", "One-line summary for a card."),

        # ---------------- 04 Scenario ----------------
        ("Scenario Weighted Severity",
         """VAR Cat = SELECTEDVALUE ( 'Scenario Category'[Category], 3 )
VAR Km = SELECTEDVALUE ( 'Scenario Distance'[Km], 100 )
RETURN
    Cat * EXP ( - DIVIDE ( Km, [Proximity Decay Km] ) )""",
         "#,0.00", "04 Scenario",
         "Category weighted by proximity, matching the regression input."),

        ("Expected Loss Mt",
         "ABS ( [Severity Coefficient] ) * [Scenario Weighted Severity]",
         "#,0.0", "04 Scenario", "Central estimate of production lost."),

        ("Expected Loss Low Mt",
         "ABS ( [Severity CI High] ) * [Scenario Weighted Severity]",
         "#,0.0", "04 Scenario", "Lower bound. Never display without this."),

        ("Expected Loss High Mt",
         "ABS ( [Severity CI Low] ) * [Scenario Weighted Severity]",
         "#,0.0", "04 Scenario", "Upper bound. Never display without this."),

        ("Daily Capability Mt",
         "AVERAGE ( fact_reliability_monthly[daily_capability_mt] )",
         "#,0.00", "04 Scenario",
         "Mean daily throughput capability, converts tonnes to days."),

        ("Expected Downtime Days",
         "DIVIDE ( [Expected Loss Mt], [Daily Capability Mt] )",
         "#,0.0", "04 Scenario", "Loss as days of normal throughput."),

        ("Value At Risk AUD",
         """VAR PriceUSD = SELECTEDVALUE ( 'Iron Ore Price'[USD per tonne], 100 )
RETURN
    [Expected Loss Mt] * 1000000 * PriceUSD / [AUD per USD]""",
         "\\$#,0;(\\$#,0)", "04 Scenario",
         "Deferred shipment value. Price and exchange rate are assumptions."),

        ("Loss Statement",
         """"Estimated " & FORMAT ( [Expected Loss Mt], "0.0" ) & " Mt lost, range "
    & FORMAT ( [Expected Loss Low Mt], "0.0" ) & " to "
    & FORMAT ( [Expected Loss High Mt], "0.0" ) & " Mt. About "
    & FORMAT ( [Expected Downtime Days], "0.0" ) & " days of throughput.\"""",
         None, "04 Scenario",
         "Card text. Keeps the range attached to the central estimate."),

        ("Nearest Analogue",
         """VAR Cat = SELECTEDVALUE ( 'Scenario Category'[Category], 3 )
VAR Km = SELECTEDVALUE ( 'Scenario Distance'[Km], 100 )
VAR Ranked =
    ADDCOLUMNS (
        ALL ( fact_reliability_event ),
        "@dist",
            ABS ( fact_reliability_event[category] - Cat ) * 100
                + ABS ( fact_reliability_event[km_to_port_hedland] - Km )
    )
VAR Best = TOPN ( 1, Ranked, [@dist], ASC )
RETURN
    CONCATENATEX ( Best, fact_reliability_event[event_label] )""",
         None, "04 Scenario",
         "Closest historical event to the scenario. Operators trust a named "
         "past event more than a modelled number."),

        ("Analogue Actual Loss Mt",
         """VAR Cat = SELECTEDVALUE ( 'Scenario Category'[Category], 3 )
VAR Km = SELECTEDVALUE ( 'Scenario Distance'[Km], 100 )
VAR Ranked =
    ADDCOLUMNS (
        ALL ( fact_reliability_event ),
        "@dist",
            ABS ( fact_reliability_event[category] - Cat ) * 100
                + ABS ( fact_reliability_event[km_to_port_hedland] - Km )
    )
VAR Best = TOPN ( 1, Ranked, [@dist], ASC )
RETURN
    MAXX ( Best, fact_reliability_event[event_lost_mt] )""",
         "#,0.00", "04 Scenario",
         "What the nearest analogue actually cost. Sits beside the modelled "
         "estimate as a reality check."),

        # ---------------- 05 Shutdown timing ----------------
        ("Production Forgone AUD",
         """VAR t = SELECTEDVALUE ( 'Lead Hours'[Hours] )
VAR PriceUSD = SELECTEDVALUE ( 'Iron Ore Price'[USD per tonne], 100 )
RETURN
    t * DIVIDE ( [Daily Capability Mt], 24 ) * 1000000 * PriceUSD
        / [AUD per USD]""",
         "\\$#,0", "05 Shutdown timing",
         "Cost of stopping early. Derived from measured throughput."),

        ("Damage Probability",
         """VAR t = SELECTEDVALUE ( 'Lead Hours'[Hours] )
VAR Cat = SELECTEDVALUE ( 'Scenario Category'[Category], 3 )
VAR Mult = SELECTEDVALUE ( 'Curve Sensitivity'[Multiplier], 1 )
VAR k = DIVIDE ( 0.06, MAX ( Cat, 1 ) ) * Mult
VAR mid = 12 * Cat
RETURN
    DIVIDE ( 1, 1 + EXP ( k * ( t - mid ) ) )""",
         "0.0%", "05 Shutdown timing",
         "ASSUMPTION, not fitted. No operator publishes incident-level damage "
         "outcomes. Structured so a fitted curve can replace it."),

        ("Expected Damage Cost AUD",
         """VAR Cat = SELECTEDVALUE ( 'Scenario Category'[Category], 3 )
VAR DamageCostPerCat = 50000000
RETURN
    [Damage Probability] * DamageCostPerCat * Cat""",
         "\\$#,0", "05 Shutdown timing",
         "Damage cost per category is an assumption, stated on the page."),

        ("Total Expected Cost AUD",
         "[Production Forgone AUD] + [Expected Damage Cost AUD]",
         "\\$#,0", "05 Shutdown timing", "The curve to minimise."),

        ("WHS Minimum Hours",
         """VAR Cat = SELECTEDVALUE ( 'Scenario Category'[Category], 3 )
RETURN
    IF ( Cat >= 3, 72, 48 )""",
         "#,0", "05 Shutdown timing",
         "Minimum safe evacuation window. A hard constraint, not a cost. "
         "Below this the option does not exist at any price."),

        ("Cost Within WHS Limit",
         """IF (
    SELECTEDVALUE ( 'Lead Hours'[Hours] ) >= [WHS Minimum Hours],
    [Total Expected Cost AUD]
)""", "\\$#,0", "05 Shutdown timing",
         "Total cost, blanked inside the forbidden window."),

        ("Optimal Lead Hours",
         """VAR Costs =
    ADDCOLUMNS (
        FILTER ( ALL ( 'Lead Hours' ), 'Lead Hours'[Hours] >= [WHS Minimum Hours] ),
        "@cost", [Total Expected Cost AUD]
    )
VAR Best = TOPN ( 1, Costs, [@cost], ASC )
RETURN
    MAXX ( Best, 'Lead Hours'[Hours] )""",
         "#,0", "05 Shutdown timing",
         "Lowest-cost lead time inside the safe window."),

        ("Optimal Statement",
         """"Recommended shutdown: " & FORMAT ( [Optimal Lead Hours], "0" )
    & " hours before landfall. WH&S minimum is "
    & FORMAT ( [WHS Minimum Hours], "0" ) & " hours.\"""",
         None, "05 Shutdown timing", "Card text for the recommendation."),

        # ---------------- 06 Validation ----------------
        ("Actual Mt",
         "SUM ( fact_reliability_monthly[total_throughput_mt] )",
         "#,0.0", "06 Validation", "Observed throughput."),

        ("Fitted Mt", "SUM ( fact_reliability_monthly[fitted_mt] )",
         "#,0.0", "06 Validation", "Model prediction with observed severity."),

        ("Capability Mt", "SUM ( fact_reliability_monthly[capability_mt] )",
         "#,0.0", "06 Validation",
         "Model prediction with severity set to zero."),

        ("Modelled Loss Mt", "SUM ( fact_reliability_monthly[lost_mt] )",
         "#,0.0", "06 Validation",
         "Capability minus fitted. Not capability minus actual: the gap "
         "between actual and fitted is ordinary model residual."),

        ("Residual Mt", "[Actual Mt] - [Fitted Mt]",
         "#,0.0", "06 Validation", "Model error, unrelated to cyclones."),

        ("Mean Absolute Error Mt",
         """AVERAGEX (
    fact_reliability_monthly,
    ABS (
        fact_reliability_monthly[total_throughput_mt]
            - fact_reliability_monthly[fitted_mt]
    )
)""", "#,0.00", "06 Validation", "Average absolute model error."),

        ("Implied Closure Days",
         "DIVIDE ( [Total Lost Mt], [Daily Capability Mt] )",
         "#,0.0", "06 Validation",
         "Loss converted to days. The model never sees closure durations, so "
         "agreement with observed practice is external corroboration."),

        # ---------------- 07 Return periods ----------------
        ("Return Period Years",
         "AVERAGE ( dim_return_period[return_period_years] )",
         "#,0.0", "07 Return periods",
         "Years between events of at least the selected severity and "
         "proximity."),

        ("Events Per Year",
         "AVERAGE ( dim_return_period[events_per_year] )",
         "#,0.000", "07 Return periods",
         "Poisson rate for the selected severity and proximity."),

        ("Season Probability",
         "AVERAGE ( dim_return_period[prob_at_least_one_per_year] )",
         "0.0%", "07 Return periods",
         "Chance of at least one such event in any given season."),

        ("Return Period Statement",
         """VAR RP = [Return Period Years]
VAR P = [Season Probability]
RETURN
    IF (
        ISBLANK ( RP ),
        "Not observed in the record",
        "About once every " & FORMAT ( RP, "0.0" ) & " years, "
            & FORMAT ( P, "0%" ) & " chance in any season"
    )""",
         None, "07 Return periods",
         "Plain-English card text. Handles the not-observed case rather than "
         "showing a blank."),

        ("Expected Events Next Decade",
         "[Events Per Year] * 10",
         "#,0.0", "07 Return periods",
         "Planning horizon figure. Easier to act on than a return period."),

        ("Return Period Sample Size",
         "SUM ( dim_return_period[events] )",
         "#,0", "07 Return periods",
         "Events the return period rests on. Show it: a 5.7 year figure "
         "built on two observations should be read as indicative."),

        # ---------------- 08 Time ----------------
        ("Season Downtime Days",
         """CALCULATE (
    [Total Downtime Days],
    ALLEXCEPT ( fact_reliability_event, fact_reliability_event[season_label] )
)""", "#,0.0", "08 Time",
         "Downtime by cyclone season. The season runs November to April, so a "
         "calendar year split would cut every season in half."),

        ("Worst Season Days",
         """MAXX (
    VALUES ( fact_reliability_event[season_label] ),
    [Season Downtime Days]
)""", "#,0.0", "08 Time", "Worst season on record."),

        ("Worst Season Label",
         """VAR Ranked =
    ADDCOLUMNS (
        VALUES ( fact_reliability_event[season_label] ),
        "@days", [Season Downtime Days]
    )
VAR Best = TOPN ( 1, Ranked, [@days], DESC )
RETURN
    CONCATENATEX ( Best, fact_reliability_event[season_label] )""",
         None, "08 Time", "Which season was worst."),

        ("Availability Rolling 12",
         """VAR LastMonth = MAX ( fact_reliability_monthly[month] )
RETURN
    CALCULATE (
        [Availability Pct],
        FILTER (
            ALL ( fact_reliability_monthly ),
            fact_reliability_monthly[month] <= LastMonth
                && fact_reliability_monthly[month] > EDATE ( LastMonth, -12 )
        )
    )""", "0.00%", "08 Time",
         "Twelve-month rolling availability. Smooths the seasonal sawtooth."),

        ("Downtime Days Rolling 12",
         """VAR LastMonth = MAX ( fact_reliability_monthly[month] )
RETURN
    CALCULATE (
        [Total Downtime Days],
        FILTER (
            ALL ( fact_reliability_event ),
            fact_reliability_event[month] <= LastMonth
                && fact_reliability_event[month] > EDATE ( LastMonth, -12 )
        )
    )""", "#,0.0", "08 Time", "Rolling twelve-month downtime."),

        # ---------------- 09 Formatting ----------------
        ("Availability Colour",
         """VAR A = [Availability Pct]
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( A ), "#888780",
        A >= [Availability Target], "#1D9E75",
        A >= 0.95, "#EF9F27",
        "#E24B4A"
    )""", None, "09 Formatting",
         "Feed to conditional formatting via Format > Fx > Field value."),

        ("Severity Colour",
         """VAR C = SELECTEDVALUE ( fact_reliability_event[category] )
RETURN
    SWITCH (
        TRUE (),
        C >= 4, "#A32D2D",
        C = 3, "#BA7517",
        C >= 1, "#378ADD",
        "#888780"
    )""", None, "09 Formatting",
         "Category colour for charts. Pair with a shape or pattern so colour "
         "is not the only cue."),

        ("Page Title",
         """VAR Cat = SELECTEDVALUE ( 'Scenario Category'[Category] )
VAR Km = SELECTEDVALUE ( 'Scenario Distance'[Km] )
RETURN
    IF (
        ISBLANK ( Cat ) || ISBLANK ( Km ),
        "Select a scenario",
        "Category " & Cat & " at " & Km & " km from Port Hedland"
    )""", None, "09 Formatting",
         "Dynamic title so a screenshot always shows which scenario is set."),

        ("Row Count Check",
         """"Months: " & DISTINCTCOUNT ( fact_reliability_monthly[month] )
    & "   Events: " & [Event Count]
    & "   Period: " & FORMAT ( MIN ( fact_reliability_monthly[month] ), "mmm yyyy" )
    & " to " & FORMAT ( MAX ( fact_reliability_monthly[month] ), "mmm yyyy" )""",
         None, "09 Formatting",
         "Small footer text. Makes a silently applied filter obvious."),

        ("Provenance Footer",
         """"Model calibrated on Port of Port Hedland, "
    & FORMAT ( MIN ( fact_reliability_monthly[month] ), "yyyy" ) & " to "
    & FORMAT ( MAX ( fact_reliability_monthly[month] ), "yyyy" )
    & ", against Bureau of Meteorology cyclone records. "
    & "Rio Tinto exports through Dampier and Cape Lambert, not Port Hedland.\"""",
         None, "09 Formatting",
         "Footer for every page. States the main limitation before anyone "
         "has to ask."),

        # ---------------- 10 Data quality ----------------
        ("Defects Found", "COUNTROWS ( dim_data_quality )",
         "#,0", "10 Data quality", "Data quality issues identified."),

        ("Defects Fixed",
         """CALCULATE (
    COUNTROWS ( dim_data_quality ),
    dim_data_quality[status] = "Fixed"
)""", "#,0", "10 Data quality", "Issues corrected rather than accepted."),

        ("High Severity Defects",
         """CALCULATE (
    COUNTROWS ( dim_data_quality ),
    dim_data_quality[severity] = "High"
)""", "#,0", "10 Data quality",
         "Defects that would have changed the conclusions if missed."),

        ("Records Affected", "SUM ( dim_data_quality[records_affected] )",
         "#,0", "10 Data quality", "Records touched by a defect."),

        ("Parse Success Rate",
         """VAR Parsed =
    CALCULATE (
        COUNTROWS ( fact_reliability_monthly ),
        NOT ISBLANK ( fact_reliability_monthly[total_throughput_mt] )
    )
VAR Total = COUNTROWS ( ALL ( fact_reliability_monthly ) )
RETURN
    DIVIDE ( Parsed, Total )""",
         "0.0%", "10 Data quality",
         "Share of source PDFs parsed automatically."),

        ("Data Quality Statement",
         """FORMAT ( [Defects Found], "0" ) & " data quality issues found, "
    & FORMAT ( [Defects Fixed], "0" ) & " corrected. "
    & FORMAT ( [High Severity Defects], "0" )
    & " would have changed the conclusions.\"""",
         None, "10 Data quality", "Summary card text for page 5."),
    ]


# ----------------------------------------------------------------------------
# Writers
# ----------------------------------------------------------------------------

def cs_escape(s: str) -> str:
    """Escape for a C# verbatim string literal."""
    return s.replace('"', '""')


def write_csx(measures, c):
    lines = [
        "// Tabular Editor 2 script — generated by src/step5_generate_dax.py",
        f"// Generated {TODAY}",
        f"// Coefficients from {c['source']}",
        "//",
        "// Usage: open your .pbix in Power BI Desktop, launch Tabular Editor",
        "// from External Tools, open this file, press F5, then File > Save.",
        "// Rerunning updates existing measures rather than duplicating them.",
        "",
        f'var tbl = Model.Tables.FirstOrDefault(t => t.Name == "{MEASURE_TABLE}");',
        "if (tbl == null) {",
        '    Error("Measure table not found. In Power BI Desktop run: '
        f'{MEASURE_TABLE} = ' + '{ BLANK() }");',
        "    return;",
        "}",
        "",
        "int created = 0, updated = 0;",
        "",
    ]

    for name, dax, fmt, folder, desc in measures:
        lines += [
            f"// ---- {name} ----",
            "{",
            f'    var name = @"{cs_escape(name)}";',
            f'    var expr = @"{cs_escape(dax)}";',
            "    var m = tbl.Measures.FirstOrDefault(x => x.Name == name);",
            "    if (m == null) { m = tbl.AddMeasure(name); created++; }",
            "    else { updated++; }",
            "    m.Expression = expr;",
            f'    m.DisplayFolder = @"{cs_escape(folder)}";',
            f'    m.Description = @"{cs_escape(desc)}";',
        ]
        if fmt:
            lines.append(f'    m.FormatString = @"{cs_escape(fmt)}";')
        lines += ["}", ""]

    lines.append(
        'Info("Measures created: " + created + ", updated: " + updated);')

    path = OUT / "measures.csx"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[save] {path.name}  ({len(measures)} measures)")


def write_tmdl(measures, c):
    lines = [
        f"/// Generated by src/step5_generate_dax.py on {TODAY}",
        f"/// Coefficients from {c['source']}",
        "",
        f"table {MEASURE_TABLE}",
        "",
    ]
    for name, dax, fmt, folder, desc in measures:
        lines.append(f"\t/// {desc}")
        lines.append(f"\tmeasure '{name}' =")
        for ln in dax.split("\n"):
            lines.append(f"\t\t\t{ln}")
        if fmt:
            lines.append(f"\t\tformatString: {fmt}")
        lines.append(f"\t\tdisplayFolder: {folder}")
        lines.append("")

    path = OUT / "measures.tmdl"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[save] {path.name}")


def write_markdown(measures, c, capability):
    by_folder = {}
    for m in measures:
        by_folder.setdefault(m[3], []).append(m)

    lines = [
        "# DAX measure reference",
        "",
        f"Generated {TODAY} by `src/step5_generate_dax.py`.",
        "",
        f"Coefficients read from {c['source']}:",
        "",
        f"- Severity coefficient: **{c['coef']:+.4f} Mt** per unit of "
        "proximity-weighted severity",
        f"- 95% confidence interval: {c['lo']:+.4f} to {c['hi']:+.4f}",
        "",
        f"Observed mean daily capability: {capability:.2f} Mt per day.",
        "",
        "## Tables this expects",
        "",
        "| Table | Source |",
        "|---|---|",
        "| `fact_reliability_monthly` | data/processed |",
        "| `fact_reliability_event` | data/processed |",
        "| `dim_return_period` | data/processed |",
        "| `dim_data_quality` | data/processed, generated by this script |",
        "| `dim_month` | Power Query, one row per month |",
        "| `Scenario Category` | DAX `GENERATESERIES ( 1, 5, 1 )` |",
        "| `Scenario Distance` | DAX `GENERATESERIES ( 0, 400, 25 )` |",
        "| `Iron Ore Price` | DAX `GENERATESERIES ( 60, 160, 10 )` |",
        "| `Lead Hours` | DAX `GENERATESERIES ( 0, 120, 6 )` |",
        "| `Curve Sensitivity` | DAX `GENERATESERIES ( 0.5, 2, 0.25 )` |",
        "",
        "Rename each scenario table's `Value` column to `Category`, `Km`, "
        "`USD per tonne`, `Hours` and `Multiplier` respectively. Leave all "
        "five with no relationships.",
        "",
        "## Loading these into Power BI",
        "",
        "Power BI Desktop has no bulk measure import. Use Tabular Editor 2:",
        "",
        "1. Download Tabular Editor 2 (free) from tabulareditor.com",
        "2. In Power BI Desktop create the holding table: "
        "`Modeling > New table`, then `_Measures = { BLANK() }`. Hide its "
        "single column.",
        "3. Load `dim_data_quality.csv`",
        "4. External Tools ribbon > Tabular Editor",
        "5. File > Open > `powerbi/measures.csx`, press F5",
        "6. File > Save, then refresh the field list in Power BI Desktop",
        "",
        "The script is idempotent: rerunning updates existing measures rather "
        "than duplicating them. Refit the model, rerun this generator, rerun "
        "the script, and the dashboard stays consistent with the analysis.",
        "",
        "## Measures",
        "",
    ]

    for folder in sorted(by_folder):
        lines.append(f"### {folder}")
        lines.append("")
        for name, dax, fmt, _, desc in by_folder[folder]:
            lines.append(f"**{name}**")
            lines.append("")
            lines.append(desc)
            lines.append("")
            lines.append("```dax")
            lines.append(f"{name} =")
            lines.append(dax)
            lines.append("```")
            if fmt:
                lines.append(f"Format: `{fmt}`")
            lines.append("")

    path = OUT / "measures.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[save] {path.name}")


# ----------------------------------------------------------------------------

def main():
    OUT.mkdir(parents=True, exist_ok=True)

    c = load_coefficients()
    capability = observed_capability()
    write_data_quality_table()
    measures = build_measures(c)

    names = [m[0] for m in measures]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise SystemExit(f"!! Duplicate measure names: {dupes}")

    write_csx(measures, c)
    write_tmdl(measures, c)
    write_markdown(measures, c, capability)

    folders = sorted({m[3] for m in measures})
    print(f"\n{len(measures)} measures across {len(folders)} folders:")
    for f in folders:
        n = sum(1 for m in measures if m[3] == f)
        print(f"  {f}: {n}")

    print("\nNEXT:")
    print(f"  1. In Power BI Desktop: Modeling > New table > "
          f"{MEASURE_TABLE} = {{ BLANK() }}")
    print("  2. Load data/processed/dim_data_quality.csv")
    print("  3. Create the five scenario tables listed in powerbi/measures.md")
    print("  4. Run powerbi/measures.csx from Tabular Editor")


if __name__ == "__main__":
    main()
