# Step 4: reliability and asset performance framing

## Why this framing

The analysis measures disruption caused by tropical cyclones. Reliability
engineering uses the same arithmetic for equipment failure: downtime,
availability, mean time between failures, mean time to restore, and how often
an event of a given severity recurs.

The difference is the failure mode. Here it is weather rather than a bearing
or a hydraulic hose. Weather-related unavailability is a standard category in
mining asset management, so no reframing is required to make the metrics fit.

Every figure below traces to Bureau of Meteorology cyclone records and
published Pilbara Ports throughput. No synthetic data is used.

## Asset performance summary

| Metric | Value |
|---|---|
| Asset | Port of Port Hedland |
| Period | Jan 2015 to Jul 2026 (11.5 years) |
| Failure mode | Tropical cyclone |
| Events | 27 |
| Total downtime | 27.1 days (650 hours) |
| Total production lost | 38.9 Mt |
| Downtime per year | 2.4 days |
| Production lost per year | 3.4 Mt |
| Availability against weather | 99.36% |
| MTBF, all events | 155 days (0.42 years) |
| MTTR, all events | 1.00 days |
| MTTR, Category 3+ | 1.75 days |

MTTR here means restoration of normal throughput, inferred from monthly
tonnage. It is not a measured repair duration.

## Worst events by downtime

| Date       | Event    |   Category |   Km to port |   Lost Mt |   Downtime days |   Availability % |
|:-----------|:---------|-----------:|-------------:|----------:|----------------:|-----------------:|
| 2025-02-14 | Zelia    |          4 |         58.1 |      4.97 |            3.47 |             88.6 |
| 2023-04-13 | Ilsa     |          5 |        114.9 |      4.68 |            3.03 |             90   |
| 2019-03-24 | Veronica |          4 |         91.8 |      4.2  |            2.91 |             90.4 |
| 2017-03-23 | Unnamed  |          2 |          8.4 |      3.19 |            2.31 |             92.4 |
| 2025-01-19 | Sean     |          3 |        111   |      2.86 |            1.8  |             94.1 |
| 2026-02-07 | Mitchell |          3 |        144.4 |      2.42 |            1.65 |             94.6 |
| 2018-01-12 | Joyce    |          2 |         91.3 |      2.11 |            1.55 |             94.9 |
| 2020-02-08 | Damien   |          3 |        191.8 |      1.91 |            1.5  |             95.1 |

## Independent check on magnitude

The regression only ever sees monthly tonnage. It has no knowledge of how long
the port closed for any event.

Converting each estimated loss into days at that month's own capability rate
gives an implied closure length. The median for the six largest events is
**2.6 days**.
Port Hedland typically clears and closes for two to four days around a severe
cyclone.

That agreement is corroboration from outside the model. It is stronger
evidence than the p-value: a significant coefficient says the effect is
unlikely to be zero, while this says the magnitude is right.

## Pareto

Category 3 and above events are 10 of 27
(37%) but account for
65% of total downtime.

This is the usual reliability picture: a small number of high-severity events
drive most of the loss, which is where mitigation effort belongs.

## Return periods

|   Min category |   Within km |   Events |   Per year |   Return period (yrs) |   P(at least one per year) |
|---------------:|------------:|---------:|-----------:|----------------------:|---------------------------:|
|              3 |         100 |        2 |      0.174 |                   5.7 |                      0.16  |
|              3 |         200 |        6 |      0.522 |                   1.9 |                      0.407 |
|              4 |         100 |        2 |      0.174 |                   5.7 |                      0.16  |
|              4 |         200 |        3 |      0.261 |                   3.8 |                      0.23  |

Read as how often an event of at least that category passes within that
distance of Port Hedland, based on 11.5 years of records.

## Limitations

1. Downtime is inferred from monthly tonnage, not measured from operational
   logs. It is an estimate of production-equivalent lost time, not a recorded
   outage duration.
2. 10 severe events is a small sample. Return periods for Category 4
   and above rest on very few observations and should be read as indicative.
3. Availability is calculated against a modelled no-cyclone capability, not a
   published nameplate capacity.
4. The port serves several miners, so this describes the port system rather
   than any single operator.
5. The 98% availability target is illustrative, not
   sourced from Pilbara Ports.

## What this does not cover

Equipment-level MTBF and MTTR, work order completeness, and failure code
analysis need maintenance system data, which no operator publishes. The
approach here was to take a failure mode where public data does exist and
apply the standard metrics to it properly, rather than simulate a maintenance
database.
