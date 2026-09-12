#!/usr/bin/env python3
"""
Step 3b — Per-event counterfactual: what would throughput have been without
the cyclone?

This replaces the cross-check at the end of step3_cyclone_effect.py, which was
wrong. That check compared Q1 2025 against the mean of all Q1 months since
2015, including years when the port was materially smaller. It was measuring
long-run growth, not cyclone impact, and returned a surplus where the
regression found a loss.

The fix is to use the fitted model itself. For each month, predict throughput
with the observed cyclone severity, then predict it again with severity set to
zero. The difference is the estimated loss, with seasonality and trend already
controlled for.

Run from the project root:
    python src/step3b_counterfactual.py

Outputs:
    data/processed/analysis_event_counterfactual.csv
    docs/step3b_counterfactual.md
"""

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
DOCS = ROOT / "docs"

FORMULA = "total_throughput_mt ~ weighted_severity + C(month_num) + t"

IRON_ORE_USD_PER_T = 100.0
AUD_PER_USD = 0.65


def main():
    df = pd.read_csv(PROC / "analysis_monthly_joined.csv", parse_dates=["month"])
    model = smf.ols(FORMULA, data=df).fit()

    # Counterfactual: same month, same trend position, zero cyclone severity
    quiet = df.copy()
    quiet["weighted_severity"] = 0.0

    df["predicted_mt"] = model.predict(df)
    df["counterfactual_mt"] = model.predict(quiet)
    df["estimated_loss_mt"] = df.counterfactual_mt - df.predicted_mt

    # Uncertainty carried through from the coefficient's confidence interval
    lo, hi = model.conf_int().loc["weighted_severity"]
    df["loss_lo_mt"] = -hi * df.weighted_severity
    df["loss_hi_mt"] = -lo * df.weighted_severity

    df["loss_aud"] = df.estimated_loss_mt * 1e6 * IRON_ORE_USD_PER_T / AUD_PER_USD

    ev = df[df.weighted_severity > 0].sort_values("estimated_loss_mt",
                                                  ascending=False)

    print("=" * 78)
    print("ESTIMATED LOSS PER CYCLONE MONTH")
    print("=" * 78)
    print("\nModel-based counterfactual. Seasonality and trend are already")
    print("controlled for, so these are not raw comparisons against a mean.\n")

    show = ev.head(15).copy()
    show["month_s"] = show.month.dt.strftime("%Y-%m")
    cols = {
        "month_s": "month",
        "total_throughput_mt": "actual",
        "counterfactual_mt": "no cyclone",
        "estimated_loss_mt": "loss",
        "loss_lo_mt": "lo",
        "loss_hi_mt": "hi",
        "max_category": "cat",
        "nearest_km": "km",
    }
    out = show[list(cols)].rename(columns=cols)
    print(out.to_string(index=False, float_format=lambda x: f"{x:8.2f}"))

    total = ev.estimated_loss_mt.sum()
    print(f"\n  Total estimated loss across {len(ev)} cyclone months: "
          f"{total:.1f} Mt")
    print(f"  Over {len(df)/12:.1f} years, that is {total/(len(df)/12):.1f} Mt "
          f"per year on average.")
    print(f"  At US${IRON_ORE_USD_PER_T:.0f}/t, roughly "
          f"A${ev.loss_aud.sum()/1e9:.1f}bn in total deferred shipment value.")

    # ------------------------------------------------------------------
    # Corrected cross-check against Rio Tinto's published figure
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("CROSS-CHECK AGAINST RIO TINTO'S 2025 ANNUAL REPORT")
    print("=" * 78)

    q1 = df[(df.month.dt.year == 2025) & (df.month_num.isin([1, 2, 3]))]
    loss_q1 = q1.estimated_loss_mt.sum()

    print(f"""
  Rio Tinto attributed roughly 13 Mt of lost Q1 2025 iron ore production to
  four cyclones affecting Western Australia, with about $0.7bn of EBITDA
  impact.

  This model estimates {loss_q1:.1f} Mt of lost throughput at Port Hedland
  across the same quarter, from Cyclones Sean and Zelia.

  These are not directly comparable, and the gap is expected:
    - Port Hedland is one port. Rio Tinto ships mainly through Dampier and
      Cape Lambert, which are not in this dataset.
    - Rio Tinto's figure is company production; this is port throughput
      across BHP, Fortescue, Roy Hill and others.
    - Rio Tinto counted four cyclones across all of Western Australia. Only
      two entered the Pilbara box used here.

  The check that matters is order of magnitude. A single-port estimate of
  {loss_q1:.1f} Mt sitting below a multi-port, whole-of-state figure of 13 Mt
  is consistent. If this model had produced 50 Mt, or a gain, something would
  be wrong.
""")

    # Naive comparison, shown deliberately to explain why it misleads
    naive_actual = q1.total_throughput_mt.mean()
    naive_norm = df[df.month_num.isin([1, 2, 3])].total_throughput_mt.mean()
    print(f"  For contrast, the naive comparison used in an earlier version of")
    print(f"  this analysis: Q1 2025 averaged {naive_actual:.1f} Mt against a")
    print(f"  {naive_norm:.1f} Mt average across all Q1 months since 2015, "
          f"implying")
    print(f"  a {(naive_actual-naive_norm)*3:+.1f} Mt surplus. That comparison is")
    print(f"  wrong: the 2015 to 2017 baseline predates roughly "
          f"{(naive_actual/naive_norm-1)*100:.0f}% of port growth,")
    print(f"  so it measures expansion rather than disruption.")

    # ------------------------------------------------------------------
    df.to_csv(PROC / "analysis_event_counterfactual.csv", index=False)
    print(f"\n[save] analysis_event_counterfactual.csv")

    DOCS.mkdir(exist_ok=True)
    write_doc(df, ev, loss_q1, naive_actual, naive_norm)


def write_doc(df, ev, loss_q1, naive_actual, naive_norm):
    tbl = ev.head(10).copy()
    tbl["month"] = tbl.month.dt.strftime("%Y-%m")
    tbl = tbl[["month", "total_throughput_mt", "counterfactual_mt",
               "estimated_loss_mt", "max_category", "nearest_km"]].round(2)
    tbl.columns = ["Month", "Actual Mt", "Counterfactual Mt",
                   "Estimated loss Mt", "Category", "Km to port"]

    text = f"""# Step 3b: per-event counterfactual

## Method

For each month, the fitted regression predicts throughput twice: once with the
observed cyclone severity, once with severity set to zero. The difference is
the estimated loss attributable to cyclone activity, with calendar month and
long-run trend already controlled for.

Model: `{FORMULA}`

## Estimated loss by event

{tbl.to_markdown(index=False)}

Total across {len(ev)} cyclone months: **{ev.estimated_loss_mt.sum():.1f} Mt**,
or about {ev.estimated_loss_mt.sum()/(len(df)/12):.1f} Mt per year.

## Cross-check against Rio Tinto

Rio Tinto attributed roughly 13 Mt of lost Q1 2025 production to four cyclones
across Western Australia. This model estimates {loss_q1:.1f} Mt of lost
throughput at Port Hedland over the same quarter.

The figures are not directly comparable. Port Hedland is one port; Rio Tinto
ships mainly through Dampier and Cape Lambert. Rio Tinto's figure is company
production across the whole state, while this is port throughput shared across
several miners. A single-port estimate sitting below a whole-of-state figure is
the expected relationship.

## A correction worth recording

An earlier version of this analysis compared Q1 2025 against the mean of all
Q1 months since 2015. That produced a {(naive_actual-naive_norm)*3:+.1f} Mt
*surplus*, contradicting the regression result from the same data.

The comparison was wrong. The 2015 to 2017 baseline predates a large part of
the port's growth, so the naive difference measured expansion rather than
disruption. The regression controls for trend; the raw comparison did not.

This is retained in the documentation rather than quietly removed, because the
contradiction between two figures derived from one dataset is what exposed the
error.
"""
    path = DOCS / "step3b_counterfactual.md"
    path.write_text(text, encoding="utf-8")
    print(f"[save] {path}")


if __name__ == "__main__":
    main()
