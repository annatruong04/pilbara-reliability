# Step 3b: per-event counterfactual

## Method

For each month, the fitted regression predicts throughput twice: once with the
observed cyclone severity, once with severity set to zero. The difference is
the estimated loss attributable to cyclone activity, with calendar month and
long-run trend already controlled for.

Model: `total_throughput_mt ~ weighted_severity + C(month_num) + t`

## Estimated loss by event

| Month   |   Actual Mt |   Counterfactual Mt |   Estimated loss Mt |   Category |   Km to port |
|:--------|------------:|--------------------:|--------------------:|-----------:|-------------:|
| 2025-02 |       37.46 |               43.57 |                4.97 |          4 |         58.1 |
| 2023-04 |       43.81 |               46.95 |                4.68 |          5 |        114.9 |
| 2019-03 |       36.75 |               43.93 |                4.2  |          4 |         91.8 |
| 2017-03 |       39.49 |               41.96 |                3.19 |          2 |          8.4 |
| 2025-01 |       46.53 |               48.23 |                2.86 |          3 |        111   |
| 2026-02 |       40.58 |               44.55 |                2.42 |          3 |        144.4 |
| 2018-01 |       41.83 |               41.42 |                2.11 |          2 |         91.3 |
| 2020-02 |       39.08 |               38.73 |                1.91 |          3 |        191.8 |
| 2016-01 |       34.09 |               39.53 |                1.69 |          2 |        135.3 |
| 2018-02 |       39.35 |               36.76 |                1.51 |          3 |        239.3 |

Total across 23 cyclone months: **38.9 Mt**,
or about 3.4 Mt per year.

## Cross-check against Rio Tinto

Rio Tinto attributed roughly 13 Mt of lost Q1 2025 production to four cyclones
across Western Australia. This model estimates 7.8 Mt of lost
throughput at Port Hedland over the same quarter.

The figures are not directly comparable. Port Hedland is one port; Rio Tinto
ships mainly through Dampier and Cape Lambert. Rio Tinto's figure is company
production across the whole state, while this is port throughput shared across
several miners. A single-port estimate sitting below a whole-of-state figure is
the expected relationship.

## A correction worth recording

An earlier version of this analysis compared Q1 2025 against the mean of all
Q1 months since 2015. That produced a +9.1 Mt
*surplus*, contradicting the regression result from the same data.

The comparison was wrong. The 2015 to 2017 baseline predates a large part of
the port's growth, so the naive difference measured expansion rather than
disruption. The regression controls for trend; the raw comparison did not.

This is retained in the documentation rather than quietly removed, because the
contradiction between two figures derived from one dataset is what exposed the
error.
